"""pokemon 表仓储：只做 SQL/ORM 读写，不含业务判断。

列表查询的三类条件（搜索 / 属性筛选 / 世代筛选）都以参数传入，由仓储拼装。
`types_json` 是 JSON 文本数组，属性筛选用 LIKE 匹配 `"fire"` 子串 —— 18 个属性名
都是不含引号与逗号的纯小写单词，LIKE '"fire"' 不会误命中（不存在子串嵌套）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Ability,
    AdminOpLog,
    MoveLearner,
    MoveReference,
    Pokemon,
)
from app.domain.pokemon_parser import DAMAGE_CLASS_ZH


@dataclass(frozen=True)
class PokemonListQuery:
    """列表查询条件。全部可选，空条件 = 全量分页。"""

    search: str | None = None  # 中英文名子串（不区分大小写）
    type_filter: str | None = None  # 属性英文键，如 "fire"
    generation: int | None = None  # 登场世代
    sort: str = "dex"  # dex / dex_desc / total_stats / total_stats_asc
    page: int = 1  # 从 1 起
    page_size: int = 20


#: 排序字段白名单（路由用它校验，仓储按此分支）。
POKEMON_SORT_FIELDS = ("dex", "dex_desc", "total_stats", "total_stats_asc")

#: 与 `STAT_ORDER` 一致；stats_json 的键带连字符，json_extract 路径需要加引号。
_STAT_JSON_KEYS = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")


def _total_stats_expr():
    """六项种族值之和（SQL 表达式），用于列表排序。

    stats_json 按项目存为 JSON 文本，SQLite 可直接用 json_extract 求和；
    逐项 coalesce 0，缺失的项按 0 计（与展示层的 `total_stats` 一致）。
    空对象视为「没有数据」，返回 NULL，让它在升序 / 降序里都排到最后。
    """
    total = None
    for key in _STAT_JSON_KEYS:
        value = func.coalesce(func.json_extract(Pokemon.stats_json, f'$."{key}"'), 0)
        total = value if total is None else total + value
    return case((Pokemon.stats_json == "{}", None), else_=total)


@dataclass(frozen=True)
class PokemonPage:
    """分页结果。"""

    items: list[Pokemon]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


def _apply_filters(stmt: Select, query: PokemonListQuery) -> Select:
    if query.search:
        raw = query.search.strip()
        keyword = f"%{raw.lower()}%"
        condition = func.lower(Pokemon.name_en).like(keyword) | func.ifnull(
            Pokemon.name_zh, ""
        ).like(keyword)
        # 纯数字输入按图鉴编号精确匹配（如「025」「25」）；同时保留名称子串匹配。
        if raw.isdigit():
            condition = condition | (Pokemon.dex_number == int(raw))
        stmt = stmt.where(condition)
    if query.type_filter:
        # types_json 形如 ["fire","flying"]，LIKE 匹配带引号的属性名
        stmt = stmt.where(Pokemon.types_json.like(f'%"{query.type_filter}"%'))
    if query.generation is not None:
        stmt = stmt.where(Pokemon.generation_introduced == query.generation)
    return stmt


async def list_pokemon(session: AsyncSession, query: PokemonListQuery) -> PokemonPage:
    """分页列表。默认按图鉴编号升序，也可按编号降序或种族值合计排序。

    排序发生在筛选之后（同一 SQL 的 WHERE → ORDER BY），所以属性 / 世代 / 搜索
    的结果子集会被整体重新排序，再分页。
    """
    base = _apply_filters(select(Pokemon), query)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    page = max(1, query.page)
    page_size = max(1, min(200, query.page_size))

    if query.sort == "dex_desc":
        order = (Pokemon.dex_number.desc(),)
    elif query.sort in ("total_stats", "total_stats_asc"):
        expr = _total_stats_expr()
        # 没有种族值的记录排在最后；同分按图鉴编号，保证分页稳定
        order = (
            expr.is_(None),
            expr.desc() if query.sort == "total_stats" else expr.asc(),
            Pokemon.dex_number.asc(),
        )
    else:
        order = (Pokemon.dex_number.asc(),)

    stmt = base.order_by(*order).offset((page - 1) * page_size).limit(page_size)
    items = list((await session.execute(stmt)).scalars().all())

    return PokemonPage(items=items, total=total, page=page, page_size=page_size)


async def get_name_rows(session: AsyncSession) -> list[tuple[str, int]]:
    """全部 (name_en, dex_number)，供 Showdown 名称映射使用。"""
    rows = (await session.execute(select(Pokemon.name_en, Pokemon.dex_number))).all()
    return [(name, dex) for name, dex in rows]


async def get_zh_names(session: AsyncSession, dex_numbers: list[int]) -> dict[int, str | None]:
    """批量取中文名：dex_number → name_zh（未同步的编号不会出现在结果里）。"""
    if not dex_numbers:
        return {}
    stmt = select(Pokemon.dex_number, Pokemon.name_zh).where(
        Pokemon.dex_number.in_(set(dex_numbers))
    )
    rows = (await session.execute(stmt)).all()
    return {dex: zh for dex, zh in rows}


async def get_by_dex_number(session: AsyncSession, dex_number: int) -> Pokemon | None:
    return (
        await session.execute(select(Pokemon).where(Pokemon.dex_number == dex_number))
    ).scalar_one_or_none()


async def get_neighbors(
    session: AsyncSession, dex_number: int
) -> tuple[Pokemon | None, Pokemon | None]:
    """同图鉴中编号最接近的前后各一条（用于详情页的上一只 / 下一只）。"""
    prev_stmt = (
        select(Pokemon)
        .where(Pokemon.dex_number < dex_number)
        .order_by(Pokemon.dex_number.desc())
        .limit(1)
    )
    next_stmt = (
        select(Pokemon)
        .where(Pokemon.dex_number > dex_number)
        .order_by(Pokemon.dex_number.asc())
        .limit(1)
    )
    prev = (await session.execute(prev_stmt)).scalar_one_or_none()
    nxt = (await session.execute(next_stmt)).scalar_one_or_none()
    return prev, nxt


async def get_by_name(session: AsyncSession, name: str) -> Pokemon | None:
    """按英文名精确查找（同步脚本补数据时使用）。"""
    return (
        await session.execute(select(Pokemon).where(Pokemon.name_en == name))
    ).scalar_one_or_none()


async def upsert_pokemon(session: AsyncSession, record: dict) -> Pokemon:
    """按 dex_number 插入或更新。返回落库后的 ORM 对象。

    注意：`source=manual` 的记录由调用方（同步服务）决定是否跳过，仓储本身不判断 ——
    仓储不做业务判断是分层约定。
    """
    existing = await get_by_dex_number(session, record["dex_number"])
    if existing is None:
        record = {**record, "synced_at": datetime.now(UTC)}
        created = Pokemon(**record)
        session.add(created)
        await session.flush()
        return created

    for key, value in record.items():
        setattr(existing, key, value)
    existing.synced_at = datetime.now(UTC)
    await session.flush()
    return existing


async def update_pokemon_fields(session: AsyncSession, pokemon: Pokemon, fields: dict) -> Pokemon:
    """手动编辑：只更新给定字段，并把来源标记为 manual。"""
    allowed = {
        "name_en",
        "name_zh",
        "types_json",
        "stats_json",
        "abilities_json",
        "evolution_json",
        "moves_json",
        "genus_zh",
        "flavor_zh",
        "generation_introduced",
        "height_dm",
        "weight_hg",
        "is_demo",
    }
    for key, value in fields.items():
        if key in allowed:
            setattr(pokemon, key, value)
    pokemon.source = "manual"
    await session.flush()
    return pokemon


async def set_artwork_path(
    session: AsyncSession, pokemon: Pokemon, artwork_path: str | None
) -> Pokemon:
    """只更新立绘缓存路径。

    不走 `update_pokemon_fields`：补图片不属于人工编辑，不应把记录标记为 manual
    （否则后续同步会跳过这条，反而保护了过期数据）。
    """
    pokemon.artwork_path = artwork_path
    await session.flush()
    return pokemon


async def set_sprite_path(
    session: AsyncSession, pokemon: Pokemon, sprite_path: str | None
) -> Pokemon:
    """只更新小图标缓存路径（同 `set_artwork_path`，不标记 manual）。"""
    pokemon.sprite_path = sprite_path
    await session.flush()
    return pokemon


async def upsert_move_refs(session: AsyncSession, moves: list[dict]) -> int:
    """批量 upsert 招式参考数据（move_ref 表）。返回写入条数。

    招式详情是共享参考数据：同一招式的数值在 151 只宝可梦之间复用，单独建表
    避免在每只宝可梦的 moves_json 里重复存储。
    """
    if not moves:
        return 0
    names = [m["name"] for m in moves]
    existing = {
        row.name: row
        for row in (
            await session.execute(select(MoveReference).where(MoveReference.name.in_(names)))
        )
        .scalars()
        .all()
    }
    for move in moves:
        row = existing.get(move["name"])
        if row is None:
            session.add(MoveReference(**_move_ref_fields(move)))
        else:
            for key, value in _move_ref_fields(move).items():
                setattr(row, key, value)
    await session.flush()
    return len(moves)


def _move_ref_fields(move: dict) -> dict:
    return {
        "name": move["name"],
        "zh": move.get("zh"),
        "type": move.get("type"),
        "damage_class": move.get("damage_class"),
        "power": move.get("power"),
        "accuracy": move.get("accuracy"),
        "pp": move.get("pp"),
        "description_zh": move.get("description_zh"),
    }


async def get_move_refs(session: AsyncSession, names: list[str]) -> dict[str, dict]:
    """按名称取招式参考数据（详情接口用）。"""
    if not names:
        return {}
    rows = (
        (await session.execute(select(MoveReference).where(MoveReference.name.in_(set(names)))))
        .scalars()
        .all()
    )
    return {
        row.name: {
            "name": row.name,
            "zh": row.zh,
            "type": row.type,
            "damage_class": row.damage_class,
            "damage_class_zh": DAMAGE_CLASS_ZH.get(row.damage_class or ""),
            "power": row.power,
            "accuracy": row.accuracy,
            "pp": row.pp,
            "description_zh": row.description_zh,
        }
        for row in rows
    }


async def get_card_fields(session: AsyncSession, dex_numbers: list[int]) -> dict[int, dict]:
    """批量取列表卡片需要的字段：编号 → 名称 / 属性 / 立绘 / 传说标记。

    使用率排行榜等「只要一张卡」的场景使用；不加载 moves_json 等大字段。
    """
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(
                Pokemon.dex_number,
                Pokemon.name_en,
                Pokemon.name_zh,
                Pokemon.types_json,
                Pokemon.artwork_path,
                Pokemon.artwork_url,
                Pokemon.sprite_url,
                Pokemon.is_legendary,
                Pokemon.is_mythical,
            ).where(Pokemon.dex_number.in_(set(dex_numbers)))
        )
    ).all()
    result: dict[int, dict] = {}
    for (
        dex,
        name_en,
        name_zh,
        types_json,
        artwork_path,
        artwork_url,
        sprite_url,
        legendary,
        mythical,
    ) in rows:
        try:
            types = json.loads(types_json or "[]")
        except (json.JSONDecodeError, TypeError):
            types = []
        result[dex] = {
            "dex_number": dex,
            "name_en": name_en,
            "name_zh": name_zh,
            "types": types if isinstance(types, list) else [],
            "artwork_path": artwork_path,
            "artwork_url": artwork_url,
            "sprite_url": sprite_url,
            "is_legendary": legendary,
            "is_mythical": mythical,
        }
    return result


# ---------------------------------------------------------------------------
# 招式百科（move_ref + move_learner）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveListQuery:
    """招式列表筛选。`sort` 只接受白名单字段，避免拼 SQL 注入。"""

    search: str | None = None
    type_filter: str | None = None
    damage_class: str | None = None
    machine_only: bool = False
    sort: str = "name"
    page: int = 1
    page_size: int = 50


MOVE_SORT_COLUMNS = {
    "name": MoveReference.name,
    "power": MoveReference.power,
    "accuracy": MoveReference.accuracy,
    "pp": MoveReference.pp,
    "learners": MoveReference.learner_count,
}


async def list_moves(session: AsyncSession, query: MoveListQuery) -> tuple[list, int]:
    """招式列表：名称搜索、属性 / 分类 / 学习器筛选、排序与分页。

    默认按中文名排序（无中文时落到英文）；`learners` 按学习者数量降序。
    """
    stmt = select(MoveReference)
    if query.search:
        keyword = f"%{query.search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(MoveReference.name).like(keyword)
            | func.lower(MoveReference.name_en or "").like(keyword)
            | func.ifnull(MoveReference.zh, "").like(keyword)
            | func.ifnull(MoveReference.description_zh, "").like(keyword)
        )
    if query.type_filter:
        stmt = stmt.where(MoveReference.type == query.type_filter)
    if query.damage_class:
        stmt = stmt.where(MoveReference.damage_class == query.damage_class)
    if query.machine_only:
        stmt = stmt.where(MoveReference.is_machine.is_(True))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    page = max(1, query.page)
    page_size = max(1, min(200, query.page_size))

    column = MOVE_SORT_COLUMNS.get(query.sort, MoveReference.name)
    if query.sort == "learners":
        order = (column.desc(), MoveReference.name.asc())
    elif query.sort == "name":
        order = (func.ifnull(MoveReference.zh, MoveReference.name).asc(),)
    else:
        # 数值型字段：None（变化招式没有威力等）排在最后
        order = (column.is_(None), column.desc(), MoveReference.name.asc())

    stmt = stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


async def get_move(session: AsyncSession, name: str) -> MoveReference | None:
    return (
        await session.execute(select(MoveReference).where(MoveReference.name == name))
    ).scalar_one_or_none()


async def get_move_learners(session: AsyncSession, name: str) -> list[MoveLearner]:
    stmt = (
        select(MoveLearner)
        .where(MoveLearner.move_name == name)
        .order_by(MoveLearner.dex_number.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_pokemon_briefs(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, tuple[str | None, str, str, bool, bool]]:
    """批量取学习者的展示信息：dex → (中文名, 英文名, types_json, 传说, 幻之)。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(
                Pokemon.dex_number,
                Pokemon.name_zh,
                Pokemon.name_en,
                Pokemon.types_json,
                Pokemon.is_legendary,
                Pokemon.is_mythical,
            ).where(Pokemon.dex_number.in_(set(dex_numbers)))
        )
    ).all()
    return {
        dex: (name_zh, name_en, types_json, legendary, mythical)
        for dex, name_zh, name_en, types_json, legendary, mythical in rows
    }


