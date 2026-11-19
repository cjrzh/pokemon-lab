"""Showdown 队伍文本解析（纯函数：文本 → 结构化配置，不访问网络 / 数据库）。

输入是从 Pokémon Showdown 或交换机器人复制来的队伍文本，输出每只宝可梦的字段。
**不解析物种名到图鉴编号** —— 那需要查库，是服务层的职责；这里只管文本。

支持并保留的字段（Showdown 导出格式，以及常见的手写变体）：

    Nickname (Species) (M) @ Item
    Ability: Blaze
    Level: 50
    Shiny: Yes
    Dynamax Level: 10
    Gigantamax: Yes
    Tera Type: Fire
    EVs: 252 SpA / 4 SpD / 252 Spe
    IVs: 0 Atk
    Timid Nature
    - Flamethrower

也兼容把超极巨化写在物种名前的写法（Limitless 赛事队表：`Gigantamax Charizard`、
中文社区的 `超极巨化 喷火龙`）。解析时剥掉前缀并标记为超极巨化，物种名仍是
`Charizard` / `喷火龙`，这样才查得到图鉴编号。

容错原则：
  - 认不出的**整只**跳过并记入 `problems`，不猜一个配置出来；
  - 认不出的**单行**忽略（`Happiness` / `Pokeball` 等字段不影响对战配置）；
  - 缺省值按 Showdown 自身的约定：IV 全 31、不闪光、等级留空（由格式决定）、
    极巨化等级 10、不超极巨化。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STAT_COUNT = 6

#: 支持的导出语言标记（与 `schemas/teams.py` 的 LANGUAGES 一致）。
#: 这里独立写一份而不是 import，是为了让解析器保持「纯文本、零依赖」。
LANGUAGES = ("CHS", "CHT", "ENG", "JPN", "KOR", "FRA", "GER", "ITA", "ESP")

#: 六项顺序（与游戏一致）：HP / 攻击 / 防御 / 特攻 / 特防 / 速度。
STAT_KEYS = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")

#: Showdown 的配点短名 → 索引。`SpD` 是特防、`Spe` 是速度，别写反。
_STAT_INDEX = {
    "hp": 0,
    "atk": 1,
    "attack": 1,
    "def": 2,
    "defense": 2,
    "defence": 2,
    "spa": 3,
    "spatk": 3,
    "specialattack": 3,
    "special-attack": 3,
    "spd": 4,
    "spdef": 4,
    "specialdefense": 4,
    "special-defense": 4,
    "spe": 5,
    "speed": 5,
}

#: 性格 slug → Showdown 英文名。导出与导入共用这一张表（单一真相来源）。
NATURE_EN: dict[str, str] = {
    "hardy": "Hardy",
    "lonely": "Lonely",
    "brave": "Brave",
    "adamant": "Adamant",
    "naughty": "Naughty",
    "bold": "Bold",
    "docile": "Docile",
    "relaxed": "Relaxed",
    "impish": "Impish",
    "lax": "Lax",
    "timid": "Timid",
    "hasty": "Hasty",
    "serious": "Serious",
    "jolly": "Jolly",
    "naive": "Naive",
    "modest": "Modest",
    "mild": "Mild",
    "quiet": "Quiet",
    "bashful": "Bashful",
    "rash": "Rash",
    "calm": "Calm",
    "gentle": "Gentle",
    "sassy": "Sassy",
    "careful": "Careful",
    "quirky": "Quirky",
}

#: Showdown 英文名（小写）→ 性格 slug，导入时反向查表。
NATURE_SLUG: dict[str, str] = {en.lower(): slug for slug, en in NATURE_EN.items()}

#: 队伍文本里需要忽略的行：交易前缀、Showdown 的标题行。
_IGNORED_LINE = re.compile(r"^\s*(!trade\w*|={2,}.*={2,})\s*$", re.IGNORECASE)
#: 形如 `Level: 50` / `Ability: Blaze` 的字段行。
_FIELD_LINE = re.compile(r"^([A-Za-z][A-Za-z ]*):\s*(.*)$")
#: 招式行。
_MOVE_LINE = re.compile(r"^[-–—]\s*(.+)$")
#: 配点行里的一项：`252 SpA`。
_POINT_ITEM = re.compile(r"^(\d+)\s+([A-Za-z-]+)$")
#: 头行末尾的括号组：`(M)`、`(Charizard)`。
_TRAILING_GROUP = re.compile(r"\(([^()]*)\)\s*$")
#: 头行的超极巨化前缀：`Gigantamax Charizard` / `超极巨化 喷火龙`。
_GMAX_PREFIX = re.compile(r"^(?:gigantamax|g-max|gmax|超极巨化)\s+", re.IGNORECASE)


@dataclass
class ParsedSet:
    """一只宝可梦的解析结果（物种名仍是文本，尚未映射编号）。"""

    species: str
    nickname: str | None = None
    gender: str | None = None
    item: str | None = None
    ability: str | None = None
    level: int | None = None
    #: 极巨化等级 0–10（剑盾）；没写时按 Showdown 默认值 10 处理
    dynamax_level: int | None = None
    #: 超极巨化（剑盾）：`Gigantamax: Yes` → True
    gigantamax: bool = False
    shiny: bool = False
    nature: str | None = None
    evs: list[int] = field(default_factory=lambda: [0] * STAT_COUNT)
    ivs: list[int] | None = None
    moves: list[str] = field(default_factory=list)
    tera_type: str | None = None
    #: 导出语言标记（CHS / ENG …）；缺省时由上层按 CHS 处理。
    language: str | None = None


@dataclass
class ParseResult:
    """整段文本的解析结果。`problems` 是跳过原因，按出现顺序。"""

    sets: list[ParsedSet] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def split_sets(text: str) -> list[list[str]]:
    """按空行切分队伍文本，去掉交易前缀与标题行，返回每个块的非空行。"""
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        if _IGNORED_LINE.match(line):
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _is_ascii_word(text: str) -> bool:
    """是否只含 ASCII 可打印字符（用于识别「英文名 + 中文括号」的写法）。"""
    stripped = text.strip()
    return bool(stripped) and all(ord(char) < 0x80 for char in stripped)


def parse_head(line: str) -> tuple[str, str | None, str | None, str | None]:
    """解析头行 → (物种名, 昵称, 性别, 道具)。

    Showdown 的写法是 `[昵称 (]物种[)] [(M|F)] [@ 道具]`：
    末尾的括号组从右往左剥，`(M)` / `(F)` 是性别，剩下的是物种（此时前面是昵称）。
    头行不像名字（如以 `@` / `-` 开头，或只剩道具）时物种名为空串。
    """
    head, _, item = line.partition(" @ ")
    head = head.strip()
    item = item.strip() or None

    trailing: list[str] = []
    while True:
        match = _TRAILING_GROUP.search(head)
        if match is None:
            break
        trailing.insert(0, match.group(1).strip())
        head = head[: match.start()].strip()

    gender: str | None = None
    if trailing and trailing[-1].upper() in ("M", "F"):
        gender = trailing.pop().upper()

    if trailing:
        # 还有括号组 → 它是物种名，`head` 是昵称
        species = trailing[-1]
        nickname = head or None
        # 中文玩家常把英文物种名写在前面、中文名放括号里：
        # `Charizard (喷火龙)`。Showdown 的官方写法是 `昵称 (物种)`，照字面
        # 解析会把「喷火龙」当物种（无法识别）。这里按字符判断并对调：
        # 前半是纯英文、括号里是中文 → 前半才是物种。
        if _is_ascii_word(head) and any(ord(char) > 0x7F for char in species):
            species, nickname = head, species
    else:
        species = head
        nickname = None

    # `@ Life Orb` / `- Heat Wave` 这类行会被当作头行；它们不是宝可梦名，
    # 返回空物种名让调用方跳过整块，而不是造出一只叫「@ Life Orb」的宝可梦。
    # 合法的物种名不会以这些符号开头（宝可梦名不含 `@ - # |`）。
    if not species or species[0] in "@-–—#|":
        return "", None, gender, item
    return species, nickname, gender, item


def parse_points(text: str, *, default: int = 0) -> tuple[list[int], list[str]]:
    """解析 `252 SpA / 4 SpD / 252 Spe` → 六项数组与认不出的项。

    `default` 是没写到的项取值：EV 用 0，IV 用 31（Showdown 只列非 31 的项）。
    显式写了 `0 Atk` 的项必须是 0，所以只能用 `default` 初始化、不能用 0 反推。
    """
    values = [default] * STAT_COUNT
    bad: list[str] = []
    for chunk in text.split("/"):
        part = chunk.strip()
        if not part:
            continue
        match = _POINT_ITEM.match(part)
        if match is None:
            bad.append(part)
            continue
        key = match.group(2).lower().replace(" ", "")
        index = _STAT_INDEX.get(key)
        if index is None:
            bad.append(part)
            continue
        values[index] = int(match.group(1))
    return values, bad


def _parse_bool(text: str) -> bool:
    return text.strip().lower() in ("yes", "true", "1", "y")


def parse_set(lines: list[str]) -> ParsedSet | None:
    """解析一个块；头行无法识别时返回 None。"""
    species, nickname, gender, item = parse_head(lines[0])
    if not species:
        return None

    # `Gigantamax Charizard` 这类写法：剥掉前缀，物种名保持不变并标记超极巨化。
    gmax_match = _GMAX_PREFIX.match(species)
    prefix_gmax = gmax_match is not None
    if gmax_match:
        species = species[gmax_match.end():].strip()
        if not species:
            return None

    parsed = ParsedSet(
        species=species,
        nickname=nickname,
        gender=gender,
        item=item,
        gigantamax=prefix_gmax,
    )
    ivs_seen = False

    for line in lines[1:]:
        move = _MOVE_LINE.match(line)
        if move:
            parsed.moves.append(move.group(1).strip())
            continue

        field_match = _FIELD_LINE.match(line)
        if field_match:
            key = field_match.group(1).strip().lower()
            value = field_match.group(2).strip()
            if key == "ability":
                parsed.ability = value or None
            elif key == "level":
                parsed.level = int(value) if value.isdigit() else None
            elif key == "dynamax level":
                # 剑盾极巨化等级 0–10；超出范围视为无效，按默认值（10）处理
                if value.isdigit() and 0 <= int(value) <= 10:
                    parsed.dynamax_level = int(value)
            elif key == "gigantamax":
                # Showdown 只写 `Gigantamax: Yes`；`No` 等同于不写
                parsed.gigantamax = _parse_bool(value)
            elif key == "shiny":
                parsed.shiny = _parse_bool(value)
            elif key == "tera type":
                parsed.tera_type = value.title() or None
            elif key == "language":
                # 只接受已知标记，其余忽略（避免脏值进数据库）
                code = value.strip().upper()
                if code in LANGUAGES:
                    parsed.language = code
            elif key == "evs":
                parsed.evs, _ = parse_points(value)
            elif key == "ivs":
                # Showdown 只列非 31 的项，没写的按 31
                parsed.ivs, _ = parse_points(value, default=31)
                ivs_seen = True
            # 其余字段（Happiness / Pokeball 等）不影响对战配置，忽略
            continue

        if line.lower().endswith("nature"):
            slug = NATURE_SLUG.get(line[: -len("nature")].strip().lower())
            if slug:
                parsed.nature = slug

    if not ivs_seen:
        parsed.ivs = None
    parsed.moves = parsed.moves[:4]
    return parsed


def parse_showdown(text: str) -> ParseResult:
    """解析整段 Showdown 队伍文本。

    空文本返回空结果（不算错误）；无法解析的块记入 `problems` 并跳过。
    """
    result = ParseResult()
    for index, lines in enumerate(split_sets(text), start=1):
        parsed = parse_set(lines)
        if parsed is None:
            result.problems.append(f"第 {index} 段无法识别：{lines[0][:40]}")
            continue
        result.sets.append(parsed)
    return result
