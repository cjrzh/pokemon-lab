"""pokemon_parser 纯函数测试：用贴近 PokéAPI 真实结构的最小 payload。"""

from __future__ import annotations

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

    import json

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
    assert abilities[0] == {"name": "overgrow", "is_hidden": False, "zh": "茂盛"}
    assert abilities[1]["is_hidden"] is True


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