async def get_move_type_options(session: AsyncSession) -> list[str]:
    """库里实际出现过的招式属性（供筛选按钮）。"""
    rows = (
        await session.execute(
            select(MoveReference.type)
            .where(MoveReference.type.is_not(None))
            .group_by(MoveReference.type)
        )
    ).all()
    return sorted({value for (value,) in rows if value})


async def list_missing_artwork(session: AsyncSession, limit: int | None = None) -> list[Pokemon]:
    """列出没有本地立绘的记录（供补图脚本使用）。"""
    stmt = select(Pokemon).where(Pokemon.artwork_path.is_(None)).order_by(Pokemon.dex_number.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def list_missing_sprites(session: AsyncSession, limit: int | None = None) -> list[Pokemon]:
    """列出没有本地小图标的记录（供补图脚本使用）。"""
    stmt = select(Pokemon).where(Pokemon.sprite_path.is_(None)).order_by(Pokemon.dex_number.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def create_manual_pokemon(session: AsyncSession, record: dict) -> Pokemon:
    """手动新增：来源标记 manual。dex_number 冲突时抛 ValueError（调用方转 409）。"""
    if await get_by_dex_number(session, record["dex_number"]) is not None:
        raise ValueError(f"图鉴编号 {record['dex_number']} 已存在")
    record = {
        **record,
        "source": "manual",
        "is_demo": record.get("is_demo", False),
        "synced_at": datetime.now(UTC),
    }
    created = Pokemon(**record)
    session.add(created)
    await session.flush()
    return created


async def count_pokemon(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Pokemon))).scalar_one()


