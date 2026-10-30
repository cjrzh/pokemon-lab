"""PokéAPI 响应 → 图鉴记录的解析（纯函数）。

不做 IO：原始 payload 由调用方（同步脚本 / 同步服务）传入。
这样解析逻辑可以被 pytest 直接测试，与网络彻底解耦。

涉及的上游端点：
  - /pokemon/{id}            属性、种族值、身高体重、特性、招式学习表
  - /pokemon-species/{id}    中文/日文名、分类、图鉴描述、登场世代、进化链 URL
  - /evolution-chain/{id}    进化链结构与条件
  - /ability/{id}            特性中文名与说明（由同步服务按需解析后传入）
  - /move/{id}               招式中文名、属性、威力等（同上）

图片策略（见 docs/DATA_SOURCES.md）：
  - 官方图鉴立绘来自 pokemon.com 的公开图鉴资源（full 475px / detail 215px）；
  - 兜底图片使用 PokéAPI sprites 仓库的 official-artwork，经 wsrv.nl 图片代理访问
    （本机直连 raw.githubusercontent.com 不稳定）。
"""

from __future__ import annotations

import json
import re
from typing import Any

#: 种族值展示顺序（游戏内习惯顺序）。
STAT_ORDER = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]

STAT_ZH = {
    "hp": "HP",
    "attack": "攻击",
    "defense": "防御",
    "special-attack": "特攻",
    "special-defense": "特防",
    "speed": "速度",
}

#: 内置的特性中文名兜底表。同步时会用 /ability 的 zh-hans 名称覆盖；
#: 保留这张小表是为了让「没有网络但已有缓存」的记录也能显示中文。
ABILITY_ZH = {
    "overgrow": "茂盛",
    "blaze": "猛火",
    "torrent": "激流",
    "swarm": "虫之预感",
    "shield-dust": "鳞粉",
    "run-away": "逃跑",
    "shedinja": "神秘守护",
    "chlorophyll": "叶绿素",
    "guts": "毅力",
    "hustle": "活力",
    "intimidate": "威吓",
    "keen-eye": "锐利目光",
    "stance-change": "战斗切换",
    "static": "静电",
    "lightning-rod": "避雷针",
    "pressure": "压迫感",
    "unnerve": "紧张感",
}

#: 伤害类别中文名。
DAMAGE_CLASS_ZH = {"physical": "物理", "special": "特殊", "status": "变化"}

#: 进化触发方式中文名。
TRIGGER_ZH = {
    "level-up": "等级提升",
    "use-item": "使用道具",
    "trade": "通信交换",
    "shed": "特殊进化",
    "spin": "旋转",
    "tower-of-darkness": "恶之塔",
    "tower-of-waters": "水之塔",
    "three-critical-hits": "击中要害 3 次",
    "take-damage": "承受伤害",
    "agile-style": "迅疾风格",
    "strong-style": "刚猛风格",
    "recoil-damage": "承受反作用力伤害",
    "other": "其他方式",
}

#: 进化道具中文名（Kanto 及常见进化石 / 道具）。
EVOLUTION_ITEM_ZH = {
    "fire-stone": "火之石",
    "water-stone": "水之石",
    "thunder-stone": "雷之石",
    "leaf-stone": "叶之石",
    "moon-stone": "月之石",
    "sun-stone": "日之石",
    "shiny-stone": "光之石",
    "dusk-stone": "暗之石",
    "dawn-stone": "觉醒之石",
    "ice-stone": "冰之石",
    "oval-stone": "浑圆之石",
    "kings-rock": "王者之证",
    "metal-coat": "金属膜",
    "dragon-scale": "龙之鳞片",
    "upgrade": "升级数据",
    "dubious-disc": "可疑修正数据",
    "electirizer": "电力增幅器",
    "magmarizer": "熔岩增幅器",
    "protector": "护具",
    "reaper-cloth": "灵界之布",
    "prism-scale": "美丽鳞片",
    "whipped-dream": "泡沫奶油",
    "sachet": "香袋",
    "tart-apple": "酸酸苹果",
    "sweet-apple": "甜甜苹果",
    "auspicious-armor": "庆祝之铠",
    "malicious-armor": "咒术之铠",
    "black-augurite": "黑奇石",
    "peat-block": "泥炭块",
    "scroll-of-darkness": "暗之卷轴",
    "scroll-of-waters": "水之卷轴",
    "strawberry-sweet": "草莓糖饰",
    "love-sweet": "爱心糖饰",
    "berry-sweet": "野莓糖饰",
    "clover-sweet": "幸运草糖饰",
    "flower-sweet": "花朵糖饰",
    "star-sweet": "星星糖饰",
    "ribbon-sweet": "蝴蝶结糖饰",
}

