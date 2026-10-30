"""招式百科接口的响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DamageClass = Literal["physical", "special", "status"]


class MoveSummary(BaseModel):
    """列表项：一眼能比较的数值 + 学习者数量。"""

    name: str = Field(description="招式 slug（如 `u-turn`），详情页路由用")
    zh: str | None = None
    name_en: str | None = None
    type: str | None = None
    damage_class: DamageClass | None = None
    damage_class_zh: str | None = None
    power: int | None = None
    accuracy: int | None = None
    pp: int | None = None
    description_zh: str | None = None
    learner_count: int = 0
    is_machine: bool = Field(default=False, description="是否可通过招式学习器学习")


class MoveListMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class MoveListResponse(BaseModel):
    items: list[MoveSummary]
    meta: MoveListMeta


class MoveLearnEntry(BaseModel):
    """一个版本组下的一种学习方式。"""

    method: str
    method_label: str
    level: int = 0


class MoveLearnerPokemon(BaseModel):
    """会这招的宝可梦（可跳转图鉴详情）。"""

    dex_number: int
    name_zh: str | None
    name_en: str
    types: list[str] = []
    is_legendary: bool = False
    is_mythical: bool = False
    #: 版本组 → 学习方式列表（按版本从新到旧）
    version_groups: dict[str, list[MoveLearnEntry]] = {}
    #: 最近一个版本组里的学习方式（列表页做摘要）
    latest_methods: list[str] = []


class MoveDetail(MoveSummary):
    """详情：完整数值、说明、按世代分组的宝可梦学习者。"""

    learners: list[MoveLearnerPokemon] = []
    #: 每个版本组有多少只宝可梦能学（用于「哪一代能学」概览）
    learners_by_version: dict[str, int] = {}
    #: 出现过的学习方式及数量
    method_counts: dict[str, int] = {}
    #: 版本组 slug → 中文名（前端不再重复维护 26 个版本组标签）
    version_labels: dict[str, str] = {}
    #: 学习方式 slug → 中文名
    method_labels: dict[str, str] = {}
