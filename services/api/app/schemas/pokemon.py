"""图鉴公开接口的请求/响应模型（只读浏览）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PokemonSummary(BaseModel):
    """列表项：够用即可的摘要信息。"""

    dex_number: int
    name_en: str
    name_zh: str | None
    types: list[str]
    is_demo: bool = Field(description="演示数据标记，前端显式展示")


class PokemonListMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PokemonListResponse(BaseModel):
    items: list[PokemonSummary]
    meta: PokemonListMeta


class PokemonAbility(BaseModel):
    name: str
    zh: str | None
    is_hidden: bool


class PokemonEvolutionNode(BaseModel):
    name: str
    dex: int
    evolves_to: list[PokemonEvolutionNode] = []


class PokemonDetail(BaseModel):
    """详情：属性、种族值、特性、进化链、来源标注。"""

    dex_number: int
    name_en: str
    name_zh: str | None
    types: list[str]
    stats: dict[str, int]
    abilities: list[PokemonAbility]
    evolution: dict = Field(default_factory=dict, description="进化链树")
    generation_introduced: int | None
    height_dm: int | None = Field(description="身高（分米），展示层换算为米")
    weight_hg: int | None = Field(description="体重（百克），展示层换算为千克")
    source: Literal["pokeapi", "manual"]
    source_label: str = Field(description="数据来源的可读标签")
    is_demo: bool
    synced_at: str | None

    @classmethod
    def source_label_of(cls, source: str) -> str:
        return "PokéAPI 同步" if source == "pokeapi" else "手动维护"


PokemonEvolutionNode.model_rebuild()


class AdminPokemonEdit(BaseModel):
    """后台编辑请求体：全部字段可选，只更新给出的字段。"""

    name_en: str | None = None
    name_zh: str | None = None
    types: list[str] | None = None
    stats: dict[str, int] | None = None
    abilities: list[PokemonAbility] | None = None
    evolution: dict | None = None
    generation_introduced: int | None = None
    height_dm: int | None = None
    weight_hg: int | None = None
    is_demo: bool | None = None


class AdminPokemonCreate(BaseModel):
    """后台手动新增：dex_number 必填，其余按需。"""

    dex_number: int = Field(ge=1, le=10000)
    name_en: str
    name_zh: str | None = None
    types: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    abilities: list[PokemonAbility] = Field(default_factory=list)
    evolution: dict = Field(default_factory=dict)
    generation_introduced: int | None = None
    height_dm: int | None = None
    weight_hg: int | None = None
    is_demo: bool = False


class AdminSyncRequest(BaseModel):
    """手动触发同步。"""

    start: int = Field(default=1, ge=1)
    end: int = Field(default=151, ge=1)
    force: bool = Field(default=False, description="覆盖手动编辑过的记录")


class AdminSyncResultResponse(BaseModel):
    synced_count: int
    skipped_manual: list[int]
    failed: dict[int, str]
    summary: str


class AdminSyncStatusResponse(BaseModel):
    total: int
    from_pokeapi: int
    from_manual: int
    demo: int
    last_synced_at: str | None
    default_range: dict
    expected_in_range: int
    coverage: float | None


class AdminOpLogEntry(BaseModel):
    id: int
    action: str
    target: str | None
    detail: str | None
    operator: str
    created_at: str


class AdminOpLogResponse(BaseModel):
    items: list[AdminOpLogEntry]