TIME_OF_DAY_ZH = {"day": "白天", "night": "夜晚", "dusk": "黄昏"}

#: 图鉴描述里的换行 / 换页 / 软连字符，统一清理为空格。
_WHITESPACE_RE = re.compile(r"[\n\r\f­​]+")

#: 选择招式学习表时优先使用的版本组（越靠前越新）。
#: PokéAPI 的 /pokemon 响应不带版本组先后信息，这里维护一份显式顺序。
#: 注意：关都 #1–151 中大多数宝可梦在《朱/紫》《剑/盾》没有出场记录，
#: 所以「有数据的最新作品」通常落在晶灿钻石／明亮珍珠或究极日月上。
VERSION_GROUP_ORDER = [
    "scarlet-violet",
    "legends-arceus",
    "brilliant-diamond-shining-pearl",
    "sword-shield",
    "lets-go-pikachu-lets-go-eevee",
    "ultra-sun-ultra-moon",
    "sun-moon",
    "omega-ruby-alpha-sapphire",
    "x-y",
    "black-2-white-2",
    "black-white",
    "heartgold-soulsilver",
    "platinum",
    "diamond-pearl",
    "emerald",
    "firered-leafgreen",
    "ruby-sapphire",
    "crystal",
    "gold-silver",
    "yellow",
    "red-blue",
]

VERSION_GROUP_ZH = {
    "scarlet-violet": "朱／紫",
    "legends-arceus": "传说 阿尔宙斯",
    "brilliant-diamond-shining-pearl": "晶灿钻石／明亮珍珠",
    "sword-shield": "剑／盾",
    "lets-go-pikachu-lets-go-eevee": "Let's Go 皮卡丘／伊布",
    "ultra-sun-ultra-moon": "究极之日／究极之月",
    "sun-moon": "太阳／月亮",
    "omega-ruby-alpha-sapphire": "欧米伽红宝石／阿尔法蓝宝石",
    "x-y": "X／Y",
    "black-2-white-2": "黑2／白2",
    "black-white": "黑／白",
    "heartgold-soulsilver": "心金／魂银",
    "platinum": "白金",
    "diamond-pearl": "钻石／珍珠",
    "emerald": "绿宝石",
    "firered-leafgreen": "火红／叶绿",
    "ruby-sapphire": "红宝石／蓝宝石",
    "crystal": "水晶",
    "gold-silver": "金／银",
    "yellow": "皮卡丘",
    "red-blue": "红／蓝",
}

#: 图片地址（公开资源，详见 docs/DATA_SOURCES.md）。
POKEMON_COM_ARTWORK = "https://assets.pokemon.com/assets/cms2/img/pokedex/full/{dex:03d}.png"
POKEMON_COM_THUMBNAIL = "https://assets.pokemon.com/assets/cms2/img/pokedex/detail/{dex:03d}.png"
#: 兜底：PokéAPI official-artwork 经 wsrv.nl 代理（raw.githubusercontent 直连不稳定）。
POKEAPI_ARTWORK_PROXY = (
    "https://wsrv.nl/?url=raw.githubusercontent.com/PokeAPI/sprites/"
    "master/sprites/pokemon/other/official-artwork/{dex}.png"
)


class PokemonParseError(ValueError):
    """上游 payload 结构不符合预期。调用方跳过该条并记录，不中断整批同步。"""


# ---------------------------------------------------------------------------
# 基础记录
# ---------------------------------------------------------------------------


