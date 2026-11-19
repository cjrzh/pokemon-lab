"""双打队伍配置的合法性规则（纯函数，便于单测）。

规则边界（如实声明，不做超出数据的推断）：
  - **编号唯一**：同一队伍里 `dex_number` 不能重复（同一图鉴编号的不同形态也算重复）。
  - **道具唯一**：同一队伍里非空道具不能重复（宝可梦系列规则：携带道具不可重复）。
  - **招式合法**：招式必须在该格式对应的版本组里能学会（数据来自 `pokemon.moves_json`）。
  - **特性合法**：特性必须属于该宝可梦（或所选形态）的 `abilities_json`。
  - **配点边界**：EV 单项 0–252、合计 ≤508；Champions 能力点单项 0–32、合计 ≤66。
    IV 0–31（Champions 没有 IV）。
  - **超极巨化**：只有剑盾格式、且该物种 / 形态确实有 G 形态时才能开启。

不做的事：不校验道具是否在本地道具表里（道具表只覆盖双打统计出现的道具，
拿它当白名单会误杀），只做「非空且重复」的检查。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.smogon_stats import showdown_slug

#: 双打格式 → PokéAPI 版本组（招式 / 特性的合法范围）。
FORMAT_VERSION_GROUP: dict[str, str] = {
    "bdsp": "brilliant-diamond-shining-pearl",
    "swsh": "sword-shield",
    "sv": "scarlet-violet",
    "champions": "champions",
}

#: 每个格式的配点上限。
EV_MAX = 252
EV_TOTAL_MAX = 508
POINT_MAX = 32
POINT_TOTAL_MAX = 66

TEAM_SIZE = 6
STAT_COUNT = 6


@dataclass
class MemberIssue:
    """一条配置问题。`field` 供前端定位到具体输入框。"""

    field: str
    message: str


@dataclass
class TeamValidation:
    """整队校验结果。`ok` 为真时 issues 为空。"""

    issues: list[MemberIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def add(self, field_name: str, message: str) -> None:
        self.issues.append(MemberIssue(field=field_name, message=message))


def points_limits(points_kind: str) -> tuple[int, int]:
    """返回（单项上限, 合计上限）。"""
    if points_kind == "stat_points":
        return POINT_MAX, POINT_TOTAL_MAX
    return EV_MAX, EV_TOTAL_MAX


def validate_points(
    values: list[int],
    points_kind: str,
    *,
    field_prefix: str,
    result: TeamValidation,
) -> None:
    """校验一项配点（EV 或能力点）。"""
    single_max, total_max = points_limits(points_kind)
    label = "能力点" if points_kind == "stat_points" else "EV"

    if len(values) != STAT_COUNT:
        result.add(field_prefix, f"{label}应为 {STAT_COUNT} 项")
        return
    for index, value in enumerate(values):
        if value < 0 or value > single_max:
            result.add(f"{field_prefix}.{index}", f"{label}单项应在 0–{single_max} 之间")
    if sum(values) > total_max:
        result.add(field_prefix, f"{label}合计不能超过 {total_max}（当前 {sum(values)}）")


def validate_ivs(values: list[int] | None, *, field_prefix: str, result: TeamValidation) -> None:
    if values is None:
        return
    if len(values) != STAT_COUNT:
        result.add(field_prefix, f"个体值应为 {STAT_COUNT} 项")
        return
    for index, value in enumerate(values):
        if value < 0 or value > 31:
            result.add(f"{field_prefix}.{index}", "个体值应在 0–31 之间")


# ---------------------------------------------------------------------------
# 批量修改（闪光 / 等级 / 性别）
# ---------------------------------------------------------------------------


def allowed_genders(gender_rate: int | None) -> set[str]:
    """该宝可梦允许的性别集合。

    `gender_rate` 沿用 PokéAPI 口径：-1 无性别（如超梦、小磁怪），
    0 只有雄性（如尼多朗、肯泰罗），8 只有雌性（如尼多兰），其余为雌雄都有。
    数据缺失（None）时不限制，交给调用方自行判断。
    """
    if gender_rate is None:
        return {"M", "F"}
    if gender_rate == -1:
        return set()  # 无性别：不能带性别标记
    if gender_rate == 0:
        return {"M"}
    if gender_rate == 8:
        return {"F"}
    return {"M", "F"}


def batch_shiny(members: list[dict], shiny: bool) -> tuple[list[dict], list[str]]:
    """批量改闪光。返回（新成员列表, 跳过说明）。

    闪光对任何宝可梦都合法，这里不筛；保留接口形状是为了三个批量操作一致。
    """
    return [dict(member, shiny=shiny) for member in members], []


def batch_level(
    members: list[dict], level: int | None
) -> tuple[list[dict], list[str]]:
    """批量改等级（None 表示恢复「按格式默认」）。等级 1–100 都合法。"""
    if level is not None and not (1 <= level <= 100):
        raise ValueError("等级应在 1–100 之间")
    return [dict(member, level=level) for member in members], []


def batch_gender(
    members: list[dict], gender: str | None, gender_rates: dict[int, int | None]
) -> tuple[list[dict], list[str]]:
    """批量改性别。**不合法的保持不变**，并在跳过说明里列出原因。

    性别不是玩家自由选择的：尼多朗只能雄性、尼多兰只能雌性、超梦等无性别的
    宝可梦不能带性别标记。这类成员原样保留，而不是被改成非法值。
    """
    if gender is not None and gender not in ("M", "F"):
        raise ValueError("性别只能是 M / F / null")

    updated: list[dict] = []
    skipped: list[str] = []
    for member in members:
        dex = member.get("dex_number")
        rate = gender_rates.get(dex)
        allowed = allowed_genders(rate)
        label = f"#{dex} {member.get('showdown_name') or ''}".strip()

        if gender is None:
            # 恢复「不指定」：无性别的宝可梦本来就是不指定，不必提示
            updated.append(dict(member, gender=None))
        elif not allowed:
            skipped.append(f"{label} 没有性别，保持原样")
            updated.append(member)
        elif gender not in allowed:
            only = "雌性" if allowed == {"F"} else "雄性"
            skipped.append(f"{label} 只能为{only}，保持原样")
            updated.append(member)
        else:
            updated.append(dict(member, gender=gender))

    return updated, skipped


def validate_gigantamax(
    members: list[dict],
    *,
    format_key: str | None,
    allowed: set[str] | None,
) -> list[MemberIssue]:
    """超极巨化配置的合法性（纯函数）。

    规则（与 Showdown 一致）：
      - 只有剑盾（`swsh`）能超极巨化；
      - 只有带 G 形态的物种 / 形态可以开启（`allowed` 是这些 Showdown 名的 slug）。

    `allowed` 为 None 时不检查物种（调用方没有清单数据时如实降级，不把
    「不知道」当成「不合法」）；`format_key` 为 None 时同样跳过格式检查。
    """
    issues: list[MemberIssue] = []
    for index, member in enumerate(members):
        if not member.get("gigantamax"):
            continue
        prefix = f"members.{index}"
        if format_key is not None and format_key != "swsh":
            issues.append(
                MemberIssue(f"{prefix}.gigantamax", "只有剑盾格式支持超极巨化")
            )
            continue
        if allowed is not None:
            slug = showdown_slug(member.get("showdown_name") or "")
            if slug.endswith("-gmax"):
                slug = slug[: -len("-gmax")]
            if slug not in allowed:
                name = member.get("showdown_name") or f"#{member.get('dex_number')}"
                issues.append(
                    MemberIssue(f"{prefix}.gigantamax", f"{name} 没有超极巨化形态")
                )
    return issues


def validate_team(
    members: list[dict],
    *,
    points_kind: str,
    legal_moves: dict[int, set[str]],
    legal_abilities: dict[int, set[str]],
    moves_known: bool = True,
    format_key: str | None = None,
    gmax_allowed: set[str] | None = None,
) -> TeamValidation:
    """整队校验。

    Args:
        members: 每只的配置 dict，字段见 `TeamMemberInput`。
        points_kind: `ev` 或 `stat_points`。
        legal_moves: 编号 → 该格式可学的招式集合（数据缺失时传空集合并置 `moves_known=False`）。
        legal_abilities: 编号 → 可用特性集合。
        moves_known: 为 False 时不校验招式合法性（本地没有招式数据时如实降级，
            而不是把「不知道」当成「不合法」）。
        format_key: 队伍所在格式；用于「只有剑盾支持超极巨化」的判断。
        gmax_allowed: 能开启超极巨化的 Showdown 名（slug）；None 表示不校验物种。
    """
    result = TeamValidation()

    if len(members) == 0:
        result.add("team", "队伍至少要有一只宝可梦")
    if len(members) > TEAM_SIZE:
        result.add("team", f"队伍最多 {TEAM_SIZE} 只宝可梦")

    seen_dex: dict[int, int] = {}
    seen_items: dict[str, int] = {}

    for index, member in enumerate(members):
        prefix = f"members.{index}"
        dex = member.get("dex_number")

        if dex in seen_dex:
            first = seen_dex[dex] + 1
            result.add(
                f"{prefix}.dex_number",
                f"与第 {first} 只重复：同一编号不能上两次",
            )
        else:
            seen_dex[dex] = index

        item = (member.get("item") or "").strip()
        if item:
            if item in seen_items:
                result.add(f"{prefix}.item", f"与第 {seen_items[item] + 1} 只携带了相同道具")
            else:
                seen_items[item] = index

        # 约定：`ability` / `moves` 里存的是 Showdown 显示名（如 `Blaze`、`Flamethrower`），
        # 本地数据用 slug（`blaze`、`flamethrower`）。比较前统一归一化，避免大小写与
        # 空格差异把合法配置误判为非法。
        ability = (member.get("ability") or "").strip()
        allowed_abilities = legal_abilities.get(dex)
        if ability and allowed_abilities:
            # Showdown 把复合特性写成 `As One (Glastrier)`，本地是 `as-one-glastrier`；
            # 去掉括号部分再比一次，避免把合法配置判成非法。
            candidates = {showdown_slug(item) for item in allowed_abilities}
            variants = {
                showdown_slug(ability),
                showdown_slug(re.sub(r"\([^)]*\)", "", ability)),
                showdown_slug(re.sub(r"\s*\(([^)]*)\)", r"-\1", ability)),
            }
            # 反过来也成立：队表里常写简名 `As One`，本地只有 `as-one-glastrier`
            # 这类带形态后缀的完整名；允许「简名是完整名的前缀」。
            if not variants & candidates and not any(
                candidate.startswith(f"{variant}-")
                for variant in variants
                for candidate in candidates
            ):
                result.add(f"{prefix}.ability", f"{ability} 不是该宝可梦可用的特性")

        moves = [move for move in (member.get("moves") or []) if move]
        if len(moves) > 4:
            result.add(f"{prefix}.moves", "最多 4 个招式")
        allowed_moves = legal_moves.get(dex)
        if moves_known and allowed_moves is not None:
            allowed_slugs = {showdown_slug(item) for item in allowed_moves}
            for move in moves:
                if showdown_slug(move) not in allowed_slugs:
                    result.add(f"{prefix}.moves", f"{move} 在该版本无法学会")

        evs = member.get("evs")
        if evs is not None:
            validate_points(evs, points_kind, field_prefix=f"{prefix}.evs", result=result)
        validate_ivs(member.get("ivs"), field_prefix=f"{prefix}.ivs", result=result)

    result.issues.extend(
        validate_gigantamax(members, format_key=format_key, allowed=gmax_allowed)
    )
    return result

    return result
