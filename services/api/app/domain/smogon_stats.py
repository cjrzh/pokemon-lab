"""Smogon 双打使用率数据的纯函数解析与推断。

数据来源（公开统计数据，非游戏客户端数据）：
  https://www.smogon.com/stats/{YYYY-MM}/        使用率总表（.txt）
  https://www.smogon.com/stats/{YYYY-MM}/moveset/ 招式 / 道具 / 配点明细（.txt）

解析目标两类文本：
  1. usage 表：`| 1 | Rillaboom | 46.59939% | ...` → 排名、使用率、对战总数
  2. moveset 块：每个宝可梦一个块，包含 Abilities / Items / Spreads / Moves / Teammates
     （部分旧格式还带 Checks and Counters，其中会出现同一只宝可梦的重复块）

本模块**只做纯计算**：输入文本，输出结构化数据；不访问网络、不读写数据库。
网络抓取在 scripts/fetch_doubles_stats.py，落库在 services/doubles_service.py。

IV 说明：Smogon 的 moveset 文件不包含个体值。`infer_ivs()` 是按配点与招式给出的
**建议值**，界面必须标注「推断」，不能冒充数据源字段。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

#: Smogon moveset 文本里的分隔线。
_SEPARATOR = re.compile(r"^\+-+\+$")
#: 块内的段落标题。出现这些行表示进入下一段。
SECTION_NAMES = (
    "Abilities",
    "Items",
    "Spreads",
    "Moves",
    "Teammates",
    "Tera Types",
    "Checks and Counters",
    "IVs",
    "Happiness",
)
#: 我们关心的段落（Checks / IVs / Happiness 不用于展示）。
_USED_SECTIONS = ("Abilities", "Items", "Spreads", "Moves", "Teammates", "Tera Types")

_USAGE_ROW = re.compile(r"^\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([\d.]+)%")
_BATTLES = re.compile(r"Total battles:\s*(\d+)")
_RAW_COUNT = re.compile(r"^Raw count:\s*(\d+)")
#: 块头下方的统计行。它们不是宝可梦标题，即使被分隔线包住也不能当成新块。
_INFO_LINE = re.compile(r"^(Raw count|Avg\. weight|Viability Ceiling):")
_ENTRY = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?)%$")
_SPREAD = re.compile(r"^([A-Za-z]+):(\d+)/(\d+)/(\d+)/(\d+)/(\d+)/(\d+)\s+(\d+(?:\.\d+)?)%$")
_BLOCK_BODY = re.compile(r"^\|(.*)\|$")

#: 配点/EV 的六项顺序（与游戏一致）：HP / 攻击 / 防御 / 特攻 / 特防 / 速度。
STAT_KEYS = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")

#: 降低攻击的性格（特攻手常用 0 攻个体值，减少混乱与欺诈伤害）。
ATTACK_LOWERING_NATURES = {"modest", "timid", "bold", "calm"}
#: 降低速度的性格（空间队常用 0 速个体值）。
SPEED_LOWERING_NATURES = {"brave", "quiet", "sassy", "relaxed"}


class SmogonParseError(ValueError):
    """文本结构与预期不符（上游格式变化或文件损坏）。"""


@dataclass(frozen=True)
class UsageRow:
    rank: int
    name: str
    usage: float


@dataclass(frozen=True)
class UsageTable:
    battles: int
    rows: tuple[UsageRow, ...]

    @property
    def rank_total(self) -> int:
        return len(self.rows)


@dataclass
class MoveSet:
    """一只宝可梦在一个格式下的统计明细。百分比均为 0–100。"""

    name: str
    raw_count: int = 0
    abilities: list[tuple[str, float]] = field(default_factory=list)
    items: list[tuple[str, float]] = field(default_factory=list)
    moves: list[tuple[str, float]] = field(default_factory=list)
    teammates: list[tuple[str, float]] = field(default_factory=list)
    tera_types: list[tuple[str, float]] = field(default_factory=list)
    spreads: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Spread:
    """一组配点。`points` 在旧世代是 EV（0–252），Champions 是能力点（0–32）。"""

    nature: str
    points: tuple[int, int, int, int, int, int]
    pct: float


def parse_usage_table(text: str) -> UsageTable:
    """解析 usage 总表。表头等无关行忽略。"""
    battles_match = _BATTLES.search(text)
    battles = int(battles_match.group(1)) if battles_match else 0

    rows: list[UsageRow] = []
    for line in text.splitlines():
        match = _USAGE_ROW.match(line)
        if not match:
            continue
        rows.append(
            UsageRow(
                rank=int(match.group(1)),
                name=match.group(2).strip(),
                usage=float(match.group(3)),
            )
        )
    if not rows:
        raise SmogonParseError("usage 表没有任何数据行（格式可能已变化）")
    return UsageTable(battles=battles, rows=tuple(rows))


def _empty_set(name: str) -> MoveSet:
    return MoveSet(name=name)


def parse_moveset_text(text: str) -> dict[str, MoveSet]:
    """解析 moveset 文本，返回 Showdown 名称 → 明细。

    旧格式（BDSP / 剑盾）在「Checks and Counters」后会重复出现同一只宝可梦的块；
    这里按名称合并（逐项取最大百分比、Raw count 取最大），避免重复统计。
    """
    lines = text.splitlines()
    blocks: dict[str, MoveSet] = {}
    current: MoveSet | None = None
    section: str | None = None
    in_checks = False

    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line or _SEPARATOR.match(line):
            continue
        body_match = _BLOCK_BODY.match(line)
        if not body_match:
            continue
        body = body_match.group(1).strip()

        if body in SECTION_NAMES:
            if body == "Checks and Counters":
                # 之后是「被谁克制」的重复块，不参与统计；下一个宝可梦标题会重置
                in_checks = True
                current = None
                section = None
            elif body in _USED_SECTIONS:
                section = body
            continue

        previous = lines[index - 1].strip() if index > 0 else ""
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if (
            _SEPARATOR.match(previous)
            and _SEPARATOR.match(following)
            and not _INFO_LINE.match(body)
        ):
            # 块标题；旧格式的 Checks 区里也有块标题，但同样按名字合并即可
            in_checks = False
            current = blocks.setdefault(body, _empty_set(body))
            section = None
            continue

        if current is None:
            continue

        raw_match = _RAW_COUNT.match(body)
        if raw_match:
            current.raw_count = max(current.raw_count, int(raw_match.group(1)))
            continue

        if section is None or in_checks:
            # 少数文件在 Checks 区用不同段落布局；那里不是主配装，直接跳过
            continue

        if section == "Spreads":
            spread_match = _SPREAD.match(body)
            if spread_match:
                nature = spread_match.group(1).lower()
                points = tuple(int(spread_match.group(i)) for i in range(2, 8))
                pct = float(spread_match.group(8))
                _merge_spread(current, Spread(nature=nature, points=points, pct=pct))
            continue

        entry_match = _ENTRY.match(body)
        if not entry_match:
            continue
        entry_name = entry_match.group(1).strip()
        if not entry_name or entry_name.lower() == "other":
            continue
        pct = float(entry_match.group(2))
        if section == "Abilities":
            _merge_pair(current.abilities, entry_name, pct)
        elif section == "Items":
            _merge_pair(current.items, entry_name, pct)
        elif section == "Moves":
            _merge_pair(current.moves, entry_name, pct)
        elif section == "Teammates":
            _merge_pair(current.teammates, entry_name, pct)
        elif section == "Tera Types":
            _merge_pair(current.tera_types, entry_name, pct)

    # 过滤掉只有标题、没有任何明细的块（例如上游在某些段落里放的非宝可梦行）
    blocks = {
        name: item
        for name, item in blocks.items()
        if item.abilities or item.items or item.moves or item.spreads or item.teammates
    }
    if not blocks:
        raise SmogonParseError("moveset 文件没有任何宝可梦块（格式可能已变化）")

    for item in blocks.values():
        item.abilities.sort(key=lambda pair: (-pair[1], pair[0]))
        item.items.sort(key=lambda pair: (-pair[1], pair[0]))
        item.moves.sort(key=lambda pair: (-pair[1], pair[0]))
        item.teammates.sort(key=lambda pair: (-pair[1], pair[0]))
        item.tera_types.sort(key=lambda pair: (-pair[1], pair[0]))
        item.spreads.sort(key=lambda spread: (-spread["pct"], spread["nature"]))
    return blocks


def _merge_pair(pairs: list[tuple[str, float]], name: str, pct: float) -> None:
    """同名条目取最大百分比（兼容重复块）。"""
    for index, (existing, value) in enumerate(pairs):
        if existing == name:
            if pct > value:
                pairs[index] = (name, pct)
            return
    pairs.append((name, pct))


def _merge_spread(item: MoveSet, spread: Spread) -> None:
    key = (spread.nature, spread.points)
    for index, existing in enumerate(item.spreads):
        if (existing["nature"], tuple(existing["points"])) == key:
            if spread.pct > existing["pct"]:
                item.spreads[index] = _spread_to_dict(spread)
            return
    item.spreads.append(_spread_to_dict(spread))


def _spread_to_dict(spread: Spread) -> dict:
    return {"nature": spread.nature, "points": list(spread.points), "pct": spread.pct}


def showdown_slug(name: str) -> str:
    """Showdown 显示名 → 小写连字符键（与 PokéAPI / 本地库命名接近）。

    例：`Mr. Mime` → `mr-mime`，`Farfetch'd` → `farfetchd`，
    `Will-O-Wisp` → `will-o-wisp`，`Type: Null` → `type-null`。
    """
    text = unicodedata.normalize("NFKD", name)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("’", "'")
    text = re.sub(r"[.'’:]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def load_nature_zh() -> dict[str, str]:
    """25 种性格的官方中文名（PokéAPI zh-hans，生成数据时固化到 labels 文件）。"""
    return {
        "hardy": "勤奋",
        "lonely": "怕寂寞",
        "brave": "勇敢",
        "adamant": "固执",
        "naughty": "顽皮",
        "bold": "大胆",
        "docile": "坦率",
        "relaxed": "悠闲",
        "impish": "淘气",
        "lax": "乐天",
        "timid": "胆小",
        "hasty": "急躁",
        "serious": "认真",
        "jolly": "爽朗",
        "naive": "天真",
        "modest": "内敛",
        "mild": "慢吞吞",
        "quiet": "冷静",
        "bashful": "害羞",
        "rash": "马虎",
        "calm": "温和",
        "gentle": "温顺",
        "sassy": "自大",
        "careful": "慎重",
        "quirky": "浮躁",
    }


def infer_ivs(
    nature: str,
    points: list[int] | tuple[int, ...],
    move_keys: set[str] | list[str],
    *,
    points_kind: str,
) -> dict | None:
    """按配点与招式推断个体值建议。

    这不是数据源字段：Smogon 只统计配点，不统计 IV。规则（保守、可解释）：
      - 降低攻击的性格 + 攻击配点为 0 → 攻击个体值 0（减少混乱自伤与欺诈伤害）；
      - 降低速度的性格 + 速度配点为 0 → 速度个体值 0（空间队抢慢）；
      - 招式含戏法空间且速度配点 ≤ 4 → 速度个体值 0；
      - 其余 31。

    Champions 使用能力点而非 EV/IV，返回 None（界面不展示 IV 建议）。
    """
    if points_kind != "ev" or len(points) != 6:
        return None

    ivs = {key: 31 for key in STAT_KEYS}
    reasons: list[str] = []
    move_set = set(move_keys)

    if nature in ATTACK_LOWERING_NATURES and points[1] == 0:
        ivs["attack"] = 0
        reasons.append("特攻向配置，0 攻可减少混乱自伤与欺诈伤害")
    if nature in SPEED_LOWERING_NATURES and points[5] == 0:
        ivs["speed"] = 0
        reasons.append("减速性格且不投速度，0 速用于空间队抢慢")
    elif "trick-room" in move_set and points[5] <= 4:
        ivs["speed"] = 0
        reasons.append("携带戏法空间且几乎不投速度，0 速更容易先手")

    return {"ivs": ivs, "reasons": reasons, "inferred": True}


def detect_points_kind(spreads: list[dict]) -> str:
    """根据配点范围判断是 EV（0–252）还是 Champions 能力点（0–32）。"""
    values = [point for spread in spreads for point in spread.get("points", [])]
    if not values:
        return "ev"
    return "stat_points" if max(values) <= 32 else "ev"


def format_points(points: list[int] | tuple[int, ...]) -> str:
    """配点 → `252/0/4/0/0/252` 形式的紧凑展示。"""
    return "/".join(str(point) for point in points)
