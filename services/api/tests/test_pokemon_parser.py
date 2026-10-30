"""pokemon_parser 纯函数测试：用贴近 PokéAPI 真实结构的最小 payload。"""

from __future__ import annotations

import json

import pytest

from app.domain.pokemon_parser import (
    PokemonParseError,
    attach_evolution,
    evolution_chain_url_from_species,
    parse_evolution_chain,
    parse_pokemon,
)


def _pokemon_payload() -> dict:
    """妙蛙草的最小 /pokemon 响应（字段结构与真实接口一致）。"""
    return {
        "id": 2,
        "name": "ivysaur",
        "height": 10,
        "weight": 130,
        "types": [
            {"slot": 1, "type": {"name": "grass"}},
            {"slot": 2, "type": {"name": "poison"}},
        ],
        "stats": [
            {"base_stat": 60, "stat": {"name": "hp"}},
            {"base_stat": 62, "stat": {"name": "attack"}},
            {"base_stat": 63, "stat": {"name": "defense"}},
            {"base_stat": 80, "stat": {"name": "special-attack"}},
            {"base_stat": 80, "stat": {"name": "special-defense"}},
            {"base_stat": 60, "stat": {"name": "speed"}},
        ],
        "abilities": [
            {"is_hidden": False, "ability": {"name": "overgrow"}},
            {"is_hidden": True, "ability": {"name": "chlorophyll"}},
        ],
    }


def _species_payload() -> dict:
    return {
        "id": 2,
        "name": "ivysaur",
        "names": [
            {"name": "フシギソウ", "language": {"name": "ja-Hrkt"}},
            {"name": "Ivysaur", "language": {"name": "en"}},
            {"name": "妙蛙草", "language": {"name": "zh-hans"}},
        ],
        "generation": {"name": "generation-i"},
        "evolution_chain": {"url": "https://pokeapi.co/api/v2/evolution-chain/1/"},
    }


def test_parse_pokemon_basic_fields() -> None:
    record = parse_pokemon(_pokemon_payload(), _species_payload())

    assert record["dex_number"] == 2
    assert record["name_en"] == "ivysaur"
    assert record["name_zh"] == "妙蛙草"
    assert record["generation_introduced"] == 1
    assert record["height_dm"] == 10
    assert record["weight_hg"] == 130
    assert record["source"] == "pokeapi"

    assert json.loads(record["types_json"]) == ["grass", "poison"]
    stats = json.loads(record["stats_json"])
    assert stats == {
        "hp": 60,
        "attack": 62,
        "defense": 63,
        "special-attack": 80,
        "special-defense": 80,
        "speed": 60,
    }

    abilities = json.loads(record["abilities_json"])
    assert abilities[0]["name"] == "overgrow"
    assert abilities[0]["is_hidden"] is False
    assert abilities[0]["zh"] == "茂盛"
    assert abilities[0]["effect_zh"] is None  # 详情由 /ability 补充
    assert abilities[1]["is_hidden"] is True


def test_parse_pokemon_profile_fields() -> None:
    """分类、图鉴描述、档案数值与图片地址。"""
    species = _species_payload()
    species.update(
        {
            "genera": [
                {"genus": "種子寶可夢", "language": {"name": "zh-hant"}},
                {"genus": "种子宝可梦", "language": {"name": "zh-hans"}},
                {"genus": "Seed Pokémon", "language": {"name": "en"}},
            ],
            "flavor_text_entries": [
                {
                    "flavor_text": "背上的种子裡\n儲存著營養。\f會漸漸長大。",
                    "language": {"name": "zh-hant"},
                },
                {
                    "flavor_text": "背上的种子里储存着营养。\n会渐渐长大。",
                    "language": {"name": "zh-hans"},
                },
                {
                    "flavor_text": "A strange seed was\nplanted on its back.",
                    "language": {"name": "en"},
                },
            ],
            "is_legendary": False,
            "is_mythical": False,
            "gender_rate": 1,
            "capture_rate": 45,
            "base_happiness": 70,
            "hatch_counter": 20,
            "growth_rate": {"name": "medium-slow"},
            "egg_groups": [{"name": "monster"}, {"name": "plant"}],
        }
    )
    record = parse_pokemon(_pokemon_payload(), species)

    assert record["genus_zh"] == "种子宝可梦"
    assert record["genus_en"] == "Seed Pokémon"
    assert record["flavor_zh"] == "背上的种子里储存着营养。 会渐渐长大。"
    assert record["flavor_en"] == "A strange seed was planted on its back."
    assert record["gender_rate"] == 1
    assert record["capture_rate"] == 45
    assert record["growth_rate"] == "medium-slow"
    assert json.loads(record["egg_groups_json"]) == ["monster", "plant"]
    assert record["artwork_url"] == "https://assets.pokemon.com/assets/cms2/img/pokedex/full/002.png"
    assert "official-artwork/2.png" in record["sprite_url"]