async def get_sync_overview(session: AsyncSession) -> dict:
    """同步总览：总数、来源分布、最近同步时间。供管理页与 selfcheck 使用。"""
    total = await count_pokemon(session)
    from_sync = (
        await session.execute(select(func.count()).where(Pokemon.source == "pokeapi"))
    ).scalar_one()
    from_manual = (
        await session.execute(select(func.count()).where(Pokemon.source == "manual"))
    ).scalar_one()
    demo_count = (
        await session.execute(select(func.count()).where(Pokemon.is_demo.is_(True)))
    ).scalar_one()
    last_synced = (await session.execute(select(func.max(Pokemon.synced_at)))).scalar_one()
    artwork_cached = (
        await session.execute(select(func.count()).where(Pokemon.artwork_path.is_not(None)))
    ).scalar_one()
    moves_covered = (
        await session.execute(select(func.count()).where(Pokemon.moves_json.not_in(("{}", ""))))
    ).scalar_one()

    # 按世代统计：generation_introduced 缺失的记录归入 None（不会出现在 map 键里）
    per_generation = dict(
        (
            await session.execute(
                select(Pokemon.generation_introduced, func.count())
                .where(Pokemon.generation_introduced.is_not(None))
                .group_by(Pokemon.generation_introduced)
                .order_by(Pokemon.generation_introduced.asc())
            )
        ).all()
    )

    return {
        "total": total,
        "from_pokeapi": from_sync,
        "from_manual": from_manual,
        "demo": demo_count,
        "last_synced_at": last_synced.isoformat() if last_synced else None,
        "artwork_cached": artwork_cached,
        "moves_covered": moves_covered,
        "per_generation": per_generation,
    }


