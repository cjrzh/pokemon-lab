"""道具百科公开路由（只读）。

`GET /items`：搜索（中英文名 / 说明）、按分类筛选、分页。
数据来自 `item_ref`（由 `scripts/sync_items.py` 从 PokéAPI 同步），
当前覆盖双打统计里出现的约 257 个道具。

与双打辅助 / 使用率排行的关系：那两处的道具条目按 slug 关联本表取图标与
说明，所以这里不重新抓取，只读同一份数据。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.repositories import pokemon_repo
from app.repositories.pokemon_repo import ItemListQuery
from app.schemas.items import (
    ItemCategoryOption,
    ItemListMeta,
    ItemListResponse,
    ItemSummary,
)
from app.services.item_service import icon_media_url

router = APIRouter(prefix="/items", tags=["items"])

#: PokéAPI 的道具分类 → 中文名。未列出的分类原样展示 slug（不猜译）。
CATEGORY_ZH: dict[str, str] = {
    "all-machines": "招式学习器",
    "bad-held-items": "负面携带道具",
    "collectibles": "收集品",
    "choice": "讲究系列",
    "effort-training": "努力值道具",
    "evolution": "进化道具",
    "gameplay": "游戏道具",
    "healing": "回复道具",
    "held-items": "携带道具",
    "in-a-pinch": "危机时威力提升",
    "jewels": "宝石",
    "loot": "掉落物",
    "mega-stones": "超级进化石",
    "medicine": "药品 / 树果",
    "memories": "记忆碟",
    "other": "其它",
    "picky-healing": "偏好回复的道具",
    "plates": "属性石板",
    "species-specific": "专用道具",
    "type-enhancement": "属性增强",
    "type-protection": "属性护具",
}


@router.get(
    "",
    response_model=ItemListResponse,
    summary="道具列表",
    description=(
        "道具名称 / 说明搜索，按分类筛选、分页；返回中文名、分类、英文短说明与图标地址。"
        "数据覆盖双打统计里出现的道具。"
    ),
)
async def list_items(
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, max_length=64, description="中英文名或英文说明关键词"),
    category: str | None = Query(default=None, description="分类 slug，如 held-items"),
) -> ItemListResponse:
    if category is not None and category not in CATEGORY_ZH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"未知分类 {category!r}（合法值：{sorted(CATEGORY_ZH)}）",
        )

    items, total = await pokemon_repo.list_items(
        session,
        ItemListQuery(search=q, category=category, page=page, page_size=page_size),
    )
    categories = await pokemon_repo.get_item_categories(session)
    page = max(1, page)
    page_size = max(1, min(200, page_size))

    return ItemListResponse(
        items=[
            ItemSummary(
                name=item.name,
                zh=item.zh,
                name_en=item.name_en,
                category=item.category,
                category_zh=CATEGORY_ZH.get(item.category or ""),
                effect_en=item.effect_en,
                effect_zh=item.effect_zh,
                effect_zh_source=item.effect_zh_source,
                cost=item.cost,
                icon_url=icon_media_url(item.name, item.icon_path),
            )
            for item in items
        ],
        meta=ItemListMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, -(-total // page_size)),
        ),
        categories=[
            ItemCategoryOption(
                value=item_category,
                label=CATEGORY_ZH.get(item_category, item_category),
                count=count,
            )
            for item_category, count in categories
        ],
    )
