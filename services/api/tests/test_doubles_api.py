"""双打辅助接口测试：名称映射、导入、详情与后台看板。

测试不依赖仓库内真实的 `data/doubles/*.json`：数据目录由 `data_dir` 夹具指向临时目录，
用例自行写入最小数据集，保证结果可复现、不随月度数据变化。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.domain.doubles_formats import FORMATS
from app.repositories import pokemon_repo
from app.services.doubles_service import (
    build_name_index,
    import_datasets,
    reset_labels_cache,
)

POKEMON_URL = "/api/v1/pokemon"
ADMIN_URL = "/api/v1/admin"


def _seed_pokemon(dex: int, name_en: str, name_zh: str) -> pokemon_repo.Pokemon:
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_zh,
        types_json=json.dumps(["fire"]),
        stats_json=json.dumps({"hp": 95}),
        abilities_json="[]",
        evolution_json="{}",
        moves_json="{}",
        source="pokeapi",
    )


def _dataset() -> dict:
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
            "usage_url": "https://example.test/usage.txt",
            "moveset_url": "https://example.test/moveset.txt",
        },
        "battles": 1000,
        "entries": [
            {
                "name": "Incineroar",
                "rank": 3,
                "usage": 31.7,
                "raw_count": 500,
                "abilities": [["intimidate", 99.6], ["blaze", 0.4]],
                "items": [["sitrus-berry", 62.7]],
                "moves": [
                    ["fake-out", 98.6],
                    ["parting-shot", 95.8],
                    ["flare-blitz", 90.9],
                ],
                "teammates": [["rillaboom", 60.4]],
                "tera_types": [],
                "spreads": [
                    {"nature": "careful", "points": [32, 0, 14, 0, 20, 0], "pct": 5.4},
                    {"nature": "adamant", "points": [32, 32, 0, 0, 2, 0], "pct": 3.0},
                ],
            },
            {
                "name": "Charizard-Mega-Y",
                "rank": 14,
                "usage": 12.2,
                "raw_count": 300,
                "abilities": [["drought", 100.0]],
                "items": [["charizardite-y", 100.0]],
                "moves": [["heat-wave", 99.2]],
                "teammates": [["incineroar", 35.3]],
                "tera_types": [],
                "spreads": [{"nature": "timid", "points": [2, 0, 0, 32, 0, 32], "pct": 8.4}],
            },
            # 不存在的本地名称：应保留记录、dex_number 为空
            {
                "name": "Missingno",
                "rank": 900,
                "usage": 0.001,
                "raw_count": 1,
                "abilities": [],
                "items": [],
                "moves": [],
                "teammates": [],
                "tera_types": [],
                "spreads": [],
            },
        ],
    }


def _write_dataset(data_dir, payload: dict, *, name: str = "champions.json") -> None:
    target = data_dir / "doubles"
    target.mkdir(parents=True, exist_ok=True)
    (target / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (target / "labels.json").write_text(
        json.dumps(
            {
                "items": {"sitrus-berry": "文柚果", "charizardite-y": "喷火龙进化石Ｙ"},
                "moves": {
                    "fake-out": "击掌奇袭",
                    "parting-shot": "抛下狠话",
                    "flare-blitz": "闪焰冲锋",
                    "heat-wave": "热风",
                },
                "abilities": {"intimidate": "威吓", "drought": "日照"},
                "natures": {"careful": "慎重", "adamant": "固执", "timid": "胆小"},
                "items_en": {"sitrus-berry": "Sitrus Berry", "charizardite-y": "Charizardite Y"},
                "moves_en": {
                    "fake-out": "Fake Out",
                    "parting-shot": "Parting Shot",
                    "flare-blitz": "Flare Blitz",
                    "heat-wave": "Heat Wave",
                },
                "abilities_en": {"intimidate": "Intimidate", "drought": "Drought"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


async def _seed(client: AsyncClient, data_dir) -> None:
    from app.db.models import MoveReference

    factory = get_session_factory()
    async with factory() as session:
        # 招式属性来自 move_ref（真实环境由图鉴同步写入）
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
                MoveReference(name="heat-wave", zh="热风", type="fire", damage_class="special"),
            ]
        )
        session.add_all(
            [
                _seed_pokemon(6, "charizard", "喷火龙"),
                _seed_pokemon(727, "incineroar", "炽焰咆哮虎"),
                _seed_pokemon(812, "rillaboom", "轰擂金刚猩"),
            ]
        )
        await session.flush()
        _write_dataset(data_dir, _dataset())
        reset_labels_cache()
        await import_datasets(session)
        await session.commit()


def test_format_order_and_trade_prefixes() -> None:
    """页面顺序：BDSP → 剑盾 → 朱紫 → 冠军；前三者带交换前缀。"""
    assert [fmt.key for fmt in FORMATS] == ["bdsp", "swsh", "sv", "champions"]
    assert [fmt.trade_prefix for fmt in FORMATS] == [
        "!tradeBDSP",
        "!tradeSWSH",
        "!tradeSV",
        None,
    ]
    assert FORMATS[0].default_level == 100
    assert all(fmt.default_level == 50 for fmt in FORMATS[1:])


def test_name_index_resolves_forms_and_skips_ambiguous_roots() -> None:
    index = build_name_index(
        [
            ("charizard", 6),
            ("urshifu-single-strike", 892),
            ("rotom", 479),
            ("nidoran-f", 29),
            ("nidoran-m", 32),
        ]
    )

    assert index.resolve("Charizard-Mega-Y") == 6
    assert index.resolve("Urshifu-Rapid-Strike") == 892
    assert index.resolve("Rotom-Wash") == 479
    assert index.resolve("NidoranM") == 32
    # 词根不唯一时不猜
    assert index.resolve("Nidoran") is None


async def test_doubles_detail_returns_profiles_with_labels(client: AsyncClient, data_dir) -> None:
    await _seed(client, data_dir)
    response = await client.get(f"{POKEMON_URL}/6/doubles")

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_data"] is True
    # 只有冠军一个格式
    assert [fmt["key"] for fmt in payload["formats"]] == ["champions"]

    fmt = payload["formats"][0]
    assert fmt["month"] == "2026-09"
    assert fmt["cutoff"] == 1760
    assert fmt["points_kind"] == "stat_points"
    # Charizard-Mega-Y 与 Charizard 都映射到 #6
    names = [profile["showdown_name"] for profile in fmt["profiles"]]
    assert names == ["Charizard-Mega-Y"]

    profile = fmt["profiles"][0]
    assert profile["rank"] == 14
    assert profile["abilities"][0] == {
        "slug": "drought",
        "name": "日照",
        "name_en": "Drought",
        "type": None,
        "icon_url": None,
        "pct": 100.0,
    }
    assert profile["items"][0]["name"] == "喷火龙进化石Ｙ"
    assert profile["items"][0]["name_en"] == "Charizardite Y"
    # 道具图标来自 item_ref；测试没有种子记录时为空（界面显示占位）
    assert profile["items"][0]["icon_url"] is None
    assert profile["moves"][0]["name"] == "热风"
    assert profile["moves"][0]["name_en"] == "Heat Wave"
    # 招式带属性，供前端的属性徽章渲染
    assert profile["moves"][0]["type"] == "fire"
    assert profile["teammates"][0]["dex_number"] == 727
    assert profile["teammates"][0]["name_zh"] == "炽焰咆哮虎"
    # Champions 是能力点，不给出 IV 建议
    assert profile["ivs"] is None
    assert profile["spreads"][0]["nature_label"] == "胆小"
    assert profile["spreads"][0]["points"] == [2, 0, 0, 32, 0, 32]


async def test_doubles_detail_returns_item_icons(client: AsyncClient, data_dir) -> None:
    """item_ref 有记录时，推荐配置里的道具带本地图标地址。"""
    await _seed(client, data_dir)

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

    payload = (await client.get(f"{POKEMON_URL}/727/doubles")).json()
    items = payload["formats"][0]["profiles"][0]["items"]
    assert items[0]["slug"] == "sitrus-berry"
    assert items[0]["icon_url"] == "/media/items/sitrus-berry.png"
    # 未收录的道具保持空值
    assert all(item["icon_url"] is None for item in items[1:])


async def test_doubles_detail_shared_dex_shows_all_forms(client: AsyncClient, data_dir) -> None:
    """同一图鉴编号的多个形态按使用率降序返回。"""
    await _seed(client, data_dir)
    payload = (await client.get(f"{POKEMON_URL}/727/doubles")).json()

    profiles = payload["formats"][0]["profiles"]
    assert [p["showdown_name"] for p in profiles] == ["Incineroar"]
    assert profiles[0]["ivs"] is None


async def test_doubles_detail_empty_for_unsynced_pokemon(client: AsyncClient, data_dir) -> None:
    await _seed(client, data_dir)
    payload = (await client.get(f"{POKEMON_URL}/812/doubles")).json()

    assert payload["has_data"] is False
    assert payload["formats"][0]["profiles"] == []


async def test_doubles_detail_404(client: AsyncClient, data_dir) -> None:
    await _seed(client, data_dir)
    response = await client.get(f"{POKEMON_URL}/9999/doubles")
    assert response.status_code == 404


async def test_admin_doubles_status_and_import(client: AsyncClient, data_dir) -> None:
    await _seed(client, data_dir)

    status = (await client.get(f"{ADMIN_URL}/doubles/status")).json()
    assert status["format_count"] == 1
    assert status["entries"] == 3
    assert status["formats"][0]["key"] == "champions"
    assert status["formats"][0]["dex_covered"] == 2

    response = await client.post(f"{ADMIN_URL}/doubles/sync")
    assert response.status_code == 200
    result = response.json()
    assert result["formats"] == 1
    assert result["entries"] == 3
    assert "Missingno" in result["unresolved"]

    logs = (await client.get(f"{ADMIN_URL}/ops")).json()["items"]
    assert logs[0]["action"] == "doubles.import"