def parse_pokemon(pokemon_payload: dict[str, Any], species_payload: dict[str, Any]) -> dict:
    """把 /pokemon + /pokemon-species 两个响应解析为图鉴记录（不含进化链与招式详情）。

    返回的 dict 直接对应 pokemon 表字段；进化链、招式与特性说明由
    `attach_evolution` / `attach_moves` / `attach_ability_details` 补充。
    """
    try:
        dex_number = int(pokemon_payload["id"])
        name_en = str(pokemon_payload["name"])
        types = [slot["type"]["name"] for slot in pokemon_payload["types"]]
        # PokéAPI 的 types 按 slot 升序，已经是「第一属性在前」
        stats_raw = {s["stat"]["name"]: int(s["base_stat"]) for s in pokemon_payload["stats"]}
        stats = {key: stats_raw[key] for key in STAT_ORDER if key in stats_raw}

        abilities = []
        for entry in pokemon_payload["abilities"]:
            ability_name = entry["ability"]["name"]
            abilities.append(
                {
                    "name": ability_name,
                    "is_hidden": bool(entry.get("is_hidden", False)),
                    # 中文名没有内置兜底时保持 None：宁可在界面显示英文原名，
                    # 也不把「Title Case 的英文」塞进中文字段冒充翻译。
                    "zh": ABILITY_ZH.get(ability_name),
                    "effect_zh": None,
                    "effect_en": None,
                }
            )

        record = {
            "dex_number": dex_number,
            "name_en": name_en,
            "name_zh": _pick_zh_name(species_payload),
            "name_ja": _pick_ja_name(species_payload),
            "types_json": _dumps(types),
            "stats_json": _dumps(stats),
            "abilities_json": _dumps(abilities),
            "evolution_json": _dumps({}),
            "moves_json": _dumps({}),
            "generation_introduced": _parse_generation(
                species_payload.get("generation", {}).get("name")
            ),
            "height_dm": _optional_int(pokemon_payload.get("height")),
            "weight_hg": _optional_int(pokemon_payload.get("weight")),
            "genus_zh": _pick_genus(species_payload, ("zh-hans", "zh-hant")),
            "genus_en": _pick_genus(species_payload, ("en",)),
            "flavor_zh": _clean_text(_pick_flavor(species_payload, ("zh-hans", "zh-hant"))),
            "flavor_en": _clean_text(_pick_flavor(species_payload, ("en",))),
            # 来源标记：中文文本来自上游时标 pokeapi；缺失时由译文服务补 project。
            "flavor_zh_source": None,
            "genus_zh_source": None,
            "is_legendary": bool(species_payload.get("is_legendary", False)),
            "is_mythical": bool(species_payload.get("is_mythical", False)),
            "is_baby": bool(species_payload.get("is_baby", False)),
            "gender_rate": _optional_int(species_payload.get("gender_rate")),
            "capture_rate": _optional_int(species_payload.get("capture_rate")),
            "base_happiness": _optional_int(species_payload.get("base_happiness")),
            "hatch_counter": _optional_int(species_payload.get("hatch_counter")),
            "growth_rate": _nested_name(species_payload.get("growth_rate")),
            "habitat": _nested_name(species_payload.get("habitat")),
            "color": _nested_name(species_payload.get("color")),
            "shape": _nested_name(species_payload.get("shape")),
            "egg_groups_json": _dumps(
                [
                    group["name"]
                    for group in species_payload.get("egg_groups", [])
                    if isinstance(group, dict) and group.get("name")
                ]
            ),
            # 图片：pokemon.com 官方图鉴立绘为默认地址；本地缓存路径由同步服务写入
            # （`artwork_path`），frontend 优先用本地缓存，失败时回落到 artwork_url。
            "artwork_url": POKEMON_COM_ARTWORK.format(dex=dex_number),
            "sprite_url": POKEAPI_ARTWORK_PROXY.format(dex=dex_number),
            "cry_url": None,
            "source": "pokeapi",
        }
        return record
    except (KeyError, TypeError, ValueError) as exc:
        raise PokemonParseError(
            f"解析失败（pokemon id={pokemon_payload.get('id', '?')}）：{exc}"
        ) from exc


# ---------------------------------------------------------------------------
# 特性 / 招式详情（同步服务按需拉取后合并）
# ---------------------------------------------------------------------------


def parse_ability_details(ability_payload: dict[str, Any]) -> dict:
    """解析 /ability/{name}：中文名 + 中文图鉴说明 + 英文简短效果。"""
    name = str(ability_payload.get("name") or "")
    return {
        "name": name,
        "zh": _pick_localized_name(ability_payload, ("zh-hans", "zh-hant")) or ABILITY_ZH.get(name),
        "effect_zh": _clean_text(_pick_flavor(ability_payload, ("zh-hans", "zh-hant"))),
        "effect_en": _pick_effect_short(ability_payload),
    }


def attach_ability_details(record: dict, details: dict[str, dict]) -> dict:
    """把特性详情合并进 abilities_json（找不到详情的特性保留原值）。"""
    abilities = _loads(record.get("abilities_json"), [])
    merged = []
    for ability in abilities:
        detail = details.get(ability.get("name", ""))
        if not detail:
            merged.append(ability)
            continue
        merged.append(
            {
                **ability,
                "zh": detail.get("zh") or ability.get("zh"),
                "effect_zh": detail.get("effect_zh"),
                "effect_en": detail.get("effect_en"),
            }
        )
    return {**record, "abilities_json": _dumps(merged)}


