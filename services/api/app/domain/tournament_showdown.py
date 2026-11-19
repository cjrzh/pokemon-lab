"""官方赛事队表的名称映射与 Showdown 文本生成（纯函数 + 持仓数据，不访问网络）。

职责边界：
  - Limitless 的物种 slug / 显示名 ←→ Showdown 官方名称 / 全国图鉴编号；
  - 道具 → 进化石 → 超级进化形态（如 `Charizardite Y` → `Charizard-Mega-Y`）；
  - 特性显示名（`As One (Glastrier)`）→ 该形态实际可用的特性（`As One`）；
  - 性格显示名 → 性格 slug；太晶属性 → 英文属性名；
  - 超极巨化：**统一写成 `Gigantamax: Yes` 一行**，物种名保留基础形态
    （Showdown / 交换机器人的导出惯例；`Charizard-Gmax` / `Gigantamax Charizard`
    都只是别名，本地不落成物种名）；
  - 固定格式（默认等级 100 / 语言标记 / 是否输出太晶 / 交易前缀）。

数据来源（同步时下载并落库到 `api_cache`，离线时使用仓库内置的兜底表）：
  - `https://play.pokemonshowdown.com/data/pokedex.json`（官方名称 + 编号）
  - `https://play.pokemonshowdown.com/data/items.js`（进化石 → 形态）
  - `https://play.pokemonshowdown.com/data/learnsets.json`（每只可学的招式）

为什么不用本地 `pokemon` / `pokemon_form` 直接映射：
  本地图鉴是 PokéAPI 口径，缺「默认形态没有独立条目」的形态（如 `Indeedee` 只有
  `indeedee-male`），而赛事队表里恰好大量使用默认形态名。Showdown 的名称是社区
  通用口径，也是建队页 / 交换机器人使用的口径 —— 用它做桥梁最稳。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.doubles_formats import FORMAT_BY_KEY
from app.domain.smogon_stats import showdown_slug

#: 属性英文名（太晶属性输出用；展示时由前端翻译）。
TYPE_EN: dict[str, str] = {
    "normal": "Normal",
    "fire": "Fire",
    "water": "Water",
    "electric": "Electric",
    "grass": "Grass",
    "ice": "Ice",
    "fighting": "Fighting",
    "poison": "Poison",
    "ground": "Ground",
    "flying": "Flying",
    "psychic": "Psychic",
    "bug": "Bug",
    "rock": "Rock",
    "ghost": "Ghost",
    "dragon": "Dragon",
    "dark": "Dark",
    "steel": "Steel",
    "fairy": "Fairy",
    "stellar": "Stellar",
}

#: 性格英文名 → slug（与 `showdown_parser.NATURE_EN` 同一套；这里独立一份，
#: 是为了让本模块不依赖解析器，避免循环引用）。
NATURE_SLUG: dict[str, str] = {
    name.lower(): name.lower()
    for name in (
        "Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed",
        "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest",
        "Mild", "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful",
        "Quirky",
    )
}

#: 属性名（Showdown 的 `Tera Type: Fire` 写法是首字母大写）。
_TERA_NORMALIZED: dict[str, str] = {
    slug: label for label, slug in ((label, label.lower()) for label in TYPE_EN.values())
}

#: Limitless 的显示名里常见的「形容词在前」写法 → Showdown 的后缀（单字）。
_ADJECTIVE_SUFFIX: dict[str, str] = {
    "hisuian": "hisui",
    "alolan": "alola",
    "galarian": "galar",
    "paldean": "paldea",
    "female": "f",
    "male": "m",
}

#: Limitless 的物种 slug → 额外的别名（大小写 / 形态后缀差异）。
_SLUG_ALIASES: dict[str, str] = {
    "indeedee": "indeedee-male",
    "basculegion": "basculegion-male",
    "meowstic": "meowstic-male",
    "pyroar": "pyroar-male",
    "aegislash": "aegislash-shield",
    "mimikyu": "mimikyu-disguised",
    "palafin": "palafin-zero",
    "maushold": "maushold-family-of-four",
    "tatsugiri": "tatsugiri-curly",
    "urshifu": "urshifu-single-strike",
    "necrozma-dawn-wings": "necrozma-dawn",
    "ogerpon-wellspring": "ogerpon-wellspring-mask",
    "ogerpon-hearthflame": "ogerpon-hearthflame-mask",
    "ogerpon-cornerstone": "ogerpon-cornerstone-mask",
    "landorus": "landorus-incarnate",
    "tornadus": "tornadus-incarnate",
    "thundurus": "thundurus-incarnate",
    "enamorus": "enamorus-incarnate",
    "keldeo": "keldeo-ordinary",
    "meloetta": "meloetta-aria",
    "darmanitan": "darmanitan-standard",
    "basculin": "basculin-red-striped",
    "zygarde": "zygarde-50",
    "toxtricity": "toxtricity-amped",
    "eiscue": "eiscue-ice",
    "morpeko": "morpeko-full-belly",
    "minior": "minior-red-meteor",
    "squawkabilly": "squawkabilly-green-plumage",
    "gimmighoul": "gimmighoul-chest",
}

#: Showdown 官方名称 → 本地中文名兜底（Pokedex 里没有中文，由 `pokemon` / `pokemon_form`
#: 提供；这里只补少数「Showdown 名与本地 name_en 不一致」的条目）。

#: 官方赛事 Showdown 文本的默认等级。赛事队表不记录等级，统一按满级 100 输出
#: （与建队页新建成员、交换机器人的预期一致）。
TOURNAMENT_DEFAULT_LEVEL = 100

#: Showdown 的 G 形态名后缀（`Charizard-Gmax` / `Urshifu-Rapid-Strike-Gmax`）。
_GMAX_SUFFIX = "-gmax"

#: 赛事站 / 中文社区常用的 G 形态前缀（`Gigantamax Charizard`、`超极巨化 喷火龙`）。
_GMAX_PREFIXES = ("gigantamax ", "g-max ", "gmax ", "超极巨化 ")


def split_gigantamax(name: str | None) -> tuple[str | None, bool]:
    """把 G 形态别名拆成 `("基础形态", True)`。

    兼容两种写法：
      - 后缀：`Charizard-Gmax`（Showdown 的物种别名）；
      - 前缀：`Gigantamax Charizard`（Limitless 赛事队表的显示名）。

    Showdown 的队伍文本用 `Gigantamax: Yes` 行表达超极巨化；本地统一收成
    「基础形态 + 标记」，避免同一只宝可梦出现两个物种名。
    """
    if not name:
        return name, False
    trimmed = name.strip()
    lowered = trimmed.lower()
    if lowered.endswith(_GMAX_SUFFIX):
        base = trimmed[: -len(_GMAX_SUFFIX)].strip()
        if base:
            return base, True
        return trimmed, False
    for prefix in _GMAX_PREFIXES:
        if lowered.startswith(prefix):
            base = trimmed[len(prefix):].strip()
            if base:
                return base, True
            break
    return trimmed, False


@dataclass(frozen=True)
class ShowdownSpecies:
    """一种在 Showdown 里有独立条目的形态。"""

    slug: str
    name: str
    dex_number: int
    #: 该形态可用的特性（Showdown 显示名）
    abilities: tuple[str, ...] = ()
    #: 该形态可学的招式（**小写连字符 slug**，与本地 `showdown_slug` 同口径）
    moves: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ShowdownItem:
    """Showdown 道具目录里与形态相关的一条（目前只关心进化石）。"""

    name: str
    #: 道具 → (成为的形态 Showdown 名)；非进化石为空
    mega_forms: tuple[tuple[str, str], ...] = ()


class ShowdownDex:
    """Showdown 官方图鉴的只读索引。

    `species` / `items` / `moves` / `learnsets` 来自同步时的快照（JSON），
    这里只做索引与查询；数据缺失时调用方应降级（不校验）而不是报错。
    """

    def __init__(
        self,
        *,
        pokedex: dict[str, dict],
        items: dict[str, dict],
        learnsets: dict[str, dict],
        moves: dict[str, dict] | None = None,
    ) -> None:
        self._pokedex = pokedex
        self._items = items
        self._learnsets = learnsets
        #: Showdown 招式 id（`rockslide`）→ 归一化 slug（`rock-slide`）
        move_slugs: dict[str, str] = {}
        for move_id, entry in (moves or {}).items():
            name = str(entry.get("name") or move_id)
            move_slugs[str(move_id).lower()] = showdown_slug(name)
        self._move_slugs = move_slugs
        #: 归一化键 → Showdown 条目（`charizardmegay` → Charizard-Mega-Y）
        self._by_key: dict[str, ShowdownSpecies] = {}
        for entry in pokedex.values():
            name = str(entry.get("name") or "")
            num = entry.get("num")
            if not name or not isinstance(num, int):
                continue
            key = _name_key(name)
            # 部分形态（mega / primal…）在 Showdown 数据里没有独立 learnset，
            # 但规则上继承基础形态的学习表；用 baseSpecies 兜底。
            base_key = _name_key(str(entry.get("baseSpecies") or ""))
            learnset = (
                learnsets.get(key)
                or learnsets.get(base_key)
                or {}
            ).get("learnset") or {}
            abilities = tuple(
                str(value) for value in (entry.get("abilities") or {}).values() if value
            )
            self._by_key[key] = ShowdownSpecies(
                slug=key,
                name=name,
                dex_number=num,
                abilities=abilities,
                moves=frozenset(
                    self.move_slug(move_id) for move_id in learnset if self.move_slug(move_id)
                ),
            )
        #: 道具名（小写 → Showdown 道具名）
        self._items_by_key: dict[str, ShowdownItem] = {}
        for entry in items.values():
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            mega = entry.get("megaStone") or {}
            forms = tuple(
                (str(from_name), str(to_name)) for from_name, to_name in mega.items()
            )
            self._items_by_key[name.lower()] = ShowdownItem(name=name, mega_forms=forms)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def species(self, name_or_slug: str) -> ShowdownSpecies | None:
        key = _name_key(name_or_slug)
        found = self._by_key.get(key)
        if found is not None:
            return found
        if " " in name_or_slug.strip():
            # Limitless 的显示名是「Female Indeedee」「Shadow Rider Calyrex」这种
            # 形容词在前的写法；Showdown 用 `Indeedee-F` / `Calyrex-Shadow`。
            # 规则：形容词换成 Showdown 后缀 → 词序循环右移 → 再逐级去掉尾部词。
            words = [
                _ADJECTIVE_SUFFIX.get(word.lower(), word)
                for word in re.split(r"[-\s]+", name_or_slug.strip())
            ]
            for shift in range(1, len(words) + 1):
                shifted = words[-shift:] + words[:-shift] if shift < len(words) else words
                for length in range(len(shifted), 0, -1):
                    candidate = _name_key("-".join(shifted[:length]))
                    found = self._by_key.get(candidate)
                    if found is not None:
                        return found
        alias = _SLUG_ALIASES.get(name_or_slug.strip().lower())
        if alias:
            return self._by_key.get(_name_key(alias))
        # `arceus-ghost` / `silvally-fairy` 这类按属性分支的形态：去掉后缀找基础形态。
        # 注意归一化键没有连字符，必须按「原始名字的片段」逐级收窄，不能 split("-")。
        raw = name_or_slug.strip()
        parts = re.split(r"[-\s]+", raw)
        for length in range(len(parts) - 1, 0, -1):
            candidate = _name_key("-".join(parts[:length]))
            found = self._by_key.get(candidate)
            if found is not None:
                return found
        return None

    def item(self, name: str | None) -> ShowdownItem | None:
        if not name:
            return None
        return self._items_by_key.get(name.strip().lower())

    def move_slug(self, move_id: str) -> str | None:
        """Showdown 招式 id（`rockslide`）→ 归一化 slug（`rock-slide`）。"""
        return self._move_slugs.get(str(move_id).strip().lower())

    def knows(self, species: ShowdownSpecies, move_label: str) -> bool | None:
        """该形态是否可学某招；无数据时返回 None（未知，而不是「不会」）。"""
        if not species.moves:
            return None
        return showdown_slug(move_label) in species.moves

    def mega_form(self, species: ShowdownSpecies, item_label: str | None) -> str | None:
        """道具是进化石时，返回它对应的形态名（不校验持有者，调用方负责）。"""
        item = self.item(item_label)
        if not item or not item.mega_forms:
            return None
        # 优先匹配持有者（如 Charizardite Y 的持有者是 Charizard）
        for _from, to in item.mega_forms:
            if _name_key(_from) == _name_key(species.name):
                return to
        return item.mega_forms[0][1]


def _name_key(name: str) -> str:
    """Showdown / Limitless 名称 → 归一化键（小写、去非字母数字）。"""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def normalize_nature(label: str | None) -> str | None:
    """`Modest` → `modest`；未知性格返回 None。"""
    if not label:
        return None
    return NATURE_SLUG.get(label.strip().lower())


def normalize_tera(label: str | None) -> str | None:
    """`Fairy` → `Fairy`；未知属性返回 None。"""
    if not label:
        return None
    return _TERA_NORMALIZED.get(label.strip().lower())


def format_level(format_key: str | None) -> int:
    """建队格式自带的默认等级（VGC 50；BDSP 100）。

    注意：官方赛事页的 Showdown 代码**不用**这个值，统一按
    `TOURNAMENT_DEFAULT_LEVEL`（100）输出；这里保留给其它调用方。
    """
    fmt = FORMAT_BY_KEY.get(format_key or "")
    return fmt.default_level if fmt else 50


def format_meta(format_key: str | None) -> dict:
    """建队格式的元信息（默认等级 / 交易前缀 / 是否输出太晶）。"""
    fmt = FORMAT_BY_KEY.get(format_key or "")
    if fmt is None:
        return {
            "format_key": None,
            "default_level": 50,
            "trade_prefix": None,
            "include_tera": False,
            "points_kind": "ev",
        }
    return {
        "format_key": fmt.key,
        "default_level": fmt.default_level,
        "trade_prefix": fmt.trade_prefix,
        "include_tera": fmt.key == "sv",
        "points_kind": fmt.points_kind,
    }


def choose_ability(
    showdown: ShowdownDex,
    species: ShowdownSpecies,
    label: str | None,
) -> str | None:
    """把赛事队表里的特性显示名对齐到该形态实际可用的特性。

    Limitless 会把复合特性写成 `As One (Glastrier)`，而 Showdown 的形态条目里只有
    `As One`；也有个别站方笔误（如把 Glimmora 写成 Rough Skin）。规则：
      1. 原样在可用特性里 → 直接用；
      2. 去掉括号部分后匹配 → 用匹配项；
      3. 仍匹配不到 → 保留原值（不猜，由校验层如实报错）。
    """
    if not label:
        return None
    available = list(species.abilities)
    lowered = {name.lower(): name for name in available}
    direct = lowered.get(label.strip().lower())
    if direct:
        return direct
    # 站方会把复合特性写成 `As One (Glastrier)`；本地的特性表用的是
    # PokéAPI 的形态后缀写法 `as-one-glastrier`。两种写法按归一化键比较。
    key = showdown_slug(label)
    for name in available:
        if showdown_slug(name) == key:
            return name
    base = label.split("(")[0].strip()
    base_key = showdown_slug(base)
    for name in available:
        if showdown_slug(name) == base_key:
            return name
    return label.strip()


def build_showdown_member(
    showdown: ShowdownDex,
    *,
    member_slug: str,
    member_label: str,
    item: str | None,
    ability: str | None,
    nature: str | None,
    tera_type: str | None,
    moves: list[str],
    format_key: str | None,
) -> dict:
    """队表的一只 → 建队页成员字段（Showdown 显示名 + 图鉴编号 + 规整后的配置）。

    返回的 dict 与 `TeamMemberInput` 字段同名，可直接提交给建队接口。
    无法映射图鉴编号时 `dex_number` 为 None（调用方决定是否保留）。

    超极巨化统一折算成「基础形态 + `gigantamax=True`」：赛事数据里的
    `charizard-gmax` / `Charizard-Gmax` 只是别名，导出的代码里只写
    `Gigantamax: Yes`，不再把 `-Gmax` 塞进物种名。
    """
    species = showdown.species(member_slug) or showdown.species(member_label)
    name = member_label or (species.name if species else member_slug)

    # 先认 G 形态：原始 slug / 显示名 / 已解析的 Showdown 名任一命中即可。
    # 兼容后缀（`Charizard-Gmax`）与前缀（`Gigantamax Charizard`）两种写法 ——
    # Limitless 队表用的是后者，导出的代码必须换成 `Gigantamax: Yes`。
    gigantamax = False
    for raw in (member_slug, member_label, name, species.name if species else None):
        base_name, is_gmax = split_gigantamax(raw)
        if not is_gmax:
            continue
        gigantamax = True
        base_species = showdown.species(base_name)
        if base_species is not None:
            species = base_species
            base_name = base_species.name
        # 基础形态可能带形态后缀（`Urshifu-Rapid-Strike-Gmax` → `Urshifu-Rapid-Strike`）
        name = base_name or name
        break

    dex = species.dex_number if species else None

    # 进化石 → 超级进化形态（如 Charizardite Y → Charizard-Mega-Y）。
    # 超级进化与超极巨化互斥：带了进化石就按超级进化，不保留 G 标记。
    if species is not None:
        mega = showdown.mega_form(species, item)
        if mega:
            name = mega
            mega_species = showdown.species(mega)
            if mega_species is not None:
                species = mega_species
                dex = mega_species.dex_number
            gigantamax = False

    resolved_ability = (
        choose_ability(showdown, species, ability) if species is not None else ability
    )
    return {
        "dex_number": dex,
        "showdown_name": name,
        "species_slug": member_slug,
        "item": item.strip() if item else None,
        "ability": resolved_ability,
        "nature": normalize_nature(nature),
        "tera_type": normalize_tera(tera_type),
        "moves": [move.strip() for move in moves if move.strip()][:4],
        # 赛事未公开等级 / 闪光 / 极巨化等级：按页面约定给满级、闪光、默认 10。
        "level": TOURNAMENT_DEFAULT_LEVEL,
        "language": "CHS",
        "shiny": True,
        "dynamax_level": 10,
        "gigantamax": gigantamax,
        "gender": None,
    }


def render_tournament_showdown(
    members: list[dict],
    *,
    format_key: str | None,
) -> str:
    """赛事队表 → Showdown 文本（可直接复制到 Showdown / 交换机器人）。

    与建队页导出同一套写法（行尾两个空格、省略 0 EV / 31 IV），但**不输出
    EV / IV** —— 赛事未公开配点，写一个看起来合理的默认值会误导读者。

    默认值按页面约定固定：等级 100、闪光、语言 CHS。剑盾额外输出
    `Dynamax Level`（默认 10）与超极巨化 `Gigantamax: Yes`（开启时），
    物种名保持基础形态 —— 这样建队页的导入器（与 Showdown 本身）都能直接解析。
    `Tera Type` 只在朱紫输出（其余格式没有太晶）。
    """
    meta = format_meta(format_key)
    blocks: list[str] = []
    for member in members:
        head = member.get("showdown_name") or member.get("species_slug") or ""
        if member.get("item"):
            head += f" @ {member['item']}"
        lines = [head, f"Ability: {member['ability']}"] if member.get("ability") else [head]
        lines.append(f"Level: {member.get('level') or TOURNAMENT_DEFAULT_LEVEL}")
        if format_key == "swsh":
            dynamax_level = member.get("dynamax_level")
            if dynamax_level is None:
                dynamax_level = 10
            lines.append(f"Dynamax Level: {dynamax_level}")
            if member.get("gigantamax"):
                lines.append("Gigantamax: Yes")
        if member.get("shiny", True):
            lines.append("Shiny: Yes")
        # 剑盾的复制代码不带语言标记（与建队页导出同一口径）
        if format_key != "swsh":
            lines.append(f"Language: {member.get('language') or 'CHS'}")
        if meta["include_tera"] and member.get("tera_type"):
            lines.append(f"Tera Type: {member['tera_type']}")
        if member.get("nature"):
            lines.append(f"{member['nature'].capitalize()} Nature")
        for move in member.get("moves") or []:
            lines.append(f"- {move}")
        blocks.append("\n".join(f"{line}  " for line in lines))
    return "\n\n".join(blocks)
