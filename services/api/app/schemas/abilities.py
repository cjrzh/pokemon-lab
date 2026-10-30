"""特性接口的请求/响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AbilityHolder(BaseModel):
    """拥有某特性的宝可梦（可跳转到图鉴详情）。"""

    dex_number: int
    name_zh: str | None
    name_en: str
    types: list[str] = []
    is_hidden: bool = Field(default=False, description="是否通过隐藏特性拥有")
    is_legendary: bool = False
    is_mythical: bool = False
    sprite_url: str | None = Field(default=None, description="小图标地址（本地缓存优先）")


class AbilitySummary(BaseModel):
    name: str
    zh: str | None
    effect_zh: str | None
    tier: Literal["s", "normal"]
    rating_source: Literal["llm", "manual"]
    rating_note: str | None = None
    holder_count: int = 0


class AbilityListMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    s_tier_total: int


class AbilityListResponse(BaseModel):
    items: list[AbilitySummary]
    meta: AbilityListMeta


class AbilityDetail(BaseModel):
    name: str
    zh: str | None
    effect_zh: str | None
    effect_en: str | None
    tier: Literal["s", "normal"]
    rating_source: Literal["llm", "manual"]
    rating_note: str | None = None
    holders: list[AbilityHolder] = []


class AdminAbilityRatingUpdate(BaseModel):
    """人工修改评级。"""

    tier: Literal["s", "normal"]
    note: str | None = Field(default=None, description="评级理由，可为空")