#: 招式学习方式的中文名。PokéAPI 的 7 种 learn method 全部覆盖，
#: 未列出的值原样展示（不猜测翻译）。
LEARN_METHOD_ZH = {
    "level-up": "升级",
    "machine": "招式学习器",
    "egg": "蛋招式",
    "tutor": "教学",
    "train": "特殊教学",
    "xd-purification": "净化",
    "stadium-surfing-pikachu": "特殊活动",
}

#: 招式详情页展示的版本组：按作品代次从新到旧（与 VERSION_GROUP_ORDER 相反）。
#: 每个版本组是一行「哪一代的哪些作品可以学这招」。
MOVE_VERSION_GROUP_ORDER = [
    "scarlet-violet",
    "legends-arceus",
    "brilliant-diamond-shining-pearl",
    "sword-shield",
    "lets-go-pikachu-lets-go-eevee",
    "ultra-sun-ultra-moon",
    "sun-moon",
    "omega-ruby-alpha-sapphire",
    "x-y",
    "black-2-white-2",
    "black-white",
    "heartgold-soulsilver",
    "platinum",
    "diamond-pearl",
    "emerald",
    "firered-leafgreen",
    "ruby-sapphire",
    "crystal",
    "gold-silver",
    "yellow",
    "red-blue",
]

#: 展示顺序：先升级，再学习器/教学，最后蛋招式。
LEARN_METHOD_ORDER = [
    "level-up",
    "machine",
    "tutor",
    "egg",
    "train",
    "xd-purification",
    "stadium-surfing-pikachu",
]


def parse_move_details(move_payload: dict[str, Any]) -> dict:
    """解析 /move/{name}：中文名、属性、伤害类别、威力/命中/PP、图鉴说明。"""
    name = str(move_payload.get("name") or "")
    move_type = _nested_name(move_payload.get("type"))
    damage_class = _nested_name(move_payload.get("damage_class"))
    return {
        "name": name,
        "zh": _pick_localized_name(move_payload, ("zh-hans", "zh-hant")),
        "type": move_type,
        "damage_class": damage_class,
        "damage_class_zh": DAMAGE_CLASS_ZH.get(damage_class or "", None),
        "power": _optional_int(move_payload.get("power")),
        "accuracy": _optional_int(move_payload.get("accuracy")),
        "pp": _optional_int(move_payload.get("pp")),
        "description_zh": _clean_text(_pick_flavor(move_payload, ("zh-hans", "zh-hant"))),
    }


def extract_all_moves(pokemon_payload: dict[str, Any]) -> dict[str, dict[str, list[dict]]]:
    """从 /pokemon 的 moves 中提取**全部**版本组与学习方式。

    返回：
        {"scarlet-violet": {"level-up": [{"name": "tackle", "level": 1}],
                            "machine":  [{"name": "protect", "level": 0}],
                            "egg":      [...]},
         "sword-shield": {...}}

    每个 (版本组, 学习方式) 内按等级 + 名称排序：
      - 升级招式按等级升序（同等级按名称）；
      - 学习器 / 教学 / 蛋招式等级恒为 0，按名称排序，便于查找。
    """
    buckets: dict[str, dict[str, list[dict]]] = {}
    for entry in pokemon_payload.get("moves", []):
        move_name = entry.get("move", {}).get("name")
        if not move_name:
            continue
        for detail in entry.get("version_group_details", []):
            method = detail.get("move_learn_method", {}).get("name")
            group = detail.get("version_group", {}).get("name")
            if not method or not group:
                continue
            level = _optional_int(detail.get("level_learned_at")) or 0
            buckets.setdefault(group, {}).setdefault(method, []).append(
                {"name": move_name, "level": level}
            )

    for methods in buckets.values():
        for method, moves in methods.items():
            # 同一招式在同一版本组可能出现多次（如不同的 TM），去重
            deduped = {(m["name"], m["level"]): m for m in moves}.values()
            if method == "level-up":
                methods[method] = sorted(deduped, key=lambda m: (m["level"], m["name"]))
            else:
                methods[method] = sorted(deduped, key=lambda m: m["name"])
    return buckets


