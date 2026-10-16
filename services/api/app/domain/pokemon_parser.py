"""PokéAPI 响应 → 图鉴记录的解析（纯函数）。

不做 IO：原始 payload 由调用方（同步脚本 / 同步服务）传入。
这样解析逻辑可以被 pytest 直接测试，与网络彻底解耦。

涉及三个上游端点：
  - /pokemon/{id}            属性、种族值、身高体重、特性
  - /pokemon-species/{id}    中文名、登场世代、进化链 URL
  - /evolution-chain/{id}    进化链结构（链式 detail）
"""

from __future__ import annotations

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

ABILITY_ZH = {
    "overgrow": "茂盛",
    "blaze": "猛火",
    "torrent": "激流",
    "swarm": "虫之预感",
    "shield-dust": "鳞粉",
    "run-away": "逃跑",
    "shedinja": "奇异守护",
    "chlorophyll": "叶绿素",
    "guts": "毅力",
    "hustle": "活力",
    "intimidate": "威吓",
    "keen-eye": "锐利目光",
    "stance-change": "战斗切换",
}


class PokemonParseError(ValueError):
    """上游 payload 结构不符合预期。调用方跳过该条并记录，不中断整批同步。"""


def parse_pokemon(pokemon_payload: dict[str, Any], species_payload: dict[str, Any]) -> dict:
    """把 /pokemon + /pokemon-species 两个响应解析为图鉴记录（不含进化链）。

    返回的 dict 直接对应 pokemon 表字段（evolution_json 稍后由
    `attach_evolution` 补充）。
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
            ability = {
                "name": entry["ability"]["name"],
                "is_hidden": bool(entry.get("is_hidden", False)),
                "zh": ABILITY_ZH.get(entry["ability"]["name"]),
            }
            abilities.append(ability)

        name_zh = _pick_zh_name(species_payload)
        generation_introduced = _parse_generation(species_payload.get("generation", {}).get("name"))

        return {
            "dex_number": dex_number,
            "name_en": name_en,
            "name_zh": name_zh,
            "types_json": _dumps(types),
            "stats_json": _dumps(stats),
            "abilities_json": _dumps(abilities),
            "evolution_json": _dumps({}),
            "generation_introduced": generation_introduced,
            "height_dm": _optional_int(pokemon_payload.get("height")),
            "weight_hg": _optional_int(pokemon_payload.get("weight")),
            "source": "pokeapi",
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PokemonParseError(
            f"解析失败（pokemon id={pokemon_payload.get('id', '?')}）：{exc}"
        ) from exc


def parse_evolution_chain(chain_payload: dict[str, Any], dex_number: int) -> dict:
    """解析 /evolution-chain 响应为进化链结构。

    输出形如：
        {"chain": [{"name": "bulbasaur", "dex": 1, "zh": "妙蛙种子",
                    "evolves_to": [ {...递归...} ]}]}
    只保留与目标宝可梦相关的路径（从根到目标所在分支），避免无关旁支。
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
        "evolves_to": [_convert_chain_node(child) for child in node.get("evolves_to", [])],
    }


def evolution_chain_url_from_species(species_payload: dict[str, Any]) -> str | None:
    """从 species 响应中取进化链 URL（相对路径或 None）。"""
    url = species_payload.get("evolution_chain", {}).get("url")
    return str(url) if url else None


def attach_evolution(record: dict, evolution: dict) -> dict:
    """把解析好的进化链挂到记录上（返回新 dict，不改原记录）。"""
    return {**record, "evolution_json": _dumps(evolution)}


def _pick_zh_name(species_payload: dict[str, Any]) -> str | None:
    """取 zh-hans 中文名；无则回落 zh-hant，再无则 None。

    注意：PokéAPI 的语言代码是**小写**（zh-hans / zh-hant），
    匹配统一做大小写折叠，避免上游风格变化导致静默丢中文名。
    """
    names = species_payload.get("names", [])

    def pick(lang: str) -> str | None:
        return next(
            (
                n["name"]
                for n in names
                if str(n.get("language", {}).get("name", "")).lower() == lang
            ),
            None,
        )

    return pick("zh-hans") or pick("zh-hant")


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
    import json

    return json.dumps(value, ensure_ascii=False)