def test_parse_pokemon_falls_back_to_zh_hant() -> None:
    species = _species_payload()
    species["names"] = [{"name": "妙蛙草", "language": {"name": "zh-hant"}}]
    record = parse_pokemon(_pokemon_payload(), species)
    assert record["name_zh"] == "妙蛙草"


def test_parse_pokemon_without_zh_name() -> None:
    species = _species_payload()
    species["names"] = [{"name": "Ivysaur", "language": {"name": "en"}}]
    record = parse_pokemon(_pokemon_payload(), species)
    assert record["name_zh"] is None


def test_parse_pokemon_rejects_broken_payload() -> None:
    with pytest.raises(PokemonParseError):
        parse_pokemon({"id": "oops"}, _species_payload())


def test_parse_generation_roman() -> None:
    species = _species_payload()
    species["generation"]["name"] = "generation-ix"
    assert parse_pokemon(_pokemon_payload(), species)["generation_introduced"] == 9

    species["generation"]["name"] = None
    assert parse_pokemon(_pokemon_payload(), species)["generation_introduced"] is None


def test_parse_evolution_chain_tree() -> None:
    chain_payload = {
        "id": 1,
        "chain": {
            "species": {"name": "bulbasaur", "url": "https://pokeapi.co/api/v2/pokemon-species/1/"},
            "evolves_to": [
                {
                    "species": {
                        "name": "ivysaur",
                        "url": "https://pokeapi.co/api/v2/pokemon-species/2/",
                    },
                    "evolves_to": [
                        {
                            "species": {
                                "name": "venusaur",
                                "url": "https://pokeapi.co/api/v2/pokemon-species/3/",
                            },
                            "evolves_to": [],
                        }
                    ],
                }
            ],
        },
    }
    tree = parse_evolution_chain(chain_payload, 2)

    assert tree["chain_id"] == "1"
    root = tree["chain"]
    assert root["name"] == "bulbasaur" and root["dex"] == 1
    mid = root["evolves_to"][0]
    assert mid["name"] == "ivysaur" and mid["dex"] == 2
    assert mid["evolves_to"][0]["name"] == "venusaur"


def test_evolution_chain_url_extraction() -> None:
    url = evolution_chain_url_from_species(_species_payload())
    assert url == "https://pokeapi.co/api/v2/evolution-chain/1/"

    assert evolution_chain_url_from_species({}) is None


def test_attach_evolution_returns_new_record() -> None:
    record = {"dex_number": 2, "evolution_json": "{}"}
    evolved = attach_evolution(record, {"chain": []})
    assert evolved["evolution_json"] != record["evolution_json"]
    assert record["evolution_json"] == "{}"  # 原记录不被修改


def test_parse_ability_details_prefers_zh_hans() -> None:
    from app.domain.pokemon_parser import parse_ability_details

    detail = parse_ability_details(
        {
            "name": "overgrow",
            "names": [
                {"name": "茂盛", "language": {"name": "zh-hant"}},
                {"name": "茂盛", "language": {"name": "zh-hans"}},
            ],
            "effect_entries": [
                {"short_effect": "Powers up Grass moves.", "language": {"name": "en"}}
            ],
            "flavor_text_entries": [
                {
                    "flavor_text": "ＨＰ減少的時候，\n草屬性的招式威力會提高。",
                    "language": {"name": "zh-hant"},
                },
                {
                    "flavor_text": "ＨＰ减少的时候，\n草属性的招式威力会提高。",
                    "language": {"name": "zh-hans"},
                },
            ],
        }
    )
    assert detail["zh"] == "茂盛"
    assert detail["effect_zh"] == "ＨＰ减少的时候， 草属性的招式威力会提高。"
    assert detail["effect_en"] == "Powers up Grass moves."


def test_extract_all_moves_groups_by_version_and_method() -> None:
    from app.domain.pokemon_parser import extract_all_moves

    payload = {
        "moves": [
            {
                "move": {"name": "tackle"},
                "version_group_details": [
                    {
                        "move_learn_method": {"name": "level-up"},
                        "level_learned_at": 1,
                        "version_group": {"name": "scarlet-violet"},
                    },
                    {
                        "move_learn_method": {"name": "level-up"},
                        "level_learned_at": 1,
                        "version_group": {"name": "red-blue"},
                    },
                ],
            },
            {
                "move": {"name": "growl"},
                "version_group_details": [
                    {
                        "move_learn_method": {"name": "level-up"},
                        "level_learned_at": 1,
                        "version_group": {"name": "scarlet-violet"},
                    }
                ],
            },
            {
                "move": {"name": "protect"},
                "version_group_details": [
                    {
                        "move_learn_method": {"name": "machine"},
                        "level_learned_at": 0,
                        "version_group": {"name": "scarlet-violet"},
                    }
                ],
            },
            {
                "move": {"name": "petal-dance"},
                "version_group_details": [
                    {
                        "move_learn_method": {"name": "egg"},
                        "level_learned_at": 0,
                        "version_group": {"name": "scarlet-violet"},
                    }
                ],
            },
        ]
    }
    groups = extract_all_moves(payload)

    sv = groups["scarlet-violet"]
    assert set(sv) == {"level-up", "machine", "egg"}
    # 升级招式按等级再按名称排序
    assert [m["name"] for m in sv["level-up"]] == ["growl", "tackle"]
    # 学习器 / 蛋招式按名称排序，等级为 0
    assert sv["machine"] == [{"name": "protect", "level": 0}]
    assert sv["egg"] == [{"name": "petal-dance", "level": 0}]
    # 旧版本组同样保留，不是只取最新
    assert [m["name"] for m in groups["red-blue"]["level-up"]] == ["tackle"]


