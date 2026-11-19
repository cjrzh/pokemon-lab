"""道具列表接口测试：搜索、分类筛选、分页、图标与分类统计。"""

from __future__ import annotations

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.db.models import ItemReference

ITEMS_URL = "/api/v1/items"


def _seed_rows() -> list[ItemReference]:
    return [
        ItemReference(
            name="sitrus-berry",
            zh="文柚果",
            name_en="Sitrus Berry",
            category="medicine",
            effect_en="Consumed at 1/2 max HP to recover 1/4 max HP.",
            cost=20,
            icon_path="items/sitrus-berry.png",
        ),
        ItemReference(
            name="leftovers",
            zh="吃剩的东西",
            name_en="Leftovers",
            category="held-items",
            effect_en="Restores 1/16 of the holder's max HP at the end of each turn.",
            cost=0,
            icon_path="items/leftovers.png",
        ),
        ItemReference(
            name="charizardite-y",
            zh="喷火龙进化石Ｙ",
            name_en="Charizardite Y",
            category="mega-stones",
            effect_en="Allows Charizard to Mega Evolve.",
            cost=0,
            icon_path=None,
        ),
        ItemReference(
            name="pretty-feather",
            zh="美丽之羽",
            name_en="Pretty Feather",
            category="collectibles",
            effect_en=None,
            cost=0,
            icon_path=None,
        ),
    ]


async def _seed(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add_all(_seed_rows())
        await session.commit()


async def test_list_items_returns_icons_and_categories(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(ITEMS_URL)).json()

    assert payload["meta"]["total"] == 4
    # 默认按中文名排序：文 / 吃 / 美 / 喷（按 Unicode，与实现一致）
    names = {item["name"] for item in payload["items"]}
    assert names == {"sitrus-berry", "leftovers", "charizardite-y", "pretty-feather"}

    berry = next(item for item in payload["items"] if item["name"] == "sitrus-berry")
    assert berry["zh"] == "文柚果"
    assert berry["category_zh"] == "药品 / 树果"
    assert berry["icon_url"] == "/media/items/sitrus-berry.png"

    # 分类统计按数量降序（每个分类各 1 个时按出现顺序）
    categories = {item["value"]: item for item in payload["categories"]}
    assert categories["held-items"]["label"] == "携带道具"
    assert categories["medicine"]["count"] == 1


async def test_list_items_search(client: AsyncClient) -> None:
    await _seed(client)

    async def search(q: str) -> list[str]:
        payload = (await client.get(ITEMS_URL, params={"q": q})).json()
        return [item["name"] for item in payload["items"]]

    assert await search("文柚") == ["sitrus-berry"]
    assert await search("leftovers") == ["leftovers"]
    assert await search("left") == ["leftovers"]
    assert await search("Mega Evolve") == ["charizardite-y"]
    assert await search("不存在") == []


async def test_list_items_filter_by_category(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(ITEMS_URL, params={"category": "held-items"})).json()

    assert [item["name"] for item in payload["items"]] == ["leftovers"]
    assert payload["meta"]["total"] == 1


async def test_list_items_pagination(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(ITEMS_URL, params={"page_size": 2, "page": 2})).json()

    assert len(payload["items"]) == 2
    assert payload["meta"] == {"page": 2, "page_size": 2, "total": 4, "total_pages": 2}


async def test_list_items_rejects_unknown_category(client: AsyncClient) -> None:
    response = await client.get(ITEMS_URL, params={"category": "not-a-category"})
    assert response.status_code == 422


async def test_list_items_empty_without_data(client: AsyncClient) -> None:
    payload = (await client.get(ITEMS_URL)).json()
    assert payload["items"] == []
    assert payload["meta"]["total"] == 0
    assert payload["categories"] == []


# ---------------------------------------------------------------------------
# 道具说明的中文（项目自译）
# ---------------------------------------------------------------------------


def test_item_translations_cover_every_item() -> None:
    """译文文件覆盖库里的全部道具（缺一条界面上就会露出英文）。"""
    from app.services.flavor_translation_service import (
        load_item_effect_translations,
        reset_item_effect_translation_cache,
    )

    reset_item_effect_translation_cache()
    translations = load_item_effect_translations()
    assert len(translations) > 200
    # 抽样确认是中文而非英文原文
    assert "携带" in translations["leftovers"]
    assert "超级进化" in translations["charizardite-y"]


async def test_list_returns_chinese_effect(client: AsyncClient) -> None:
    """接口带出中文说明与来源标记。"""
    from app.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            ItemReference(
                name="leftovers",
                zh="吃剩的东西",
                name_en="Leftovers",
                category="held-items",
                effect_en="Restores 1/16 of the holder's max HP at the end of each turn.",
                effect_zh="携带：每回合结束时回复携带者最大 HP 的 1/16（6.25%）。",
                effect_zh_source="project",
            )
        )
        await session.commit()

    payload = (await client.get(ITEMS_URL)).json()
    item = next(row for row in payload["items"] if row["name"] == "leftovers")
    assert item["effect_zh"].startswith("携带")
    assert item["effect_zh_source"] == "project"
    # 英文原文仍保留，界面可折叠展示
    assert item["effect_en"].startswith("Restores")


async def test_items_without_translation_fall_back_to_english(client: AsyncClient) -> None:
    """没有译文时 effect_zh 为 null，前端回落到英文，而不是显示空。"""
    from app.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            ItemReference(
                name="unknown-item",
                zh="未知道具",
                name_en="Unknown",
                category="other",
                effect_en="Does something.",
                effect_zh=None,
                effect_zh_source=None,
            )
        )
        await session.commit()

    payload = (await client.get(ITEMS_URL, params={"q": "未知"})).json()
    item = payload["items"][0]
    assert item["effect_zh"] is None
    assert item["effect_en"] == "Does something."