def pick_latest_version_group(
    groups: dict[str, dict[str, list[dict]]],
) -> str | None:
    """按 VERSION_GROUP_ORDER 选「有数据的、最新的」版本组作为默认展示项。"""
    if not groups:
        return None

    def rank(group: str) -> int:
        try:
            return VERSION_GROUP_ORDER.index(group)
        except ValueError:
            return len(VERSION_GROUP_ORDER)

    return sorted(groups, key=rank)[0]


def collect_move_names(groups: dict[str, dict[str, list[dict]]]) -> set[str]:
    """收集所有出现过的招式名（用于批量拉取招式详情）。"""
    return {
        move["name"]
        for methods in groups.values()
        for moves in methods.values()
        for move in moves
    }


def attach_moves(
    record: dict,
    groups: dict[str, dict[str, list[dict]]],
) -> dict:
    """把「版本组 → 学习方式 → 招式名/等级」写入 moves_json。

    招式数值（属性/威力/PP）不在这里重复存，而是由 `move_ref` 表统一提供；
    这里只保留「谁、在哪个版本组、用什么方式、几级学会」。
    无数据时写空对象。
    """
    if not groups:
        return {**record, "moves_json": _dumps({})}

    latest = pick_latest_version_group(groups)
    payload = {
        "default_version_group": latest,
        "version_group_label": VERSION_GROUP_ZH.get(latest or "", latest),
        "version_groups": {
            group: {
                "label": VERSION_GROUP_ZH.get(group, group),
                "methods": {
                    method: moves
                    for method, moves in sorted(
                        methods.items(),
                        key=lambda item: (
                            LEARN_METHOD_ORDER.index(item[0])
                            if item[0] in LEARN_METHOD_ORDER
                            else len(LEARN_METHOD_ORDER),
                            item[0],
                        ),
                    )
                },
            }
            for group, methods in sorted(groups.items())
        },
    }
    return {**record, "moves_json": _dumps(payload)}


# ---------------------------------------------------------------------------
# 进化链
# ---------------------------------------------------------------------------


def parse_evolution_chain(chain_payload: dict[str, Any], dex_number: int) -> dict:
    """解析 /evolution-chain 响应为进化链结构。

    输出形如：
        {"chain": [{"name": "bulbasaur", "dex": 1, "detail": None,
                    "evolves_to": [ {...递归...} ]}]}
    每个节点附带人类可读的进化条件（等级 / 道具 / 交换 / 亲密度等）。
    """
    try:
        root = chain_payload["chain"]
        chain_name = str(chain_payload.get("id", ""))
        tree = _convert_chain_node(root)
        return {"chain_id": chain_name, "chain": tree}
    except (KeyError, TypeError) as exc:
        raise PokemonParseError(f"解析进化链失败（dex={dex_number}）：{exc}") from exc


def _convert_chain_node(node: dict[str, Any]) -> dict:
    species_name = node["species"]["name"]
    species_url = node["species"]["url"]
    dex = int(species_url.rstrip("/").split("/")[-1])
    return {
        "name": species_name,
        "dex": dex,
        "detail": _describe_evolution(node),
        "evolves_to": [_convert_chain_node(child) for child in node.get("evolves_to", [])],
    }


def _describe_evolution(node: dict[str, Any]) -> str | None:
    """把 evolution_details 转成中文条件描述；根节点返回 None。"""
    details = node.get("evolution_details") or []
    if not details:
        return None
    # 优先使用 is_default 的一条；否则取最后一条（通常是最新规则）
    chosen = next((d for d in details if d.get("is_default")), details[-1])

    trigger = chosen.get("trigger", {}).get("name") or ""
    item = (chosen.get("item") or {}).get("name")
    held_item = (chosen.get("held_item") or {}).get("name")
    known_move = (chosen.get("known_move") or {}).get("name")
    known_move_type = (chosen.get("known_move_type") or {}).get("name")
    location = (chosen.get("location") or {}).get("name")
    min_level = _optional_int(chosen.get("min_level"))
    min_happiness = _optional_int(chosen.get("min_happiness"))
    min_affection = _optional_int(chosen.get("min_affection"))
    min_beauty = _optional_int(chosen.get("min_beauty"))
    time_of_day = chosen.get("time_of_day") or ""

    parts: list[str] = []
    if min_level:
        parts.append(f"等级 {min_level}")
    elif trigger == "use-item" and item:
        parts.append(f"使用{_item_zh(item)}")
    elif trigger == "trade":
        parts.append("通信交换")
    elif trigger and trigger not in {"level-up", "use-item", "trade"}:
        parts.append(TRIGGER_ZH.get(trigger, trigger))

    if held_item:
        parts.append(f"携带{_item_zh(held_item)}")
    if min_happiness:
        parts.append(f"亲密度 ≥ {min_happiness}")
    if min_affection:
        parts.append(f"友好度 ≥ {min_affection}")
    if min_beauty:
        parts.append(f"美丽度 ≥ {min_beauty}")
    if known_move:
        parts.append(f"学会「{known_move}」")
    if known_move_type:
        parts.append(f"学会 {known_move_type} 属性招式")
    if time_of_day in TIME_OF_DAY_ZH:
        parts.append(TIME_OF_DAY_ZH[time_of_day])
    if chosen.get("needs_overworld_rain"):
        parts.append("下雨时")
    if chosen.get("near_special_rock"):
        parts.append("在特殊岩石附近")
    if location:
        parts.append(f"在 {location}")
    if chosen.get("relative_physical_stats") == 1:
        parts.append("攻击 > 防御")
    elif chosen.get("relative_physical_stats") == -1:
        parts.append("攻击 < 防御")

    return " · ".join(parts) if parts else TRIGGER_ZH.get(trigger, "特殊条件")


