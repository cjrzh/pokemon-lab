"""双打队伍的读写与合法性校验编排。

分层：
  - 规则本身是纯函数（`domain/team_rules.py`）；
  - 本模块负责「取数据 → 调规则 → 落库」：从 `pokemon.moves_json` / `abilities_json`
    提取该格式的合法招式与特性，组装校验上下文；
  - 路由只做参数校验与响应组装。

数据边界（如实声明）：合法性以本地已同步的 PokéAPI 数据为准。本地没有某只宝可梦的
招式数据时，不把「不知道」当成「不合法」——`validate_team` 的 `moves_known` 会降级为跳过，
接口在响应里通过 `warnings` 提示。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DoubleFormat, Team, TeamMember
from app.domain.doubles_formats import FORMAT_BY_KEY
from app.domain.showdown_parser import parse_showdown
from app.domain.sketch import is_smeargle, sketchable_moves
from app.domain.smogon_stats import showdown_slug
from app.domain.team_rules import (
    FORMAT_VERSION_GROUP,
    TEAM_SIZE,
    TeamValidation,
    batch_gender,
    batch_level,
    batch_shiny,
    validate_team,
)
from app.repositories import pokemon_repo
from app.schemas.teams import DEFAULT_LANGUAGE
from app.services import form_service
from app.services.doubles_service import resolve_name_index

logger = logging.getLogger(__name__)

#: 个人自用：不再按浏览器隔离，新队伍统一写这个归属值。
#: `team.owner_key` 列保留以兼容旧数据（旧队伍各自带着原来的 UUID），只是不再参与过滤。
LOCAL_OWNER = "local"


class TeamError(ValueError):
    """队伍操作失败。"""


@dataclass
class TeamValidationContext:
    """校验所需的数据快照。"""

    points_kind: str
    legal_moves: dict[int, set[str]] = field(default_factory=dict)
    legal_abilities: dict[int, set[str]] = field(default_factory=dict)
    moves_known: bool = True
    warnings: list[str] = field(default_factory=list)


def _moves_for_version_group(moves_json: str, version_group: str) -> set[str]:
    """从 `moves_json` 取某个版本组里能学会的招式名集合。"""
    try:
        payload = json.loads(moves_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return set()
    groups = payload.get("version_groups") or {}
    group = groups.get(version_group) or {}
    moves: set[str] = set()
    for entries in (group.get("methods") or {}).values():
        for entry in entries:
            name = entry.get("name") if isinstance(entry, dict) else None
            if name:
                moves.add(name)
    return moves


def _form_moves_for_version_group(forms: list[tuple[str, str]]) -> set[str]:
    """形态的招式表 → 可学招式集合（调用方已按版本组筛选）。

    `forms` 是 [(形态名, 该形态在该版本组的招式明细 JSON)]；明细结构为
    `{学习方式: [{name, level}, …]}`。
    """
    legal: set[str] = set()
    for _name, methods_json in forms:
        try:
            methods = json.loads(methods_json or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(methods, dict):
            continue
        for entries in methods.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                name = entry.get("name") if isinstance(entry, dict) else None
                if name:
                    legal.add(name)
    return legal


def _abilities_from_json(abilities_json: str) -> set[str]:
    try:
        payload = json.loads(abilities_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return set()
    return {
        item["name"]
        for item in payload
        if isinstance(item, dict) and item.get("name")
    }


def ancestor_dex_numbers(evolution_json: str, dex_number: int) -> list[int]:
    """进化链上排在 `dex_number` 之前的编号（不含自己），从最早形态到直接前身。

    用于「继承前代招式」：一只宝可梦保留了进化前形态能学的招式，
    所以合法性判定不能只看它自己的招式表。例：雷丘的 Fake Out 来自皮丘（蛋招式）。
    数据缺失或编号不在链上时返回空列表。
    """
    try:
        payload = json.loads(evolution_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return []
    chain = payload.get("chain")
    if not isinstance(chain, dict):
        return []

    def walk(node: dict, path: list[int]) -> list[int] | None:
        current = path + [node["dex"]] if isinstance(node.get("dex"), int) else path
        if node.get("dex") == dex_number:
            return current[:-1]  # 不含自己
        for child in node.get("evolves_to") or []:
            if isinstance(child, dict):
                found = walk(child, current)
                if found is not None:
                    return found
        return None

    return walk(chain, []) or []


async def build_validation_context(
    session: AsyncSession, format_key: str, dex_numbers: list[int]
) -> TeamValidationContext:
    """组装某个格式下这些宝可梦的合法招式 / 特性。

    招式取「自己的招式表 ∪ 进化链上前代的招式表」：一只宝可梦保留进化前学过的招式，
    只查自己会误判合法配置为非法（如雷丘的 Fake Out 来自皮丘的蛋招式）。
    """
    fmt = FORMAT_BY_KEY.get(format_key)
    points_kind = fmt.points_kind if fmt else "ev"
    version_group = FORMAT_VERSION_GROUP.get(format_key, "")
    context = TeamValidationContext(points_kind=points_kind)

    moves_rows = await pokemon_repo.get_moves_json_map(session, dex_numbers)
    abilities_rows = await pokemon_repo.get_abilities_map(session, dex_numbers)
    evolution_rows = await pokemon_repo.get_evolution_json_map(session, dex_numbers)
    # 形态专属的招式 / 特性（如水熊的「水流连打」、蕾冠王的「人马一体」）：
    # PokéAPI 的默认形态表单里没有它们，必须并入同编号的形态数据，否则合法的
    # 官方配置会被误判成非法。形态是「同一编号的另一个样子」，按编号合并是安全的。
    form_moves = await pokemon_repo.get_form_moves_map(session, dex_numbers, version_group)
    form_abilities = await pokemon_repo.get_form_abilities_map(session, dex_numbers)

    # 先把进化链上的前代编号收集齐，再一次性取它们的招式表（避免 N+1 查询）
    ancestors: dict[int, list[int]] = {}
    for dex in dex_numbers:
        chain = ancestor_dex_numbers(evolution_rows.get(dex, "{}"), dex)
        ancestors[dex] = chain
    pre_dex = {ancestor for chain in ancestors.values() for ancestor in chain}
    pre_moves_rows = await pokemon_repo.get_moves_json_map(session, sorted(pre_dex))

    missing: list[int] = []
    for dex in dex_numbers:
        moves_json = moves_rows.get(dex)
        if moves_json is None:
            missing.append(dex)
            continue
        legal = _moves_for_version_group(moves_json, version_group)
        for ancestor_dex in ancestors.get(dex, []):
            ancestor_json = pre_moves_rows.get(ancestor_dex)
            if ancestor_json:
                legal |= _moves_for_version_group(ancestor_json, version_group)
        legal |= _form_moves_for_version_group(form_moves.get(dex, []))
        context.legal_moves[dex] = legal
        if not legal:
            missing.append(dex)
        abilities = _abilities_from_json(abilities_rows.get(dex, "[]"))
        for form_json in form_abilities.get(dex, []):
            abilities |= _abilities_from_json(form_json)
        context.legal_abilities[dex] = abilities

    if missing:
        context.moves_known = False
        unique = sorted(set(missing))
        context.warnings.append(
            f"本地缺少 {len(unique)} 只宝可梦在该版本的招式数据"
            f"（#{', #'.join(str(dex) for dex in unique[:5])}"
            f"{' 等' if len(unique) > 5 else ''}），招式合法性未校验"
        )

    # 图图犬的「写生」：招式表里只有写生本身，但写生能复制本版本任意宝可梦学会的
    # 招式（排除暗黑洞这类不能写生的）。不展开的话建队页只能选一个「写生」。
    for dex in dex_numbers:
        if not is_smeargle(dex, context.legal_moves.get(dex, set())):
            continue
        version_moves = await pokemon_repo.list_moves_for_version(session, version_group)
        context.legal_moves[dex] = context.legal_moves.get(dex, set()) | sketchable_moves(
            version_moves
        )

    return context


async def validate_members(
    session: AsyncSession, format_key: str, members: list[dict]
) -> TeamValidation:
    dex_numbers = [member["dex_number"] for member in members if member.get("dex_number")]
    context = await build_validation_context(session, format_key, dex_numbers)
    return validate_team(
        members,
        points_kind=context.points_kind,
        legal_moves=context.legal_moves,
        legal_abilities=context.legal_abilities,
        moves_known=context.moves_known,
        format_key=format_key,
        gmax_allowed=gigantamax_allowed_names(),
    )


def gigantamax_allowed_names() -> set[str]:
    """能开启超极巨化的 Showdown 名（slug）；清单文件缺失时为空集合。"""
    return set(form_service.load_gigantamax_map())


async def list_teams(session: AsyncSession) -> list[Team]:
    """所有队伍（个人自用，不做浏览器隔离），按用户拖动的顺序排列。

    `team.owner_key` 列仍保留（旧数据带着它），但不再参与查询过滤 ——
    历史队伍与新建队伍都一视同仁地列出来。

    `sort_order` 是用户手动排序的结果；相同值（旧数据默认 0）按 id 升序兜底，
    保证顺序稳定、分页不会跳。
    """
    stmt = select(Team).order_by(Team.sort_order.asc(), Team.id.asc())
    return list((await session.execute(stmt)).scalars().all())


async def reorder_teams(session: AsyncSession, team_ids: list[int]) -> list[Team]:
    """按给定顺序重写 `sort_order`（整表顺序，前端传完整列表）。

    只接受存在的 id：不存在的直接忽略，而不是报错 —— 例如另一个标签页刚删了队伍。
    未出现在列表里的队伍保持不变（它们会排在后面，因为新顺序从 0 开始编号）。
    """
    teams = list((await session.execute(select(Team))).scalars().all())
    by_id = {team.id: team for team in teams}

    position = 0
    for team_id in team_ids:
        team = by_id.get(team_id)
        if team is None:
            continue
        team.sort_order = position
        position += 1

    await session.flush()
    return await list_teams(session)


async def get_team(session: AsyncSession, team_id: int) -> Team | None:
    stmt = select(Team).where(Team.id == team_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_members(session: AsyncSession, team_id: int) -> list[TeamMember]:
    stmt = (
        select(TeamMember)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.position.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_teams(session: AsyncSession) -> int:
    from sqlalchemy import func

    return (
        await session.execute(select(func.count()).select_from(Team))
    ).scalar_one()


async def create_team(
    session: AsyncSession,
    *,
    name: str,
    format_key: str,
    note: str | None,
    members: list[dict],
) -> Team:
    # 新队伍排到列表最前面：取当前最小的 sort_order − 1（空表时为 0）。
    # 建队页左侧列表按 sort_order 升序显示，新建后立刻在顶部可见。
    current_min = (
        await session.execute(select(func.min(Team.sort_order)))
    ).scalar_one_or_none()
    sort_order = 0 if current_min is None else current_min - 1

    team = Team(
        # owner_key 列仍存在（旧数据结构），个人自用不再区分归属，统一写这个占位值。
        owner_key=LOCAL_OWNER,
        name=name.strip(),
        format_key=format_key,
        note=note,
        sort_order=sort_order,
    )
    session.add(team)
    await session.flush()
    await _replace_members(session, team, members)
    # updated_at 是 server_default，flush 后取回真实值，避免响应组装时触发懒加载
    await session.refresh(team)
    return team


async def update_team(
    session: AsyncSession,
    team: Team,
    *,
    name: str | None = None,
    note: str | None = None,
    members: list[dict] | None = None,
) -> Team:
    if name is not None:
        team.name = name.strip()
    if note is not None:
        team.note = note
    if members is not None:
        await _replace_members(session, team, members)
    await session.flush()
    await session.refresh(team)
    return team


async def delete_team(session: AsyncSession, team: Team) -> None:
    await session.execute(delete(TeamMember).where(TeamMember.team_id == team.id))
    await session.delete(team)
    await session.flush()


async def _replace_members(session: AsyncSession, team: Team, members: list[dict]) -> None:
    """整体替换成员（队伍编辑按整队提交，避免逐只 diff 的复杂度）。"""
    await session.execute(delete(TeamMember).where(TeamMember.team_id == team.id))
    for position, member in enumerate(members):
        session.add(
            TeamMember(
                team_id=team.id,
                position=position,
                dex_number=member["dex_number"],
                showdown_name=member["showdown_name"],
                nickname=member.get("nickname"),
                item=member.get("item"),
                ability=member.get("ability"),
                nature=member.get("nature"),
                evs_json=json.dumps(member.get("evs") or [0, 0, 0, 0, 0, 0]),
                ivs_json=(
                    json.dumps(member["ivs"]) if member.get("ivs") is not None else None
                ),
                moves_json=json.dumps(member.get("moves") or [], ensure_ascii=False),
                tera_type=member.get("tera_type"),
                gender=member.get("gender"),
                shiny=bool(member.get("shiny")),
                level=member.get("level"),
                dynamax_level=member.get("dynamax_level"),
                gigantamax=bool(member.get("gigantamax")),
                language=member.get("language") or DEFAULT_LANGUAGE,
            )
        )
    await session.flush()


def member_payload(member: TeamMember) -> dict:
    """ORM → 响应字段。"""
    return {
        "position": member.position,
        "dex_number": member.dex_number,
        "showdown_name": member.showdown_name,
        "nickname": member.nickname,
        "item": member.item,
        "ability": member.ability,
        "nature": member.nature,
        "evs": json.loads(member.evs_json or "[0,0,0,0,0,0]"),
        "ivs": json.loads(member.ivs_json) if member.ivs_json else None,
        "moves": json.loads(member.moves_json or "[]"),
        "tera_type": member.tera_type,
        "gender": member.gender,
        "shiny": member.shiny,
        "level": member.level,
        "dynamax_level": member.dynamax_level,
        "gigantamax": member.gigantamax,
        "language": member.language or DEFAULT_LANGUAGE,
    }


def format_meta(format_key: str) -> dict:
    """队伍相关格式元数据（交易前缀 / 默认等级 / 配点类型）。"""
    fmt = FORMAT_BY_KEY.get(format_key)
    if fmt is None:
        return {}
    return {
        "key": fmt.key,
        "label": fmt.label,
        "short_label": fmt.short_label,
        "points_kind": fmt.points_kind,
        "trade_prefix": fmt.trade_prefix,
        "default_level": fmt.default_level,
        "month": fmt.month,
        "cutoff": fmt.cutoff,
    }


async def available_formats(session: AsyncSession) -> list[DoubleFormat]:
    """已导入统计的格式（队伍只能建在有数据的版本上）。"""
    rows = list((await session.execute(select(DoubleFormat))).scalars().all())
    order = {key: index for index, key in enumerate(FORMAT_VERSION_GROUP)}
    return sorted(rows, key=lambda row: order.get(row.key, len(order)))


# ---------------------------------------------------------------------------
# Showdown 代码导入（文本 → 成员配置；物种名 → 图鉴编号需要查库）
# ---------------------------------------------------------------------------


@dataclass
class ImportOutcome:
    members: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def apply_batch(
    session: AsyncSession,
    members: list[dict],
    *,
    shine: bool | None,
    set_level: bool,
    level: int | None,
    set_gender: bool,
    gender: str | None,
) -> tuple[list[dict], list[str]]:
    """对成员列表做批量修改（闪光 / 等级 / 性别），返回（新列表, 跳过说明）。

    性别需要 `gender_rate` 才能判断合法性，所以在这里查库补上；
    规则本身是纯函数（`domain/team_rules.py`）。
    """
    updated = [dict(member) for member in members]
    skipped: list[str] = []

    if shine is not None:
        updated, _ = batch_shiny(updated, shine)

    if set_level:
        updated, _ = batch_level(updated, level)

    if set_gender:
        dex_numbers = [member["dex_number"] for member in updated if member.get("dex_number")]
        rates = await pokemon_repo.get_gender_rates(session, dex_numbers)
        updated, skipped = batch_gender(updated, gender, rates)

    return updated, skipped


async def import_showdown(session: AsyncSession, format_key: str, text: str) -> ImportOutcome:
    """把 Showdown 队伍文本转成可提交的成员列表。

    流程：纯函数解析（`domain/showdown_parser.py`）→ 物种名映射到图鉴编号 →
    按该格式重新组装字段。**不落库**：前端拿到结果后进编辑器，用户确认再保存，
    这样导入出错时不会污染已有队伍。

    数据边界：
      - 物种名解析不到编号时，该只跳过并记入 `problems`（不猜）；
      - 招式 / 特性按 Showdown 显示名保留，保存时的合法性校验与手工建队一致。
    """
    parsed = parse_showdown(text)
    outcome = ImportOutcome(problems=list(parsed.problems))

    if not parsed.sets:
        if not outcome.problems:
            outcome.problems.append("没有识别到任何宝可梦")
        return outcome

    name_rows = await pokemon_repo.get_name_rows(session)
    index = resolve_name_index(name_rows)
    # 形态（如 `Urshifu-Rapid-Strike` / `Arcanine-Hisui`）也要能解析到编号：
    # 否则赛事队表导出的 Showdown 代码在建队页会「无法识别」。
    forms = await pokemon_repo.get_form_name_rows(session)
    for form_name, dex in forms:
        index.exact.setdefault(showdown_slug(form_name), dex)

    seen: set[int] = set()
    for parsed_set in parsed.sets:
        # 导入用 Showdown 名（如 `Charizard-Gmax`）时拆掉 G 后缀：G 形态不是
        # 独立的宝可梦，超极巨化由 `gigantamax` 标记表达。
        # 前缀写法（`Gigantamax Charizard`）在解析器里已经剥掉并标记。
        species = parsed_set.species
        gigantamax = parsed_set.gigantamax
        if species.lower().endswith("-gmax"):
            species = species[: -len("-gmax")]
            gigantamax = True
        dex = index.resolve(species)
        if dex is None:
            outcome.problems.append(
                f"无法识别「{parsed_set.species}」对应的图鉴编号，已跳过"
            )
            continue
        # 与队伍规则一致：同一图鉴编号只能出现一次（不同形态也算重复）
        if dex in seen:
            outcome.problems.append(
                f"「{parsed_set.species}」与前面的成员图鉴编号相同（#{dex}），只保留第一只"
            )
            continue
        if len(outcome.members) >= TEAM_SIZE:
            outcome.problems.append(f"超过 {TEAM_SIZE} 只，后面的已忽略")
            break
        seen.add(dex)

        outcome.members.append(
            {
                "dex_number": dex,
                "showdown_name": species,
                "nickname": parsed_set.nickname,
                "item": parsed_set.item,
                "ability": parsed_set.ability,
                "nature": parsed_set.nature,
                "evs": parsed_set.evs,
                "ivs": parsed_set.ivs,
                "moves": parsed_set.moves,
                "tera_type": parsed_set.tera_type,
                "gender": parsed_set.gender,
                "shiny": parsed_set.shiny,
                "level": parsed_set.level,
                "dynamax_level": parsed_set.dynamax_level,
                "gigantamax": gigantamax,
                "language": parsed_set.language or DEFAULT_LANGUAGE,
            }
        )

    return outcome
