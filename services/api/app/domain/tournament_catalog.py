"""官方赛事（VGC）的来源、规则映射与展示标签（纯数据，不含 IO 逻辑）。

数据源：Limitless VGC（https://limitlessvgc.com）—— 官方赛事（地区赛 / 国际赛 /
世锦赛 / 特殊赛事 / 国家赛 / Players Cup）的成绩与队伍表都收录在这里。
`robots.txt` 为全站允许抓取；本项目按需同步、控制并发、只抓公开页面。

与「历史使用率」的关系：
  - Smogon 统计的是 **天梯** 使用率；
  - 这里统计的是 **官方赛事** 的实际参赛队伍（队表 → 使用率），
    两者口径不同，页面上分开呈现，不混为一谈。

规则（format）→ 建队格式（format_key）的映射：
  项目只提供 BDSP / 剑盾 / 朱紫 / 冠军 四个版本的双打建队。官方赛事的大部分
  规则都能落到这四个版本里；第三世代及更早、以及日月没有建队入口的规则如实标为
  `legacy`（可查看队表，但不能一键建队）。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 页面来源（展示「数据来自」与拼接链接用）。
SOURCE_NAME = "Limitless VGC"
SOURCE_ROOT = "https://limitlessvgc.com"
SOURCE_NOTE = "官方赛事成绩与队表来自 Limitless VGC（社区维护的 VGC 赛事数据库）"

#: 请求头：标明来源，便于对方识别流量。
USER_AGENT = "pokemon-lab/0.1 (personal project; official VGC results sync)"


@dataclass(frozen=True)
class TournamentRuleset:
    """Limitless 的规则标识（赛事列表里的 `data-format`）与展示文案。"""

    identifier: str
    #: 展示名（中文优先）
    label: str
    #: 所属世代 / 版本
    game: str
    #: 可建队的格式 key（bdsp / swsh / sv / champions）；无对应时为 None
    format_key: str | None = None


#: 规则目录：新规则在前。`format_key` 表示「能用本地数据建队」的版本。
RULESETS: tuple[TournamentRuleset, ...] = (
    TournamentRuleset("m-c", "宝可梦冠军 Reg M-C（官方赛事）", "宝可梦冠军", "champions"),
    TournamentRuleset("m-b", "宝可梦冠军 Reg M-B", "宝可梦冠军", "champions"),
    TournamentRuleset("m-a", "宝可梦冠军 Reg M-A", "宝可梦冠军", "champions"),
    TournamentRuleset("svi", "朱紫 Reg I", "朱紫", "sv"),
    TournamentRuleset("svh", "朱紫 Reg H", "朱紫", "sv"),
    TournamentRuleset("svg", "朱紫 Reg G", "朱紫", "sv"),
    TournamentRuleset("svf", "朱紫 Reg F", "朱紫", "sv"),
    TournamentRuleset("sve", "朱紫 Reg E", "朱紫", "sv"),
    TournamentRuleset("svd", "朱紫 Reg D", "朱紫", "sv"),
    TournamentRuleset("svc", "朱紫 Reg C", "朱紫", "sv"),
    TournamentRuleset("svb", "朱紫 Reg B", "朱紫", "sv"),
    TournamentRuleset("sva", "朱紫 Reg A", "朱紫", "sv"),
    TournamentRuleset("vgc22", "剑盾 Series 12", "剑盾", "swsh"),
    TournamentRuleset("swsh9", "剑盾 Series 9", "剑盾", "swsh"),
    TournamentRuleset("swsh8", "剑盾 Series 8", "剑盾", "swsh"),
    TournamentRuleset("swsh7", "剑盾 Series 7", "剑盾", "swsh"),
    TournamentRuleset("swsh5", "剑盾 Series 5", "剑盾", "swsh"),
    TournamentRuleset("swsh3", "剑盾 Series 3", "剑盾", "swsh"),
    TournamentRuleset("swsh2", "剑盾 Series 2", "剑盾", "swsh"),
    # 日月：本地没有建队格式，只能看队表与使用率
    TournamentRuleset("ultra", "究极日月 Ultra Series", "究极日月"),
    TournamentRuleset("moon", "日月 Moon Series", "日月"),
    TournamentRuleset("sun", "日月 Sun Series", "日月", "bdsp"),
    TournamentRuleset("vgc18", "VGC 2018", "日月"),
    TournamentRuleset("vgc17", "VGC 2017", "日月"),
    TournamentRuleset("vgc16", "VGC 2016", "ORAS"),
    TournamentRuleset("vgc15", "VGC 2015", "ORAS"),
    TournamentRuleset("vgc14", "VGC 2014", "XY"),
    # 更早的赛事只有成绩，队表几乎缺失
    TournamentRuleset("vgc13", "VGC 2013", "黑2白2"),
    TournamentRuleset("vgc12", "VGC 2012", "黑2白2"),
    TournamentRuleset("vgc11", "VGC 2011", "黑2白2"),
    TournamentRuleset("vgc10", "VGC 2010", "第四世代"),
)

RULESET_BY_ID = {item.identifier: item for item in RULESETS}

#: 赛事类型（来自列表页的 `type=` 筛选项）。
EVENT_TYPES: dict[str, str] = {
    "regional": "地区赛",
    "international": "国际赛",
    "worlds": "世界锦标赛",
    "special": "特殊赛事",
    "national": "国家赛",
    "players_cup": "Players Cup",
}

#: 同步时按类型抓列表（Limitless 的列表页一次最多 100 条，需要翻页）。
SYNC_TYPES: tuple[str, ...] = tuple(EVENT_TYPES)

#: 从赛事名推断类型的兜底规则（列表页给了 type 筛选，正常不需要；用于直接按 id 抓取时）。
_NAME_TYPE_HINTS: tuple[tuple[str, str], ...] = (
    ("national championship", "national"),
    ("players cup", "players_cup"),
    ("world championship", "worlds"),
    ("international championship", "international"),
    ("regional", "regional"),
)


def ruleset_label(identifier: str | None) -> str:
    """规则展示名；目录里没有时原样返回（不猜译）。"""
    if not identifier:
        return "未知规则"
    item = RULESET_BY_ID.get(identifier)
    return item.label if item else identifier


def format_key_for(identifier: str | None) -> str | None:
    """该规则能否用本地数据建队；不能时返回 None。"""
    if not identifier:
        return None
    item = RULESET_BY_ID.get(identifier)
    return item.format_key if item else None


def event_type_label(kind: str | None) -> str:
    if not kind:
        return "其他"
    return EVENT_TYPES.get(kind, kind)


def infer_event_type(name: str) -> str | None:
    """从赛事名推断类型（兜底，列表页的 `type` 筛选项更权威）。"""
    lowered = name.lower()
    for hint, kind in _NAME_TYPE_HINTS:
        if hint in lowered:
            return kind
    return None


def tournament_url(tournament_id: int, page: str = "") -> str:
    """赛事页面地址；`page` 为 "" / "teams" / "statistics"。"""
    suffix = f"/{page}" if page else ""
    return f"{SOURCE_ROOT}/tournaments/{tournament_id}{suffix}"


def list_url(event_type: str, page: int, *, show: int = 100) -> str:
    return (
        f"{SOURCE_ROOT}/tournaments?time=all&show={show}"
        f"&type={event_type}&page={page}"
    )


def team_url(team_id: int) -> str:
    return f"{SOURCE_ROOT}/teams/{team_id}"
