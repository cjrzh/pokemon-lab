"""图鉴公开接口与管理接口测试。

管理接口的同步测试通过替换 `dex_sync_service.fetch_json` 模拟 PokéAPI
（patch 服务模块的名字绑定，不劫持全局 httpx.AsyncClient），不打真实网络。
种子几条 pokemon 记录直接经仓储写入。
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.repositories import pokemon_repo
from tests.test_pokeapi_client import FetchResultStub

POKEMON_URL = "/api/v1/pokemon"
ADMIN_URL = "/api/v1/admin"


def _seed_record(dex: int, name_en: str, name_zh: str, types: list[str]) -> dict:
    return {
        "dex_number": dex,
        "name_en": name_en,
        "name_zh": name_zh,
        "types_json": json.dumps(types),
        "stats_json": json.dumps(
            {
                "hp": 45,
                "attack": 49,
                "defense": 49,
                "special-attack": 65,
                "special-defense": 65,
                "speed": 45,
            }
        ),
        "abilities_json": json.dumps([{"name": "overgrow", "is_hidden": False, "zh": "茂盛"}]),
        "evolution_json": json.dumps({}),
        "generation_introduced": 1,
        "height_dm": 7,
        "weight_hg": 69,
        "source": "pokeapi",
    }


async def _seed(client: AsyncClient) -> None:
    """经仓储写入三条种子数据（绕过接口，专注测接口行为）。"""
    from app.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                pokemon_repo.Pokemon(**_seed_record(*args))
                for args in [
                    (1, "bulbasaur", "妙蛙种子", ["grass", "poison"]),
                    (4, "charmander", "小火龙", ["fire"]),
                    (7, "squirtle", "杰尼龟", ["water"]),
                ]
            ]
        )
        await session.commit()


async def test_list_pokemon_pagination_and_order(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.get(POKEMON_URL, params={"page": 1, "page_size": 2})

    assert response.status_code == 200
    payload = response.json()
    assert [i["dex_number"] for i in payload["items"]] == [1, 4]
    assert payload["meta"]["total"] == 3
    assert payload["meta"]["total_pages"] == 2


async def test_list_pokemon_search_zh_and_en(client: AsyncClient) -> None:
    await _seed(client)
    # 中文名搜索
    payload = (await client.get(POKEMON_URL, params={"q": "小火"})).json()
    assert [i["name_zh"] for i in payload["items"]] == ["小火龙"]

    # 英文名搜索（不区分大小写）
    payload = (await client.get(POKEMON_URL, params={"q": "BULB"})).json()
    assert [i["name_en"] for i in payload["items"]] == ["bulbasaur"]


async def test_list_pokemon_type_filter(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(POKEMON_URL, params={"type": "fire"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [4]

    # 复合属性也应命中
    payload = (await client.get(POKEMON_URL, params={"type": "poison"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [1]


async def test_list_pokemon_rejects_unknown_type(client: AsyncClient) -> None:
    response = await client.get(POKEMON_URL, params={"type": "shadow"})
    assert response.status_code == 422


async def test_list_pokemon_empty_state(client: AsyncClient) -> None:
    """无数据时返回空列表而非错误 —— 前端空态渲染的依据。"""
    payload = (await client.get(POKEMON_URL)).json()
    assert payload["items"] == []
    assert payload["meta"]["total"] == 0


async def test_get_pokemon_detail(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.get(f"{POKEMON_URL}/4")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name_zh"] == "小火龙"
    assert payload["types"] == ["fire"]
    assert payload["stats"]["hp"] == 39 or payload["stats"]["hp"] == 45  # 种子值
    assert payload["abilities"][0]["name"] == "overgrow"
    assert payload["source_label"] == "PokéAPI 同步"
    assert payload["is_demo"] is False


async def test_get_pokemon_detail_404(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.get(f"{POKEMON_URL}/999")
    assert response.status_code == 404
    assert "尚未同步" in response.json()["detail"]


# ---------- 管理接口 ----------


async def test_admin_edit_marks_source_manual(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.put(
        f"{ADMIN_URL}/pokemon/4",
        json={"name_zh": "小火龙（修正）", "types": ["fire", "flying"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name_zh"] == "小火龙（修正）"
    assert payload["source"] == "manual"
    assert payload["source_label"] == "手动维护"

    # 操作日志已记录
    logs = (await client.get(f"{ADMIN_URL}/ops")).json()["items"]
    assert logs[0]["action"] == "pokemon.edit"
    assert logs[0]["target"] == "#4"


async def test_admin_edit_404_and_empty_body(client: AsyncClient) -> None:
    await _seed(client)
    assert (await client.put(f"{ADMIN_URL}/pokemon/999", json={"name_zh": "x"})).status_code == 404
    response = await client.put(f"{ADMIN_URL}/pokemon/4", json={})
    assert response.status_code == 422


async def test_admin_edit_rejects_invalid_type(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.put(f"{ADMIN_URL}/pokemon/4", json={"types": ["shadow"]})
    assert response.status_code == 422


async def test_admin_create_manual_and_conflict(client: AsyncClient) -> None:
    await _seed(client)

    response = await client.post(
        f"{ADMIN_URL}/pokemon",
        json={
            "dex_number": 25,
            "name_en": "pikachu",
            "name_zh": "皮卡丘",
            "types": ["electric"],
            "is_demo": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["source"] == "manual"

    # dex 冲突 → 409
    response = await client.post(
        f"{ADMIN_URL}/pokemon",
        json={"dex_number": 25, "name_en": "pikachu-dup"},
    )
    assert response.status_code == 409


async def test_admin_sync_status(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{ADMIN_URL}/pokemon/sync/status")).json()

    assert payload["total"] == 3
    assert payload["from_pokeapi"] == 3
    assert payload["from_manual"] == 0
    assert payload["default_range"] == {"start": 1, "end": 151}


async def test_admin_sync_rejects_oversized_range(client: AsyncClient) -> None:
    response = await client.post(f"{ADMIN_URL}/pokemon/sync", json={"start": 1, "end": 10000})
    assert response.status_code == 422


async def test_admin_trigger_sync_with_mock_upstream(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mock PokéAPI：同步 #25 皮卡丘，验证落库与结果汇总。"""
    pokemon_payload = {
        "id": 25,
        "name": "pikachu",
        "height": 4,
        "weight": 60,
        "types": [{"slot": 1, "type": {"name": "electric"}}],
        "stats": [
            {"base_stat": 35, "stat": {"name": "hp"}},
            {"base_stat": 55, "stat": {"name": "attack"}},
            {"base_stat": 40, "stat": {"name": "defense"}},
            {"base_stat": 50, "stat": {"name": "special-attack"}},
            {"base_stat": 50, "stat": {"name": "special-defense"}},
            {"base_stat": 90, "stat": {"name": "speed"}},
        ],
        "abilities": [{"is_hidden": False, "ability": {"name": "static"}}],
    }
    species_payload = {
        "id": 25,
        "name": "pikachu",
        "names": [{"name": "皮卡丘", "language": {"name": "zh-hans"}}],
        "generation": {"name": "generation-i"},
        "evolution_chain": {"url": "https://pokeapi.co/api/v2/evolution-chain/10/"},
    }
    chain_payload = {
        "id": 10,
        "chain": {
            "species": {"name": "pichu", "url": "https://pokeapi.co/api/v2/pokemon-species/172/"},
            "evolves_to": [
                {
                    "species": {
                        "name": "pikachu",
                        "url": "https://pokeapi.co/api/v2/pokemon-species/25/",
                    },
                    "evolves_to": [],
                },
            ],
        },
    }

    async def fake_fetch_json(session, path, **kwargs):
        payload = {
            "/pokemon/25": pokemon_payload,
            "/pokemon-species/25": species_payload,
            "/evolution-chain/10": chain_payload,
        }.get(path)
        if payload is None:
            raise pytest.fail(f"unexpected upstream path: {path}")
        return FetchResultStub(payload=json.dumps(payload), cache_state="miss")

    monkeypatch.setattr("app.services.dex_sync_service.fetch_json", fake_fetch_json)

    response = await client.post(f"{ADMIN_URL}/pokemon/sync", json={"start": 25, "end": 25})

    assert response.status_code == 200
    payload = response.json()
    assert payload["synced_count"] == 1
    assert payload["failed"] == {}

    # 落库可查
    detail = (await client.get(f"{POKEMON_URL}/25")).json()
    assert detail["name_zh"] == "皮卡丘"
    assert detail["types"] == ["electric"]
    assert detail["evolution"]["chain"]["evolves_to"][0]["dex"] == 25


async def test_admin_sync_skips_manual_records(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """手动编辑过的记录，同步默认跳过（且不发起上游请求）。"""
    await _seed(client)
    # 先把 #4 标记为手动
    await client.put(f"{ADMIN_URL}/pokemon/4", json={"name_zh": "小火龙（手动）"})

    async def fail_if_called(session, path, **kwargs):
        raise AssertionError("跳过的记录不应发起上游请求")

    monkeypatch.setattr("app.services.dex_sync_service.fetch_json", fail_if_called)

    response = await client.post(f"{ADMIN_URL}/pokemon/sync", json={"start": 4, "end": 4})
    payload = response.json()
    assert payload["skipped_manual"] == [4]
    assert payload["synced_count"] == 0

    # 手动值未被覆盖
    detail = (await client.get(f"{POKEMON_URL}/4")).json()
    assert detail["name_zh"] == "小火龙（手动）"
