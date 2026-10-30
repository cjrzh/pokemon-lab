"""招式百科接口测试：列表筛选 / 排序、详情学习者与双向链接所需字段。"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.repositories import pokemon_repo
from app.services.move_service import rebuild_move_index

MOVES_URL = "/api/v1/moves"


def _moves_json(groups: dict) -> str:
    """构造 moves_json：{version_group: {method: [(name, level)]}}。"""
    version_groups = {}
    for version_group, methods in groups.items():
        version_groups[version_group] = {
            "methods": {
                method: [{"name": name, "level": level} for name, level in entries]
                for method, entries in methods.items()
            }
        }
    return json.dumps({"version_groups": version_groups}, ensure_ascii=False)


def _seed_pokemon(dex: int, name_en: str, name_zh: str, types: list[str], moves_json: str):
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_zh,
        types_json=json.dumps(types),
        stats_json=json.dumps({"hp": 50}),
        abilities_json="[]",
        evolution_json="{}",
        moves_json=moves_json,
        source="pokeapi",
    )


async def _seed(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                _seed_pokemon(
                    1,
                    "bulbasaur",
                    "妙蛙种子",
                    ["grass", "poison"],
                    _moves_json(
                        {
                            "scarlet-violet": {
                                "level-up": [("tackle", 1), ("vine-whip", 7)],
                                "machine": [("protect", 0)],
                            },
                            "sword-shield": {"machine": [("protect", 0)]},
                        }
                    ),
                ),
                _seed_pokemon(
                    4,
                    "charmander",
                    "小火龙",
                    ["fire"],
                    _moves_json(
                        {
                            "scarlet-violet": {
                                "level-up": [("scratch", 1)],
                                "machine": [("protect", 0)],
                            }
                        }
                    ),
                ),
                _seed_pokemon(
                    150,
                    "mewtwo",
                    "超梦",
                    ["psychic"],
                    _moves_json({"red-blue": {"level-up": [("confusion", 1)]}}),
                ),
            ]
        )
        await session.flush()

        # 招式参考数据（真实同步时会由 PokéAPI 详情写入）
        from app.db.models import MoveReference

        session.add_all(
            [
                MoveReference(
                    name="protect",
                    zh="守住",
                    name_en="Protect",
                    type="normal",
                    damage_class="status",
                    pp=10,
                    description_zh="完全挡住对手的攻击。",
                ),
                MoveReference(
                    name="tackle",
                    zh="撞击",
                    name_en="Tackle",
                    type="normal",
                    damage_class="physical",
                    power=40,
                    accuracy=100,
                    pp=35,
                ),
                MoveReference(
                    name="vine-whip",
                    zh="藤鞭",
                    name_en="Vine Whip",
                    type="grass",
                    damage_class="physical",
                    power=45,
                    accuracy=100,
                    pp=25,
                ),
                MoveReference(
                    name="scratch",
                    zh="抓",
                    name_en="Scratch",
                    type="normal",
                    damage_class="physical",
                    power=40,
                    accuracy=100,
                    pp=35,
                ),
                MoveReference(
                    name="confusion",
                    zh="念力",
                    name_en="Confusion",
                    type="psychic",
                    damage_class="special",
                    power=50,
                    accuracy=100,
                    pp=25,
                ),
            ]
        )
        await session.flush()
        await rebuild_move_index(session)
        await session.commit()


async def test_list_moves_search_and_filters(client: AsyncClient) -> None:
    await _seed(client)

    payload = (await client.get(MOVES_URL)).json()
    assert payload["meta"]["total"] == 5
    # 默认按中文名排序：守 / 念 / 抓 / 撞 / 藤
    assert [item["name"] for item in payload["items"]][0] == "protect"

    payload = (await client.get(MOVES_URL, params={"q": "守住"})).json()
    assert [item["name"] for item in payload["items"]] == ["protect"]

    payload = (await client.get(MOVES_URL, params={"type": "grass"})).json()
    assert [item["name"] for item in payload["items"]] == ["vine-whip"]

    payload = (await client.get(MOVES_URL, params={"damage_class": "status"})).json()
    assert [item["name"] for item in payload["items"]] == ["protect"]

    payload = (await client.get(MOVES_URL, params={"machine_only": "true"})).json()
    assert [item["name"] for item in payload["items"]] == ["protect"]


async def test_list_moves_sort_by_learners(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(MOVES_URL, params={"sort": "learners"})).json()
    assert payload["items"][0]["name"] == "protect"
    assert payload["items"][0]["learner_count"] == 2


async def test_list_moves_rejects_invalid_params(client: AsyncClient) -> None:
    await _seed(client)
    assert (await client.get(MOVES_URL, params={"sort": "nope"})).status_code == 422
    assert (await client.get(MOVES_URL, params={"damage_class": "magic"})).status_code == 422


async def test_move_detail_lists_learners_and_versions(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{MOVES_URL}/protect")).json()

    assert payload["zh"] == "守住"
    assert payload["learner_count"] == 2
    assert payload["is_machine"] is True
    # 版本组从新到旧：scarlet-violet 在前
    assert list(payload["learners_by_version"]) == ["scarlet-violet", "sword-shield"]
    assert payload["learners_by_version"]["scarlet-violet"] == 2
    assert payload["method_labels"]["machine"] == "招式学习器"
    assert payload["version_labels"]["scarlet-violet"] == "朱／紫"

    learners = {item["dex_number"]: item for item in payload["learners"]}
    assert learners[1]["name_zh"] == "妙蛙种子"
    assert learners[1]["types"] == ["grass", "poison"]
    assert learners[1]["version_groups"]["scarlet-violet"][0]["method"] == "machine"


async def test_move_detail_keeps_level_up_levels(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{MOVES_URL}/vine-whip")).json()

    learner = payload["learners"][0]
    assert learner["dex_number"] == 1
    entry = learner["version_groups"]["scarlet-violet"][0]
    assert entry == {"method": "level-up", "method_label": "升级", "level": 7}


async def test_move_detail_404(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.get(f"{MOVES_URL}/nonexistent")
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]
