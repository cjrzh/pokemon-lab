"""形态接口测试：详情里的形态菜单、形态详情与 404。"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.db.models import PokemonForm
from app.repositories import pokemon_repo

POKEMON_URL = "/api/v1/pokemon"


def _seed_pokemon() -> pokemon_repo.Pokemon:
    return pokemon_repo.Pokemon(
        dex_number=892,
        name_en="urshifu-single-strike",
        name_zh="武道熊师",
        types_json=json.dumps(["fighting", "dark"]),
        stats_json=json.dumps(
            {
                "hp": 100,
                "attack": 130,
                "defense": 100,
                "special-attack": 63,
                "special-defense": 60,
                "speed": 97,
            }
        ),
        abilities_json=json.dumps([{"name": "unseen-fist", "is_hidden": False, "zh": "无形拳"}]),
        evolution_json="{}",
        moves_json="{}",
        height_dm=19,
        weight_hg=1050,
        source="pokeapi",
        sprite_path="sprites/892.png",
    )


def _seed_form() -> PokemonForm:
    return PokemonForm(
        name="urshifu-rapid-strike",
        dex_number=892,
        suffix="rapid-strike",
        zh="连击流",
        name_en_label="Rapid Strike Urshifu",
        types_json=json.dumps(["fighting", "water"]),
        stats_json=json.dumps(
            {
                "hp": 100,
                "attack": 130,
                "defense": 100,
                "special-attack": 63,
                "special-defense": 60,
                "speed": 97,
            }
        ),
        abilities_json=json.dumps([{"name": "unseen-fist", "is_hidden": False}]),
        height_dm=19,
        weight_hg=1050,
        artwork_path="forms/artwork/urshifu-rapid-strike.png",
        sprite_path="forms/sprites/urshifu-rapid-strike.png",
        position=1,
    )


async def _seed(client: AsyncClient) -> None:
    from app.services.ability_service import sync_abilities

    factory = get_session_factory()
    async with factory() as session:
        session.add(_seed_pokemon())
        await session.flush()
        await sync_abilities(session)
        session.add(_seed_form())
        await session.commit()


async def test_detail_lists_forms_with_default_first(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{POKEMON_URL}/892")).json()

    forms = payload["forms"]
    assert [form["name"] for form in forms] == [
        "urshifu-single-strike",
        "urshifu-rapid-strike",
    ]
    default, rapid = forms
    assert default["is_default"] is True
    assert default["label"] == "武道熊师"
    assert default["types"] == ["fighting", "dark"]
    assert default["sprite_url"] == "/media/sprites/892.png"

    assert rapid["is_default"] is False
    assert rapid["label"] == "连击流"
    assert rapid["types"] == ["fighting", "water"]
    assert rapid["sprite_url"] == "/media/forms/sprites/urshifu-rapid-strike.png"


async def test_detail_without_forms_returns_empty_menu(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add(_seed_pokemon())
        await session.commit()

    payload = (await client.get(f"{POKEMON_URL}/892")).json()
    assert payload["forms"] == []


async def test_form_detail_returns_types_and_stats(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{POKEMON_URL}/892/forms/urshifu-rapid-strike")).json()

    assert payload["dex_number"] == 892
    assert payload["label"] == "连击流"
    assert payload["types"] == ["fighting", "water"]
    assert payload["stats"]["attack"] == 130
    assert payload["total_stats"] == 550
    assert payload["abilities"][0]["name"] == "unseen-fist"
    assert payload["artwork_url"] == "/media/forms/artwork/urshifu-rapid-strike.png"
    assert payload["is_default"] is False


async def test_default_form_detail_matches_pokemon(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{POKEMON_URL}/892/forms/default")).json()

    assert payload["is_default"] is True
    assert payload["name"] == "urshifu-single-strike"
    assert payload["types"] == ["fighting", "dark"]
    assert payload["sprite_url"] == "/media/sprites/892.png"


async def test_form_detail_404_for_unknown_or_wrong_dex(client: AsyncClient) -> None:
    await _seed(client)

    assert (await client.get(f"{POKEMON_URL}/892/forms/rotom-wash")).status_code == 404
    assert (await client.get(f"{POKEMON_URL}/999/forms/urshifu-rapid-strike")).status_code == 404


async def test_form_only_ability_gets_reference_translation(client: AsyncClient) -> None:
    """形态独有特性（蕾冠王的「人马一体」）也要有中文名与说明。

    回归点：`pokemon.abilities_json` 里没有这个特性（它只属于形态），
    旧实现只扫宝可梦表，参考表里就只有 slug，页面显示不出中文。
    """
    from app.services.ability_service import sync_abilities

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            pokemon_repo.Pokemon(
                dex_number=898,
                name_en="calyrex",
                name_zh="蕾冠王",
                types_json=json.dumps(["psychic", "grass"]),
                stats_json=json.dumps({"hp": 100, "attack": 80, "defense": 80,
                                       "special-attack": 80, "special-defense": 80,
                                       "speed": 80}),
                abilities_json=json.dumps(
                    [{"name": "unnerve", "is_hidden": False, "zh": "紧张感"}]
                ),
                evolution_json="{}",
                moves_json="{}",
                source="pokeapi",
            )
        )
        session.add(
            PokemonForm(
                name="calyrex-ice",
                dex_number=898,
                suffix="ice",
                zh="骑白马的样子",
                name_en_label="Ice Rider Calyrex",
                types_json=json.dumps(["psychic", "ice"]),
                stats_json=json.dumps({"hp": 100, "attack": 165, "defense": 150,
                                       "special-attack": 85, "special-defense": 130,
                                       "speed": 50}),
                # 形态表里只有 slug，没有中文
                abilities_json=json.dumps([{"name": "as-one-glastrier", "is_hidden": False}]),
                position=1,
            )
        )
        await session.flush()
        await sync_abilities(session)
        await session.commit()

    payload = (await client.get(f"{POKEMON_URL}/898/forms/calyrex-ice")).json()
    ability = payload["abilities"][0]
    assert ability["name"] == "as-one-glastrier"
    # 中文名与说明必须从参考表 / 译文补上，不能只剩 slug
    assert ability["zh"] == "人马一体"
    assert ability["effect_zh"] and "紧张感" in ability["effect_zh"]
