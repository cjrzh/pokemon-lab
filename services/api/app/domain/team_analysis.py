"""队伍打击面 / 缺失面分析（纯函数，不读文件、不做 IO）。

回答三个问题：
  1. **打击面**：队伍能打出 2× 及以上的进攻属性有哪些，各能克制多少种对手属性组合；
  2. **缺失面**（盲点）：哪些防守属性完全没有被任何队员的进攻属性克制（= 打不动）；
  3. **共同弱点**：队伍有多少只被同一个进攻属性 2× 及以上克制（速度堆叠的隐患）。

属性的合法性来自克制表本身；本模块不校验队伍配置是否合法（那是 team_rules 的事）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.type_engine import TypeChart, evaluate

#: 判定为「打得动」的最低倍率。
SEVERITY = 2.0


@dataclass
class AttackCoverage:
    """一个进攻属性的覆盖情况。"""

    type: str
    #: 能打出 2× 及以上的防守属性（单属性视角）。
    hits: list[str] = field(default_factory=list)
    #: 队伍里有多少只带这个属性（用于排序，先看主属性）。
    member_count: int = 0


@dataclass
class WeaknessHotspot:
    """一个共同弱点。"""

    type: str
    #: 被它 2× 及以上克制的成员编号。
    members: list[int] = field(default_factory=list)


@dataclass
class TeamCoverage:
    """整队分析结果。"""

    attack: list[AttackCoverage] = field(default_factory=list)
    #: 没有任何队员能 2× 打到的防守属性（按克制表顺序）。
    gaps: list[str] = field(default_factory=list)
    #: 被 2 只以上队员共同害怕的属性（按人数降序）。
    hotspots: list[WeaknessHotspot] = field(default_factory=list)


def analyze_team(
    members: Sequence[dict], chart: TypeChart
) -> TeamCoverage:
    """分析队伍。

    Args:
        members: 每只含 `dex_number` 与 `types`（属性列表）的 dict。
        chart: 规范克制表（attack → {defense: 倍率}）。

    设计取舍：只按**属性**判断，不按具体招式。队伍配置里虽然记了招式，
    但本地没有完整的招式属性映射时（如导入的 Showdown 代码里只有英文名），
    用属性近似比编造数据更诚实 —— 页面会把口径写在说明里。
    """
    defense_types = sorted({defense for row in chart.values() for defense in row})

    # ---------- 进攻：每个队伍属性打谁疼 ----------
    attacking_types: dict[str, int] = {}
    for member in members:
        for member_type in member.get("types") or []:
            attacking_types[member_type] = attacking_types.get(member_type, 0) + 1

    attack: list[AttackCoverage] = []
    covered: set[str] = set()
    for attack_type, count in attacking_types.items():
        try:
            hits = [
                defense
                for defense in defense_types
                if evaluate(attack_type, [defense], chart) >= SEVERITY
            ]
        except KeyError:
            # 克制表里没有这个属性（脏数据）——跳过，不猜
            continue
        if hits:
            attack.append(AttackCoverage(type=attack_type, hits=hits, member_count=count))
            covered.update(hits)

    # 先按「能打到的属性数量」降序，再按队伍里出现次数降序，最后按属性名稳定排序
    attack.sort(key=lambda item: (-len(item.hits), -item.member_count, item.type))
    gaps = [defense for defense in defense_types if defense not in covered]

    # ---------- 防御：谁的弱点被队友放大 ----------
    hotspots: list[WeaknessHotspot] = []
    for attack_type in chart:
        weak_members: list[int] = []
        for member in members:
            types = member.get("types") or []
            if not types:
                continue
            multiplier = evaluate(attack_type, types, chart)
            if multiplier >= SEVERITY:
                weak_members.append(member["dex_number"])
        if len(weak_members) >= 2:
            hotspots.append(WeaknessHotspot(type=attack_type, members=weak_members))
    hotspots.sort(key=lambda item: (-len(item.members), item.type))

    return TeamCoverage(attack=attack, gaps=gaps, hotspots=hotspots)
