"""道具百科接口的响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ItemSummary(BaseModel):
    """列表项：名称、分类、说明与图标。"""

    name: str = Field(description="道具 slug（如 `sitrus-berry`）")
    zh: str | None = None
    name_en: str | None = None
    category: str | None = Field(default=None, description="PokéAPI 分类 slug，如 held-items")
    category_zh: str | None = Field(default=None, description="分类中文名")
    effect_en: str | None = Field(default=None, description="英文短说明（上游原文）")
    effect_zh: str | None = Field(
        default=None, description="中文说明（项目自译，非官方文本；见 effect_zh_source）"
    )
    effect_zh_source: str | None = Field(
        default=None, description="中文说明来源：project（项目自译）"
    )
    cost: int | None = None
    icon_url: str | None = Field(default=None, description="图标地址（本地缓存优先）")


class ItemListMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ItemCategoryOption(BaseModel):
    """分类筛选选项。"""

    value: str
    label: str
    count: int


class ItemListResponse(BaseModel):
    items: list[ItemSummary]
    meta: ItemListMeta
    categories: list[ItemCategoryOption] = Field(
        default_factory=list, description="库里实际出现过的分类及数量"
    )