async def log_admin_op(
    session: AsyncSession, action: str, target: str | None = None, detail: str | None = None
) -> None:
    """记录一次后台操作。失败不影响主流程（由调用方决定是否吞异常）。"""
    session.add(AdminOpLog(action=action, target=target, detail=detail))


async def list_admin_ops(session: AsyncSession, limit: int = 50) -> list[AdminOpLog]:
    stmt = select(AdminOpLog).order_by(AdminOpLog.id.desc()).limit(min(limit, 200))
    return list((await session.execute(stmt)).scalars().all())


def parse_json_fields(pokemon: Pokemon) -> dict:
    """把 ORM 对象转成带解析后 JSON 字段的字典（响应组装用）。"""

    def safe_loads(text: str, default):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return default

    stats = safe_loads(pokemon.stats_json, {})
    return {
        "id": pokemon.id,
        "dex_number": pokemon.dex_number,
        "name_en": pokemon.name_en,
        "name_zh": pokemon.name_zh,
        "name_ja": pokemon.name_ja,
        "types": safe_loads(pokemon.types_json, []),
        "stats": stats,
        "total_stats": sum(stats.values()) if stats else None,
        "abilities": safe_loads(pokemon.abilities_json, []),
        "evolution": safe_loads(pokemon.evolution_json, {}),
        "moves": safe_loads(pokemon.moves_json, {}),
        "generation_introduced": pokemon.generation_introduced,
        "height_dm": pokemon.height_dm,
        "weight_hg": pokemon.weight_hg,
        "genus_zh": pokemon.genus_zh,
        "genus_en": pokemon.genus_en,
        "flavor_zh": pokemon.flavor_zh,
        "flavor_en": pokemon.flavor_en,
        "flavor_zh_source": pokemon.flavor_zh_source,
        "genus_zh_source": pokemon.genus_zh_source,
        "artwork_path": pokemon.artwork_path,
        "artwork_url_remote": pokemon.artwork_url,
        "sprite_url": pokemon.sprite_url,
        "sprite_path": pokemon.sprite_path,
        "is_legendary": pokemon.is_legendary,
        "is_mythical": pokemon.is_mythical,
        "is_baby": pokemon.is_baby,
        "gender_rate": pokemon.gender_rate,
        "capture_rate": pokemon.capture_rate,
        "base_happiness": pokemon.base_happiness,
        "hatch_counter": pokemon.hatch_counter,
        "growth_rate": pokemon.growth_rate,
        "habitat": pokemon.habitat,
        "color": pokemon.color,
        "shape": pokemon.shape,
        "egg_groups": safe_loads(pokemon.egg_groups_json, []),
        "source": pokemon.source,
        "is_demo": pokemon.is_demo,
        "synced_at": pokemon.synced_at.isoformat() if pokemon.synced_at else None,
    }