def evolution_chain_url_from_species(species_payload: dict[str, Any]) -> str | None:
    """从 species 响应中取进化链 URL（相对路径或 None）。"""
    url = species_payload.get("evolution_chain", {}).get("url")
    return str(url) if url else None


def attach_evolution(record: dict, evolution: dict) -> dict:
    """把解析好的进化链挂到记录上（返回新 dict，不改原记录）。"""
    return {**record, "evolution_json": _dumps(evolution)}


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _pick_zh_name(species_payload: dict[str, Any]) -> str | None:
    """取 zh-hans 中文名；无则回落 zh-hant，再无则 None。

    注意：PokéAPI 的语言代码是**小写**（zh-hans / zh-hant），
    匹配统一做大小写折叠，避免上游风格变化导致静默丢中文名。
    """
    return _pick_localized_name(species_payload, ("zh-hans", "zh-hant"))


def _pick_ja_name(species_payload: dict[str, Any]) -> str | None:
    return _pick_localized_name(species_payload, ("ja", "ja-hrkt"))


def _pick_localized_name(payload: dict[str, Any], languages: tuple[str, ...]) -> str | None:
    names = payload.get("names", [])
    for language in languages:
        found = next(
            (
                n["name"]
                for n in names
                if str(n.get("language", {}).get("name", "")).lower() == language
            ),
            None,
        )
        if found:
            return str(found)
    return None


def _pick_genus(species_payload: dict[str, Any], languages: tuple[str, ...]) -> str | None:
    genera = species_payload.get("genera", [])
    for language in languages:
        found = next(
            (
                g["genus"]
                for g in genera
                if str(g.get("language", {}).get("name", "")).lower() == language
            ),
            None,
        )
        if found:
            return str(found)
    return None


def _pick_flavor(payload: dict[str, Any], languages: tuple[str, ...]) -> str | None:
    """取最新版本的中文/英文图鉴描述（同语言按版本顺序取最后一条）。"""
    entries = payload.get("flavor_text_entries", [])
    for language in languages:
        candidates = [
            str(entry["flavor_text"])
            for entry in entries
            if str(entry.get("language", {}).get("name", "")).lower() == language
            and entry.get("flavor_text")
        ]
        if candidates:
            return candidates[-1]
    return None


def _pick_effect_short(ability_payload: dict[str, Any]) -> str | None:
    entries = ability_payload.get("effect_entries", [])
    for language in ("en",):
        found = next(
            (
                e.get("short_effect")
                for e in entries
                if str(e.get("language", {}).get("name", "")).lower() == language
            ),
            None,
        )
        if found:
            return _clean_text(found)
    return None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = _WHITESPACE_RE.sub(" ", str(value))
    return re.sub(r"\s{2,}", " ", text).strip() or None


def _nested_name(value: Any) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else None
    return None


def _item_zh(slug: str) -> str:
    return EVOLUTION_ITEM_ZH.get(slug, slug)


def _parse_generation(generation_name: str | None) -> int | None:
    """'generation-i' → 1。无法解析返回 None。"""
    if not generation_name or "-" not in generation_name:
        return None
    roman = generation_name.split("-", 1)[1]
    numerals = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9}
    return numerals.get(roman)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: Any, default):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
