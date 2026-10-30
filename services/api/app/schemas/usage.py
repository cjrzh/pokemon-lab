"""对战使用率排行接口的响应模型。

一个响应同时包含：
  - `formats`：四个固定格式的元数据与条目数（用于页面标签；未导入的格式也在里面）；
  - 当前格式的排行榜 `items` 与分页 `meta`。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.doubles import DoublesSpread, DoublesUsage


class UsageFormatInfo(BaseModel):
    """排行榜页顶部的格式标签。"""

    key: str
    label: str
    short_label: str
    game: str
    ruleset: str
    month: str = Field(description="统计月份（YYYY-MM）")
    cutoff: int = Field(description="Smogon 等级线")
    points_kind: Literal["ev", "stat_points"] = "ev"
    battles: int = 0
    note: str | None = None
    source_url: str | None = None
    entries: int = Field(default=0, description="该格式的排行条目数")
    imported: bool = Field(default=False, description="数据是否已导入本地库")


class UsageRankingItem(BaseModel):
    """排行榜一行：排名、使用率、图鉴信息与高频配装摘要。"""

    showdown_name: str = Field(description="Smogon / Showdown 显示名；同编号的形态分数行")
    dex_number: int | None = Field(default=None, description="映射到的全国图鉴编号")
    name_zh: str | None = None
    name_en: str | None = None
    types: list[str] = Field(default_factory=list)
    artwork_url: str | None = Field(default=None, description="立绘（本地缓存优先）")
    artwork_fallback_url: str | None = None
    sprite_url: str | None = Field(default=None, description="小图标（96×96，本地缓存优先）")
    is_legendary: bool = False
    is_mythical: bool = False
    rank: int | None = None
    usage: float | None = Field(default=None, description="使用率百分比（0–100）")
    raw_count: int = 0
    abilities: list[DoublesUsage] = Field(default_factory=list, description="前 3 个常用特性")
    items: list[DoublesUsage] = Field(default_factory=list, description="前 3 个常用道具")
    moves: list[DoublesUsage] = Field(default_factory=list, description="前 4 个常用招式")
    spread: DoublesSpread | None = Field(default=None, description="最常见的一组配点")


class UsageRankingMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class UsageRankingResponse(BaseModel):
    """排行榜页的完整数据。"""

    formats: list[UsageFormatInfo] = Field(description="固定四个格式，按 BDSP → 剑盾 → 朱紫 → 冠军")
    format_key: str = Field(description="当前展示的格式 key")
    items: list[UsageRankingItem] = []
    meta: UsageRankingMeta
    has_data: bool = Field(description="本地是否导入了任意双打统计")
