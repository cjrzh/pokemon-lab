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


async def _set_stats(dex: int, stats: dict[str, int], types: list[str] | None = None) -> None:
    """直接改种子记录的种族值 / 属性（经仓储，避免绕到管理接口）。"""
    from sqlalchemy import select

    from app.db.engine import get_session_factory
    from app.db.models import Pokemon

    factory = get_session_factory()
    async with factory() as session:
        pokemon = (
            await session.execute(select(Pokemon).where(Pokemon.dex_number == dex))
        ).scalar_one()
        pokemon.stats_json = json.dumps(stats)
        if types is not None:
            pokemon.types_json = json.dumps(types)
        await session.commit()


async def test_list_pokemon_sorted_by_stats(client: AsyncClient) -> None:
    """种族值排序：筛选之后对结果子集整体排序，再分页。"""
    await _seed(client)
    # 三条种子记录种族值相同（318），同分按图鉴编号
    payload = (await client.get(POKEMON_URL, params={"sort": "total_stats"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [1, 4, 7]

    await _set_stats(
        4,
        {
            "hp": 39,
            "attack": 52,
            "defense": 43,
            "special-attack": 60,
            "special-defense": 50,
            "speed": 65,
        },
    )
    await _set_stats(
        7,
        {
            "hp": 44,
            "attack": 48,
            "defense": 65,
            "special-attack": 50,
            "special-defense": 64,
            "speed": 43,
        },
    )

    # 合计：小火龙 309 < 杰尼龟 314 < 妙蛙种子 318
    payload = (await client.get(POKEMON_URL, params={"sort": "total_stats"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [1, 7, 4]

    payload = (await client.get(POKEMON_URL, params={"sort": "total_stats_asc"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [4, 7, 1]

    payload = (await client.get(POKEMON_URL, params={"sort": "dex_desc"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [7, 4, 1]


async def test_list_pokemon_sort_applies_after_filters(client: AsyncClient) -> None:
    """属性筛选后的子列表按种族值排序。"""
    await _seed(client)
    await _set_stats(1, {"hp": 45, "attack": 49})  # 合计 94
    await _set_stats(4, {"hp": 39, "attack": 52})  # 合计 91
    await _set_stats(7, {"hp": 44, "attack": 48}, types=["fire", "water"])  # 合计 92

    # 火属性命中另外两只；结果集按合计排序：[7]=92 → [4]=91
    payload = (await client.get(POKEMON_URL, params={"type": "fire", "sort": "total_stats"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [7, 4]

    payload = (
        await client.get(POKEMON_URL, params={"type": "fire", "sort": "total_stats_asc"})
    ).json()
    assert [i["dex_number"] for i in payload["items"]] == [4, 7]


async def test_list_pokemon_rejects_unknown_sort(client: AsyncClient) -> None:
    assert (await client.get(POKEMON_URL, params={"sort": "nope"})).status_code == 422


async def test_list_pokemon_stats_sort_puts_empty_stats_last(client: AsyncClient) -> None:
    """没有种族值的记录不参与排名，升序降序都排在最后。"""
    await _seed(client)
    from app.db.engine import get_session_factory
    from app.db.models import Pokemon

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            Pokemon(
                dex_number=999,
                name_en="mystery",
                name_zh="未知",
                types_json=json.dumps(["normal"]),
                stats_json="{}",
                abilities_json="[]",
                evolution_json="{}",
                moves_json="{}",
                source="manual",
            )
        )
        await session.commit()

    payload = (await client.get(POKEMON_URL, params={"sort": "total_stats"})).json()
    assert payload["items"][-1]["dex_number"] == 999
    payload = (await client.get(POKEMON_URL, params={"sort": "total_stats_asc"})).json()
    assert payload["items"][-1]["dex_number"] == 999


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
    assert payload["default_range"] == {"start": 1, "end": 1025}


async def test_admin_sync_rejects_out_of_dex_range(client: AsyncClient) -> None:
    # 全国图鉴之外（10001+）直接拒绝；范围内的大区间（如全国 1025 只）允许，
    # 由 admin 路由按世代分批引导。
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

    ability_payload = {
        "name": "static",
        "names": [{"name": "静电", "language": {"name": "zh-hans"}}],
        "effect_entries": [
            {"short_effect": "May paralyze on contact.", "language": {"name": "en"}}
        ],
        "flavor_text_entries": [
            {"flavor_text": "身上帶有靜電。", "language": {"name": "zh-hant"}},
            {"flavor_text": "身上带有静电。", "language": {"name": "zh-hans"}},
        ],
    }
    move_payload = {
        "name": "thunder-shock",
        "names": [{"name": "电击", "language": {"name": "zh-hans"}}],
        "type": {"name": "electric"},
        "damage_class": {"name": "special"},
        "power": 40,
        "accuracy": 100,
        "pp": 30,
    }
    # 招式表里补充一条升级招式，验证 moves 链路（真实 payload 也带 moves）
    pokemon_payload["moves"] = [
        {
            "move": {"name": "thunder-shock"},
            "version_group_details": [
                {
                    "move_learn_method": {"name": "level-up"},
                    "level_learned_at": 1,
                    "version_group": {"name": "scarlet-violet"},
                }
            ],
        }
    ]

    async def fake_fetch_json(session, path, **kwargs):
        payload = {
            "/pokemon/25": pokemon_payload,
            "/pokemon-species/25": species_payload,
            "/evolution-chain/10": chain_payload,
            "/ability/static": ability_payload,
            "/move/thunder-shock": move_payload,
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
    # 特性：中文名与说明来自 /ability
    assert detail["abilities"][0]["zh"] == "静电"
    assert detail["abilities"][0]["effect_zh"] == "身上带有静电。"
    # 招式：按版本组 + 学习方式分组，数值来自共享的 move_ref
    moves = detail["moves"]
    assert moves["default_version_group"] == "scarlet-violet"
    groups = {g["version_group"]: g for g in moves["version_groups"]}
    assert "scarlet-violet" in groups
    methods = {m["method"]: m for m in groups["scarlet-violet"]["methods"]}
    assert methods["level-up"]["label"] == "升级"
    assert methods["level-up"]["moves"][0] == {
        "name": "thunder-shock",
        "zh": "电击",
        "level": 1,
        "type": "electric",
        "damage_class": "special",
        "damage_class_zh": "特殊",
        "power": 40,
        "accuracy": 100,
        "pp": 30,
        "description_zh": None,
    }


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


# ---------- P2 打磨：图片 / 图鉴档案 / 招式 ----------


def _seed_enriched_record(dex: int = 1) -> dict:
    return {
        "dex_number": dex,
        "name_en": "bulbasaur",
        "name_zh": "妙蛙种子",
        "name_ja": "フシギダネ",
        "types_json": json.dumps(["grass", "poison"]),
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
        "abilities_json": json.dumps(
            [
                {
                    "name": "overgrow",
                    "is_hidden": False,
                    "zh": "茂盛",
                    "effect_zh": "ＨＰ减少的时候，草属性的招式威力会提高。",
                    "effect_en": "Powers up Grass moves.",
                }
            ]
        ),
        "evolution_json": json.dumps(
            {
                "chain_id": "1",
                "chain": {
                    "name": "bulbasaur",
                    "dex": 1,
                    "detail": None,
                    "evolves_to": [
                        {
                            "name": "ivysaur",
                            "dex": 2,
                            "detail": "等级 16",
                            "evolves_to": [],
                        }
                    ],
                },
            }
        ),
        "moves_json": json.dumps(
            {
                "default_version_group": "scarlet-violet",
                "version_group_label": "朱／紫",
                "version_groups": {
                    "scarlet-violet": {
                        "label": "朱／紫",
                        "methods": {
                            "level-up": [{"name": "tackle", "level": 1}],
                            "machine": [{"name": "protect", "level": 0}],
                            "egg": [{"name": "petal-dance", "level": 0}],
                        },
                    }
                },
            }
        ),
        "genus_zh": "种子宝可梦",
        "genus_en": "Seed Pokémon",
        "flavor_zh": "背上的种子里储存着营养。",
        "flavor_en": "A strange seed was planted on its back.",
        "artwork_path": "artwork/1.png",
        "artwork_url": "https://assets.pokemon.com/assets/cms2/img/pokedex/full/001.png",
        "sprite_url": "https://wsrv.nl/?url=example/1.png",
        "is_legendary": False,
        "gender_rate": 1,
        "capture_rate": 45,
        "base_happiness": 70,
        "hatch_counter": 20,
        "growth_rate": "medium-slow",
        "habitat": "grassland",
        "color": "green",
        "shape": "quadruped",
        "egg_groups_json": json.dumps(["monster", "plant"]),
        "generation_introduced": 1,
        "height_dm": 7,
        "weight_hg": 69,
        "source": "pokeapi",
    }


async def _seed_enriched(client: AsyncClient) -> None:
    from app.db.engine import get_session_factory
    from app.db.models import MoveReference

    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                MoveReference(
                    name="tackle",
                    zh="撞击",
                    type="normal",
                    damage_class="physical",
                    power=40,
                    accuracy=100,
                    pp=35,
                    description_zh="用整个身体撞向对手进行攻击。",
                ),
                MoveReference(
                    name="protect",
                    zh="守住",
                    type="normal",
                    damage_class="status",
                    power=None,
                    accuracy=None,
                    pp=10,
                ),
            ]
        )
        session.add(pokemon_repo.Pokemon(**_seed_enriched_record(1)))
        session.add(
            pokemon_repo.Pokemon(
                **{
                    **_seed_enriched_record(2),
                    "name_en": "ivysaur",
                    "name_zh": "妙蛙草",
                    "name_ja": None,
                    "artwork_path": None,
                }
            )
        )
        await session.commit()


async def test_list_pokemon_includes_artwork_and_total_stats(client: AsyncClient) -> None:
    await _seed_enriched(client)
    payload = (await client.get(POKEMON_URL, params={"q": "妙蛙种子"})).json()

    item = payload["items"][0]
    assert item["name_ja"] == "フシギダネ"
    assert item["total_stats"] == 318
    # 有本地缓存时用 /media 托管地址
    assert item["artwork_url"] == "/media/artwork/1.png"
    assert item["artwork_fallback_url"].startswith("https://wsrv.nl/")
    # 小图标：没有本地缓存时回落远程小图（96×96，与立绘分开）
    assert item["sprite_url"] == (
        "https://wsrv.nl/?url=raw.githubusercontent.com/PokeAPI/sprites/"
        "master/sprites/pokemon/1.png"
    )


async def test_list_pokemon_uses_local_sprite_when_cached(client: AsyncClient) -> None:
    """本地有小图标缓存时返回 /media/sprites 路径（离线可用）。"""
    await _seed_enriched(client)
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

    payload = (await client.get(POKEMON_URL, params={"q": "妙蛙种子"})).json()
    assert payload["items"][0]["sprite_url"] == "/media/sprites/1.png"


async def test_list_pokemon_falls_back_to_remote_artwork(client: AsyncClient) -> None:
    await _seed_enriched(client)
    payload = (await client.get(POKEMON_URL, params={"q": "ivysaur"})).json()
    item = payload["items"][0]
    # 没有本地缓存 → pokemon.com 远程地址
    assert item["artwork_url"] == "https://assets.pokemon.com/assets/cms2/img/pokedex/full/001.png"


async def test_detail_includes_profile_moves_and_neighbors(client: AsyncClient) -> None:
    await _seed_enriched(client)
    payload = (await client.get(f"{POKEMON_URL}/1")).json()

    assert payload["genus_zh"] == "种子宝可梦"
    assert payload["flavor_zh"] == "背上的种子里储存着营养。"
    assert payload["capture_rate"] == 45
    assert payload["gender_rate"] == 1
    assert payload["egg_groups"] == ["monster", "plant"]
    assert payload["total_stats"] == 318

    assert payload["abilities"][0]["effect_zh"].startswith("ＨＰ减少")

    moves = payload["moves"]
    assert moves["default_version_group"] == "scarlet-violet"
    group = moves["version_groups"][0]
    assert group["label"] == "朱／紫"
    assert [m["method"] for m in group["methods"]] == ["level-up", "machine", "egg"]
    assert [m["label"] for m in group["methods"]] == ["升级", "招式学习器", "蛋招式"]
    level_up = group["methods"][0]["moves"][0]
    assert level_up["zh"] == "撞击"
    assert level_up["power"] == 40
    # 学习器招式：数值从 move_ref 合并，未收录的蛋招式字段为 None
    assert group["methods"][1]["moves"][0]["zh"] == "守住"
    assert group["methods"][2]["moves"][0]["zh"] is None

    # 进化链补上中文名与条件
    chain = payload["evolution"]["chain"]
    assert chain["zh"] == "妙蛙种子"
    assert chain["evolves_to"][0]["zh"] == "妙蛙草"
    assert chain["evolves_to"][0]["detail"] == "等级 16"

    assert payload["prev"] is None
    assert payload["next"] == {"dex_number": 2, "name_zh": "妙蛙草", "name_en": "ivysaur"}


async def test_detail_evolution_without_synced_form_keeps_english(client: AsyncClient) -> None:
    """进化后形态未同步时不给中文名，避免虚构翻译。"""
    from app.db.engine import get_session_factory

    record = _seed_enriched_record(1)
    record["evolution_json"] = json.dumps(
        {
            "chain": {
                "name": "bulbasaur",
                "dex": 1,
                "detail": None,
                "evolves_to": [
                    {"name": "venusaur", "dex": 3, "detail": "等级 32", "evolves_to": []}
                ],
            }
        }
    )
    factory = get_session_factory()
    async with factory() as session:
        session.add(pokemon_repo.Pokemon(**record))
        await session.commit()

    payload = (await client.get(f"{POKEMON_URL}/1")).json()
    child = payload["evolution"]["chain"]["evolves_to"][0]
    assert child["zh"] is None
    assert child["name"] == "venusaur"


async def test_media_static_mount_serves_cached_artwork(client: AsyncClient, var_dir) -> None:
    """立绘写入 media/artwork 后能通过 /media 访问（离线可用）。"""
    from app.core.config import get_settings

    settings = get_settings()
    target = settings.artwork_dir / "1.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    response = await client.get("/media/artwork/1.png")
    assert response.status_code == 200
    assert response.content.startswith(b"\x89PNG")


async def test_detail_returns_all_version_groups_and_learn_methods(client: AsyncClient) -> None:
    """招式不只返回升级：同一版本组内的学习器 / 蛋招式 / 教学都要在。

    同时验证版本组按「新 → 旧」排列，默认版本组仍是可用的最新作品。
    """
    from app.db.engine import get_session_factory
    from app.db.models import MoveReference

    record = _seed_enriched_record(1)
    record["moves_json"] = json.dumps(
        {
            "default_version_group": "scarlet-violet",
            "version_group_label": "朱／紫",
            "version_groups": {
                "red-blue": {
                    "label": "红／蓝",
                    "methods": {"level-up": [{"name": "tackle", "level": 1}]},
                },
                "scarlet-violet": {
                    "label": "朱／紫",
                    "methods": {
                        "level-up": [{"name": "tackle", "level": 1}],
                        "machine": [{"name": "protect", "level": 0}],
                        "egg": [{"name": "petal-dance", "level": 0}],
                        "tutor": [{"name": "body-slam", "level": 0}],
                    },
                },
            },
        }
    )
    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                MoveReference(
                    name="tackle", zh="撞击", type="normal", damage_class="physical", power=40
                ),
                MoveReference(
                    name="protect", zh="守住", type="normal", damage_class="status", pp=10
                ),
                MoveReference(
                    name="petal-dance",
                    zh="花瓣舞",
                    type="grass",
                    damage_class="special",
                    power=120,
                ),
                MoveReference(
                    name="body-slam",
                    zh="泰山压顶",
                    type="normal",
                    damage_class="physical",
                    power=85,
                ),
            ]
        )
        session.add(pokemon_repo.Pokemon(**record))
        await session.commit()

    payload = (await client.get(f"{POKEMON_URL}/1")).json()
    moves = payload["moves"]

    # 新作品在前
    assert [g["version_group"] for g in moves["version_groups"]] == [
        "scarlet-violet",
        "red-blue",
    ]
    sv = moves["version_groups"][0]
    # 学习方式按「升级 → 学习器 → 教学 → 蛋招式」排序
    assert [m["method"] for m in sv["methods"]] == ["level-up", "machine", "tutor", "egg"]
    assert [m["label"] for m in sv["methods"]] == ["升级", "招式学习器", "教学", "蛋招式"]
    assert sv["methods"][3]["moves"][0]["zh"] == "花瓣舞"


# ---------- 全国图鉴（Gen 1–9） ----------


async def test_list_pokemon_search_by_dex_number(client: AsyncClient) -> None:
    """纯数字输入按图鉴编号精确匹配（支持「025」这种补零写法）。"""
    await _seed(client)
    payload = (await client.get(POKEMON_URL, params={"q": "004"})).json()
    assert [i["dex_number"] for i in payload["items"]] == [4]

    # 中文名里含数字不会误伤；不存在的编号返回空
    payload = (await client.get(POKEMON_URL, params={"q": "9999"})).json()
    assert payload["items"] == []


async def test_admin_sync_status_per_generation(client: AsyncClient) -> None:
    """分世代覆盖统计以 generation_introduced 聚合。"""
    await _seed(client)  # 三条都是第 1 世代
    payload = (await client.get(f"{ADMIN_URL}/pokemon/sync/status")).json()
    assert payload["per_generation"] == {"1": 3}
