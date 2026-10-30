"""特性接口测试：列表、详情（拥有者）、S 级筛选与人工评级。"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.repositories import pokemon_repo

ABILITIES_URL = "/api/v1/abilities"
ADMIN_URL = "/api/v1/admin"


def _seed_pokemon(dex: int, name_en: str, name_zh: str, types: list[str], abilities: list[dict]):
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_zh,
        types_json=json.dumps(types),
        stats_json=json.dumps({"hp": 50}),
        abilities_json=json.dumps(abilities),
        evolution_json="{}",
        moves_json="{}",
        generation_introduced=1,
        height_dm=10,
        weight_hg=100,
        source="pokeapi",
    )


async def _seed(client: AsyncClient) -> None:
    from app.db.engine import get_session_factory
    from app.services.ability_service import sync_abilities

    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                _seed_pokemon(
                    1,
                    "bulbasaur",
                    "妙蛙种子",
                    ["grass"],
                    [
                        {
                            "name": "overgrow",
                            "zh": "茂盛",
                            "is_hidden": False,
                            "effect_zh": "草系招式增强。",
                        },
                        {
                            "name": "chlorophyll",
                            "zh": "叶绿素",
                            "is_hidden": True,
                            "effect_zh": "晴天速度翻倍。",
                        },
                    ],
                ),
                _seed_pokemon(
                    4,
                    "charmander",
                    "小火龙",
                    ["fire"],
                    [
                        {
                            "name": "blaze",
                            "zh": "猛火",
                            "is_hidden": False,
                            "effect_zh": "火系招式增强。",
                        }
                    ],
                ),
            ]
        )
        await session.flush()
        # 特性参考表由同步服务汇总；测试里手动触发一次
        await sync_abilities(session)
        await session.commit()


async def test_list_abilities_returns_aggregated_abilities(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(ABILITIES_URL)).json()

    names = [item["name"] for item in payload["items"]]
    assert set(names) == {"overgrow", "chlorophyll", "blaze"}
    assert payload["meta"]["total"] == 3
    # 未评级前默认普通
    assert all(item["tier"] == "normal" for item in payload["items"])


async def test_ability_detail_lists_holders(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{ABILITIES_URL}/chlorophyll")).json()

    assert payload["zh"] == "叶绿素"
    assert payload["holders"] == [
        {
            "dex_number": 1,
            "name_zh": "妙蛙种子",
            "name_en": "bulbasaur",
            "types": ["grass"],
            "is_hidden": True,
            "is_legendary": False,
            "is_mythical": False,
            # 本地没有小图标缓存 → 回落远程代理地址
            "sprite_url": (
                "https://wsrv.nl/?url=raw.githubusercontent.com/PokeAPI/sprites/"
                "master/sprites/pokemon/1.png"
            ),
        }
    ]


async def test_ability_holder_uses_local_sprite_when_cached(client: AsyncClient) -> None:
    """拥有本地小图标时返回 /media/sprites 路径（离线可用）。"""
    await _seed(client)
    from sqlalchemy import select

    from app.db.engine import get_session_factory
    from app.db.models import Pokemon

    factory = get_session_factory()
    async with factory() as session:
        pokemon = (
            await session.execute(select(Pokemon).where(Pokemon.dex_number == 1))
        ).scalar_one()
        pokemon.sprite_path = "sprites/1.png"
        await session.commit()

    payload = (await client.get(f"{ABILITIES_URL}/chlorophyll")).json()
    assert payload["holders"][0]["sprite_url"] == "/media/sprites/1.png"


async def test_ability_404(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.get(f"{ABILITIES_URL}/nonexistent")
    assert response.status_code == 404


async def test_admin_can_rate_ability_s_tier(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.put(
        f"{ADMIN_URL}/abilities/overgrow",
        json={"tier": "s", "note": "测试评级"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tier"] == "s"
    assert payload["rating_source"] == "manual"
    assert payload["rating_note"] == "测试评级"

    # 列表里 S 级排在前面
    listing = (await client.get(ABILITIES_URL, params={"tier": "s"})).json()
    assert [item["name"] for item in listing["items"]] == ["overgrow"]

    # 操作日志已记录
    logs = (await client.get(f"{ADMIN_URL}/ops")).json()["items"]
    assert logs[0]["action"] == "ability.rate"


async def test_admin_rate_rejects_invalid_tier(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.put(
        f"{ADMIN_URL}/abilities/overgrow", json={"tier": "ss"}
    )
    assert response.status_code == 422


async def test_manual_rating_survives_automatic_sync(client: AsyncClient) -> None:
    """人工评级后，重新汇总特性（自动评级）不会覆盖 manual。"""
    await _seed(client)
    await client.put(f"{ADMIN_URL}/abilities/blaze", json={"tier": "s", "note": "人工"})

    from app.db.engine import get_session_factory
    from app.services.ability_service import sync_abilities

    factory = get_session_factory()
    async with factory() as session:
        await sync_abilities(session)
        await session.commit()

    payload = (await client.get(f"{ABILITIES_URL}/blaze")).json()
    assert payload["tier"] == "s"
    assert payload["rating_source"] == "manual"