# ---------------------------------------------------------------------------
# 特性（ability 参考表）
# ---------------------------------------------------------------------------


async def list_abilities(
    session: AsyncSession,
    *,
    search: str | None = None,
    tier: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Ability], int]:
    """特性列表：搜索（中/英文名、说明）、按 S 级筛选、分页。

    排序：S 级在前，其次按中文名；分页在排序之后执行。
    """
    stmt = select(Ability)
    if search:
        raw = search.strip()
        keyword = f"%{raw.lower()}%"
        stmt = stmt.where(
            func.lower(Ability.name).like(keyword)
            | func.ifnull(Ability.zh, "").like(keyword)
            | func.ifnull(Ability.effect_zh, "").like(keyword)
        )
    if tier in ("s", "normal"):
        stmt = stmt.where(Ability.tier == tier)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    page = max(1, page)
    page_size = max(1, min(200, page_size))
    stmt = (
        stmt.order_by(
            # 's' < 'normal' 按字符串排序不成立，用 case 显式置顶
            case((Ability.tier == "s", 0), else_=1),
            func.ifnull(Ability.zh, Ability.name).asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


async def get_ability(session: AsyncSession, name: str) -> Ability | None:
    return (await session.execute(select(Ability).where(Ability.name == name))).scalar_one_or_none()


async def get_ability_holders(session: AsyncSession, name: str) -> list[Pokemon]:
    """拥有某特性的宝可梦（按图鉴编号），通过 abilities_json 的设备名匹配。

    与列表筛选同样的约定：ability name 是纯小写 kebab-case，`"name"` 不会误命中子串。
    """
    stmt = (
        select(Pokemon)
        .where(Pokemon.abilities_json.like(f'%"{name}"%'))
        .order_by(Pokemon.dex_number.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_ability_tier_map(session: AsyncSession) -> dict[str, str]:
    """特性名 → 评级（'s' / 'normal'）。图鉴接口为特性附 S 级标记用。"""
    rows = (await session.execute(select(Ability.name, Ability.tier))).all()
    return {name: tier for name, tier in rows}


async def get_s_tier_names(session: AsyncSession) -> list[str]:
    """当前全部 S 级特性名（供图鉴页做高亮）。"""
    stmt = select(Ability.name).where(Ability.tier == "s").order_by(Ability.name)
    rows = (await session.execute(stmt)).all()
    return [name for (name,) in rows]


async def update_ability_rating(
    session: AsyncSession, ability: Ability, *, tier: str, note: str | None
) -> Ability:
    """人工修改评级：置为 manual，之后的自动评级不再覆盖。"""
    ability.tier = tier
    ability.rating_note = note
    ability.rating_source = "manual"
    await session.flush()
    return ability
