"""使用率排行接口测试：四格式标签、排序、搜索、分页与条目摘要。

数据目录由 `data_dir` 夹具指向临时目录，用例写入最小数据集，
不依赖仓库里真实的月度统计。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.repositories import pokemon_repo
from app.services.doubles_service import import_datasets, reset_labels_cache

USAGE_URL = "/api/v1/usage-ranking"


def _entry(name: str, rank: int | None, usage: float | None) -> dict:
    return {
        "name": name,
        "rank": rank,
        "usage": usage,
        "raw_count": 100,
        "abilities": [["intimidate", 99.0], ["blaze", 99.0], ["unnerve", 1.0], ["pressure", 0.5]],
        "items": [
            ["sitrus-berry", 60.0],
            ["leftovers", 20.0],
            ["rocky-helmet", 10.0],
            ["occa-berry", 5.0],
        ],
        "moves": [
            ["fake-out", 99.0],
            ["parting-shot", 95.0],
            ["flare-blitz", 90.0],
            ["protect", 80.0],
            ["snarl", 10.0],
        ],
        "teammates": [],
        "tera_types": [],
        "spreads": [{"nature": "careful", "points": [32, 0, 14, 0, 20, 0], "pct": 5.4}],
    }


def _dataset(entries: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "format": {
            "key": "champions",
            "label": "宝可梦冠军 · VGC 2026 Reg M-C",
            "short_label": "冠军",
            "game": "Pokémon Champions",
            "ruleset": "VGC 2026 Reg M-C",
            "smogon_format": "gen9championsvgc2026regmc",
            "month": "2026-09",
            "cutoff": 1760,
            "points_kind": "stat_points",
            "note": "测试数据",
            "trade_prefix": None,
            "default_level": 50,
        },
        "battles": 1000,
        "entries": entries,
    }


_LABELS = {
    "items": {
        "sitrus-berry": "文柚果",
        "leftovers": "吃剩的东西",
        "rocky-helmet": "凸凸头盔",
        "occa-berry": "龙火果",
    },
    "moves": {
        "fake-out": "击掌奇袭",
        "parting-shot": "抛下狠话",
        "flare-blitz": "闪焰冲锋",
        "protect": "守住",
        "snarl": "大声咆哮",
    },
    "abilities": {
        "intimidate": "威吓",
        "blaze": "猛火",
        "unnerve": "紧张感",
        "pressure": "压迫感",
    },
    "natures": {"careful": "慎重"},
    "items_en": {
        "sitrus-berry": "Sitrus Berry",
        "leftovers": "Leftovers",
        "rocky-helmet": "Rocky Helmet",
        "occa-berry": "Occa Berry",
    },
    "moves_en": {
        "fake-out": "Fake Out",
        "parting-shot": "Parting Shot",
        "flare-blitz": "Flare Blitz",
        "protect": "Protect",
        "snarl": "Snarl",
    },
    "abilities_en": {
        "intimidate": "Intimidate",
        "blaze": "Blaze",
        "unnerve": "Unnerve",
        "pressure": "Pressure",
    },
}


def _pokemon(dex: int, name_en: str, name_zh: str, types: list[str], *, artwork: bool = True):
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_zh,
        types_json=json.dumps(types),
        stats_json=json.dumps({"hp": 60}),
        abilities_json="[]",
        evolution_json="{}",
        moves_json="{}",
        source="pokeapi",
        artwork_path=f"artwork/{dex}.png" if artwork else None,
        artwork_url=None,
        sprite_url=f"https://example.test/{dex}.png",
    )


async def _seed(client: AsyncClient, data_dir, entries: list[dict]) -> None:
    from app.db.models import MoveReference

    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                _pokemon(727, "incineroar", "炽焰咆哮虎", ["fire", "dark"]),
                _pokemon(3, "venusaur", "妙蛙花", ["grass", "poison"], artwork=False),
                _pokemon(903, "sneasler", "大狃拉", ["fighting", "poison"]),
            ]
        )
        session.add_all(
            [
                MoveReference(
                    name="fake-out", zh="击掌奇袭", type="normal", damage_class="physical"
                ),
                MoveReference(
                    name="parting-shot", zh="抛下狠话", type="dark", damage_class="status"
                ),
                MoveReference(
                    name="flare-blitz", zh="闪焰冲锋", type="fire", damage_class="physical"
                ),
                MoveReference(name="protect", zh="守住", type="normal", damage_class="status"),
            ]
        )
        await session.flush()

        target = data_dir / "doubles"
        target.mkdir(parents=True, exist_ok=True)
        (target / "champions.json").write_text(
            json.dumps(_dataset(entries), ensure_ascii=False), encoding="utf-8"
        )
        (target / "labels.json").write_text(
            json.dumps(_LABELS, ensure_ascii=False), encoding="utf-8"
        )
        reset_labels_cache()
        await import_datasets(session)
        await session.commit()


async def test_ranking_always_lists_four_formats(client: AsyncClient, data_dir) -> None:
    """未导入的格式也要出现（entries=0、imported=false），顺序固定。"""
    await _seed(client, data_dir, [_entry("Incineroar", 1, 30.0)])

    payload = (await client.get(USAGE_URL)).json()
    assert [fmt["key"] for fmt in payload["formats"]] == ["bdsp", "swsh", "sv", "champions"]

    by_key = {fmt["key"]: fmt for fmt in payload["formats"]}
    assert by_key["bdsp"]["imported"] is False
    assert by_key["bdsp"]["entries"] == 0
    assert by_key["champions"]["imported"] is True
    assert by_key["champions"]["entries"] == 1
    assert by_key["champions"]["month"] == "2026-09"
    assert by_key["champions"]["cutoff"] == 1760
    # 未导入格式的元数据来自代码里的格式定义（保证页面能展示标签与月份）
    assert by_key["sv"]["month"] == "2026-04"
    assert by_key["sv"]["source_url"].endswith("gen9vgc2026regi-1630.txt")
    assert payload["has_data"] is True
    assert payload["format_key"] == "bdsp"


async def test_ranking_sorted_by_rank_and_has_no_data_state(client: AsyncClient) -> None:
    """没有任何格式导入时返回空榜，但仍带四个格式标签。"""
    payload = (await client.get(USAGE_URL)).json()

    assert payload["has_data"] is False
    assert len(payload["formats"]) == 4
    assert payload["items"] == []
    assert payload["meta"]["total"] == 0


async def test_ranking_items_sorted_and_paginated(client: AsyncClient, data_dir) -> None:
    await _seed(
        client,
        data_dir,
        [
            _entry("Incineroar", 3, 10.0),
            _entry("Venusaur", 1, 30.0),
            _entry("Sneasler", 2, 20.0),
        ],
    )

    payload = (await client.get(USAGE_URL, params={"format": "champions"})).json()
    assert [item["showdown_name"] for item in payload["items"]] == [
        "Venusaur",
        "Sneasler",
        "Incineroar",
    ]
    assert payload["meta"] == {"page": 1, "page_size": 50, "total": 3, "total_pages": 1}

    # 每页 2 条：第 2 页只剩一条
    payload = (
        await client.get(USAGE_URL, params={"format": "champions", "page_size": 2, "page": 2})
    ).json()
    assert [item["showdown_name"] for item in payload["items"]] == ["Incineroar"]
    assert payload["meta"]["total_pages"] == 2


async def test_ranking_item_summary_and_artwork(client: AsyncClient, data_dir) -> None:
    await _seed(client, data_dir, [_entry("Incineroar", 1, 30.0), _entry("Venusaur", 2, 20.0)])

    items = (await client.get(USAGE_URL, params={"format": "champions"})).json()["items"]
    incineroar, venusaur = items

    assert incineroar["dex_number"] == 727
    assert incineroar["name_zh"] == "炽焰咆哮虎"
    assert incineroar["types"] == ["fire", "dark"]
    # 本地缓存优先；没有缓存时前端用 sprite 兜底
    assert incineroar["artwork_url"] == "/media/artwork/727.png"
    assert incineroar["artwork_fallback_url"] == "https://example.test/727.png"
    assert venusaur["artwork_url"] is None

    # 摘要只保留前 3 个特性 / 3 个道具 / 4 个招式，但都带中英文名与招式属性
    assert [a["name"] for a in incineroar["abilities"]] == ["威吓", "猛火", "紧张感"]
    assert [i["name"] for i in incineroar["items"]] == ["文柚果", "吃剩的东西", "凸凸头盔"]
    # 道具图标：未同步 item_ref 时为空，界面显示占位而不是假图标
    assert all(item["icon_url"] is None for item in incineroar["items"])
    assert [m["name"] for m in incineroar["moves"]] == [
        "击掌奇袭",
        "抛下狠话",
        "闪焰冲锋",
        "守住",
    ]
    assert incineroar["moves"][2]["type"] == "fire"
    assert incineroar["spread"]["nature_label"] == "慎重"
    assert incineroar["spread"]["points"] == [32, 0, 14, 0, 20, 0]


async def test_ranking_search_by_name_and_dex(client: AsyncClient, data_dir) -> None:
    await _seed(
        client,
        data_dir,
        [
            _entry("Incineroar", 1, 30.0),
            _entry("Venusaur", 2, 20.0),
            _entry("Sneasler", 3, 10.0),
        ],
    )

    async def search(q: str) -> list[str]:
        payload = (await client.get(USAGE_URL, params={"format": "champions", "q": q})).json()
        return [item["showdown_name"] for item in payload["items"]]

    assert await search("咆哮虎") == ["Incineroar"]
    assert await search("venu") == ["Venusaur"]
    assert await search("Sneas") == ["Sneasler"]
    assert await search("3") == ["Venusaur"]
    assert await search("不存在") == []


async def test_ranking_items_include_item_icons(client: AsyncClient, data_dir) -> None:
    """item_ref 有记录时，道具条目带上本地图标地址。"""
    await _seed(client, data_dir, [_entry("Incineroar", 1, 30.0)])

    from app.db.engine import get_session_factory
    from app.db.models import ItemReference

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            ItemReference(
                name="sitrus-berry",
                zh="文柚果",
                name_en="Sitrus Berry",
                category="medicine",
                icon_path="items/sitrus-berry.png",
            )
        )
        await session.commit()

    items = (await client.get(USAGE_URL, params={"format": "champions"})).json()["items"]
    berry = items[0]["items"][0]
    assert berry["slug"] == "sitrus-berry"
    assert berry["icon_url"] == "/media/items/sitrus-berry.png"
    # 未收录的道具保持空值，不拼假地址
    assert items[0]["items"][1]["icon_url"] is None


async def test_ranking_rejects_unknown_format(client: AsyncClient) -> None:
    response = await client.get(USAGE_URL, params={"format": "gen9ou"})
    assert response.status_code == 422
    assert "format" in response.json()["detail"]


async def test_ranking_page_size_is_capped(client: AsyncClient, data_dir) -> None:
    await _seed(client, data_dir, [_entry("Incineroar", 1, 30.0)])
    response = await client.get(USAGE_URL, params={"format": "champions", "page_size": 999})
    assert response.status_code == 422
