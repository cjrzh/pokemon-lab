"""图鉴公开接口的请求/响应模型（只读浏览）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PokemonListAbility(BaseModel):
    """列表卡片上的特性（只需名称与 S 级标记）。"""

    name: str
    zh: str | None
    is_hidden: bool
    is_s_tier: bool


class PokemonSummary(BaseModel):
    """列表项：卡片需要的信息（立绘、编号、名称、属性、种族值、特性）。

    `stats` 是完整六项，列表模式需要按项展示；`total_stats` 是六项之和，
    卡片模式单独显示。
    """

    dex_number: int
    name_en: str
    name_zh: str | None
    name_ja: str | None = None
    types: list[str]
    stats: dict[str, int] = Field(default_factory=dict, description="六项种族值")
    total_stats: int | None = Field(default=None, description="六项种族值之和")
    artwork_url: str | None = Field(default=None, description="立绘地址（本地缓存优先）")
    artwork_fallback_url: str | None = Field(default=None, description="立绘远程兜底地址")
    sprite_url: str | None = Field(
        default=None, description="小图标地址（96×96，本地缓存优先；列表与特性页使用）"
    )
    is_legendary: bool = False
    is_mythical: bool = False
    abilities: list[PokemonListAbility] = []
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
    effect_zh: str | None = Field(default=None, description="中文图鉴说明")
    effect_en: str | None = None
    tier: Literal["s", "normal"] = "normal"
    is_s_tier: bool = False


class PokemonEvolutionNode(BaseModel):
    name: str
    dex: int
    zh: str | None = None
    detail: str | None = Field(default=None, description="进化条件，如「等级 16」")
    evolves_to: list[PokemonEvolutionNode] = []


class PokemonMove(BaseModel):
    name: str
    zh: str | None = None
    level: int = 0
    type: str | None = None
    damage_class: str | None = None
    damage_class_zh: str | None = None
    power: int | None = None
    accuracy: int | None = None
    pp: int | None = None
    description_zh: str | None = None


class PokemonMoveMethod(BaseModel):
    """某个版本组下的一种学习方式（升级 / 学习器 / 蛋招式 / 教学 …）。"""

    method: str
    label: str
    moves: list[PokemonMove] = []


class PokemonMoveVersionGroup(BaseModel):
    version_group: str
    label: str
    methods: list[PokemonMoveMethod] = []


class PokemonMoves(BaseModel):
    """全部招式：按版本组分组，组内再按学习方式分组。"""

    default_version_group: str | None = Field(
        default=None, description="默认展示的版本组（有数据的最新作品）"
    )
    version_groups: list[PokemonMoveVersionGroup] = []


class PokemonNeighbor(BaseModel):
    dex_number: int
    name_zh: str | None
    name_en: str


class PokemonDetail(BaseModel):
    """详情：立绘、基础档案、图鉴描述、属性、种族值、特性、进化链、招式。"""

    dex_number: int
    name_en: str
    name_zh: str | None
    name_ja: str | None = None
    types: list[str]
    stats: dict[str, int]
    total_stats: int | None = None
    abilities: list[PokemonAbility]
    evolution: dict = Field(default_factory=dict, description="进化链树")
    moves: PokemonMoves = Field(default_factory=PokemonMoves)

    # ---------- 图鉴档案 ----------
    genus_zh: str | None = None
    genus_en: str | None = None
    flavor_zh: str | None = None
    flavor_en: str | None = None
    flavor_zh_source: Literal["pokeapi", "project"] | None = Field(
        default=None, description="中文图鉴描述来源：pokeapi 官方 / project 项目自译"
    )
    genus_zh_source: Literal["pokeapi", "project"] | None = None
    artwork_url: str | None = None
    artwork_fallback_url: str | None = None
    sprite_url: str | None = None
    is_legendary: bool = False
    is_mythical: bool = False
    is_baby: bool = False
    gender_rate: int | None = Field(
        default=None, description="雌性比例（0–8）；-1 表示无性别；None 表示未知"
    )
    capture_rate: int | None = None
    base_happiness: int | None = None
    hatch_counter: int | None = None
    growth_rate: str | None = None
    habitat: str | None = None
    color: str | None = None
    shape: str | None = None
    egg_groups: list[str] = []

    generation_introduced: int | None
    height_dm: int | None = Field(description="身高（分米），展示层换算为米")
    weight_hg: int | None = Field(description="体重（百克），展示层换算为千克")
    prev: PokemonNeighbor | None = None
    next: PokemonNeighbor | None = None
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
    moves: dict | None = None
    genus_zh: str | None = None
    flavor_zh: str | None = None
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
    moves: dict = Field(default_factory=dict)
    generation_introduced: int | None = None
    height_dm: int | None = None
    weight_hg: int | None = None
    is_demo: bool = False


class AdminSyncRequest(BaseModel):
    """手动触发同步。"""

    start: int = Field(default=1, ge=1)
    end: int = Field(default=1025, ge=1)
    force: bool = Field(default=False, description="覆盖手动编辑过的记录")
    skip_existing: bool = Field(
        default=False, description="跳过本地已有的 PokéAPI 记录（断点续传）"
    )


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
    artwork_cached: int | None = None
    moves_covered: int | None = None
    per_generation: dict = Field(
        default_factory=dict, description="世代 → 已同步数量（1–9）"
    )


class AdminOpLogEntry(BaseModel):
    id: int
    action: str
    target: str | None
    detail: str | None
    operator: str
    created_at: str


class AdminOpLogResponse(BaseModel):
    items: list[AdminOpLogEntry]