def test_extract_all_moves_empty() -> None:
    from app.domain.pokemon_parser import extract_all_moves

    assert extract_all_moves({}) == {}
    assert extract_all_moves({"moves": []}) == {}


def test_pick_latest_version_group_and_collect_names() -> None:
    from app.domain.pokemon_parser import collect_move_names, pick_latest_version_group

    groups = {
        "red-blue": {"level-up": [{"name": "tackle", "level": 1}]},
        "scarlet-violet": {"machine": [{"name": "protect", "level": 0}]},
    }
    assert pick_latest_version_group(groups) == "scarlet-violet"
    assert pick_latest_version_group({}) is None
    assert collect_move_names(groups) == {"tackle", "protect"}


def test_evolution_detail_human_readable() -> None:
    chain_payload = {
        "id": 1,
        "chain": {
            "species": {"name": "bulbasaur", "url": "https://pokeapi.co/api/v2/pokemon-species/1/"},
            "evolves_to": [
                {
                    "species": {
                        "name": "ivysaur",
                        "url": "https://pokeapi.co/api/v2/pokemon-species/2/",
                    },
                    "evolution_details": [
                        {
                            "is_default": True,
                            "trigger": {"name": "level-up"},
                            "min_level": 16,
                        }
                    ],
                    "evolves_to": [],
                }
            ],
        },
    }
    tree = parse_evolution_chain(chain_payload, 1)
    assert tree["chain"]["detail"] is None
    assert tree["chain"]["evolves_to"][0]["detail"] == "等级 16"


def test_evolution_detail_item_and_friendship() -> None:
    chain_payload = {
        "id": 67,
        "chain": {
            "species": {"name": "eevee", "url": "https://pokeapi.co/api/v2/pokemon-species/133/"},
            "evolves_to": [
                {
                    "species": {
                        "name": "vaporeon",
                        "url": "https://pokeapi.co/api/v2/pokemon-species/134/",
                    },
                    "evolution_details": [
                        {
                            "is_default": True,
                            "trigger": {"name": "use-item"},
                            "item": {"name": "water-stone"},
                        }
                    ],
                    "evolves_to": [],
                },
                {
                    "species": {
                        "name": "espeon",
                        "url": "https://pokeapi.co/api/v2/pokemon-species/196/",
                    },
                    "evolution_details": [
                        {
                            "is_default": True,
                            "trigger": {"name": "level-up"},
                            "min_happiness": 160,
                            "time_of_day": "day",
                        }
                    ],
                    "evolves_to": [],
                },
            ],
        },
    }
    tree = parse_evolution_chain(chain_payload, 133)
    children = tree["chain"]["evolves_to"]
    assert children[0]["detail"] == "使用水之石"
    assert children[1]["detail"] == "亲密度 ≥ 160 · 白天"


def test_attach_moves_keeps_all_groups_and_methods() -> None:
    from app.domain.pokemon_parser import attach_moves

    record = {"dex_number": 1, "moves_json": "{}"}
    groups = {
        "scarlet-violet": {
            "level-up": [{"name": "tackle", "level": 1}],
            "machine": [{"name": "protect", "level": 0}],
            "egg": [{"name": "petal-dance", "level": 0}],
        },
        "red-blue": {"level-up": [{"name": "tackle", "level": 1}]},
    }
    result = attach_moves(record, groups)
    stored = json.loads(result["moves_json"])

    assert stored["default_version_group"] == "scarlet-violet"
    assert stored["version_group_label"] == "朱／紫"
    sv = stored["version_groups"]["scarlet-violet"]
    assert list(sv["methods"]) == ["level-up", "machine", "egg"]
    assert sv["methods"]["machine"] == [{"name": "protect", "level": 0}]
    assert "red-blue" in stored["version_groups"]
    assert record["moves_json"] == "{}"  # 原记录不被修改


def test_attach_moves_empty() -> None:
    from app.domain.pokemon_parser import attach_moves

    result = attach_moves({"moves_json": "{}"}, {})
    assert json.loads(result["moves_json"]) == {}
