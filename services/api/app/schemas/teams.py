"""双打队伍的请求 / 响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.team_rules import STAT_COUNT, TEAM_SIZE

#: Showdown 支持的语言标记。导出时的 `Language:` 行取值。
LANGUAGES = ("CHS", "CHT", "ENG", "JPN", "KOR", "FRA", "GER", "ITA", "ESP")
DEFAULT_LANGUAGE = "CHS"


class TeamMemberInput(BaseModel):
    """一只宝可梦的配置（提交用）。"""

    dex_number: int = Field(ge=1, le=10000)
    showdown_name: str = Field(max_length=64, description="Showdown 显示名（含形态）")
    nickname: str | None = Field(default=None, max_length=32)
    item: str | None = Field(default=None, max_length=64, description="Showdown 英文道具名")
    ability: str | None = Field(default=None, max_length=64)
    nature: str | None = Field(default=None, max_length=16, description="性格 slug，如 adamant")
    evs: list[int] = Field(default_factory=lambda: [0] * STAT_COUNT)
    ivs: list[int] | None = None
    moves: list[str] = Field(default_factory=list)
    tera_type: str | None = Field(default=None, max_length=16)
    gender: Literal["M", "F"] | None = None
    shiny: bool = False
    level: int | None = Field(default=None, ge=1, le=100)
    #: 极巨化等级 0–10（仅剑盾有意义；Showdown 默认 10，NULL 表示按默认值）。
    #: 极巨化后的 HP 倍率随等级提高，所以它是配置的一部分而不是展示信息。
    dynamax_level: int | None = Field(default=None, ge=0, le=10)
    #: 超极巨化（仅剑盾；只有带 G 形态的物种合法）。导出为 `Gigantamax: Yes`。
    gigantamax: bool = False
    language: Literal[LANGUAGES] = Field(  # type: ignore[valid-type]
        default=DEFAULT_LANGUAGE, description="导出语言标记，缺省 CHS"
    )

    @field_validator("evs", "ivs")
    @classmethod
    def _check_length(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(value) != STAT_COUNT:
            raise ValueError(f"配点应为 {STAT_COUNT} 项")
        return value


class TeamCreate(BaseModel):
    """新建队伍。"""

    name: str = Field(min_length=1, max_length=64)
    format_key: str = Field(description="bdsp / swsh / sv / champions")
    note: str | None = Field(default=None, max_length=500)
    members: list[TeamMemberInput] = Field(default_factory=list, max_length=TEAM_SIZE)


class TeamUpdate(BaseModel):
    """更新队伍（字段缺省表示不变）。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=500)
    members: list[TeamMemberInput] | None = Field(default=None, max_length=TEAM_SIZE)


class ValidationIssue(BaseModel):
    """一条校验问题。`field` 用于前端定位到具体输入框。"""

    field: str
    message: str


class TeamValidationResult(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = []
    warnings: list[str] = Field(
        default_factory=list, description="数据缺失等非阻断提示（如本地没有该版本招式数据）"
    )
    #: 本地数据可能落后于当前规则时，把「数据缺口」和「配置确实非法」区分开：
    #: 例如官方赛事里合法的招式，本地 PokéAPI 数据里还没有。
    data_warnings: list[str] = Field(
        default_factory=list,
        description="疑似本地数据缺口（不是配置错误）：官方赛事会出现的招式 / 形态本地未收录",
    )


class TeamMemberView(TeamMemberInput):
    """响应里的成员（与提交字段一致，外加槽位与形态）。

    `form` 由后端按 `showdown_name` 反查得到（已保存的队伍只存 Showdown 名）：
    这样重新打开队伍时，形态选择器能定位到当初选的那一项，而不是默认形态。
    """

    position: int
    form: str | None = Field(
        default=None, description="本地形态 slug（`pokemon_form.name`）；默认形态为 null"
    )


# ---------------------------- 队伍评价 ----------------------------


class AnalysisMember(BaseModel):
    dex_number: int | None
    name: str
    types: list[str] = []


class AnalysisAttack(BaseModel):
    type: str
    type_zh: str
    hits: list[str] = []
    hits_zh: list[str] = []
    member_count: int = 0


class AnalysisHotspot(BaseModel):
    type: str
    type_zh: str
    members: list[int] = []


class AnalysisLlm(BaseModel):
    text: str
    model: str | None = None


class TeamAnalysis(BaseModel):
    """队伍评价：计算结果 + LLM 解读。

    `llm` 为 None 且 `llm_error` 有值时，说明计算成功但 AI 建议不可用 ——
    前端应展示计算部分并提示，而不是整体报错。
    """

    members: list[AnalysisMember] = []
    attack: list[AnalysisAttack] = []
    gaps: list[str] = []
    gaps_zh: list[str] = []
    hotspots: list[AnalysisHotspot] = []
    llm: AnalysisLlm | None = None
    llm_error: str | None = None


class TeamAnalyzeRequest(BaseModel):
    """队伍评价请求（不落库，用于编辑器里的临时草稿）。"""

    members: list[TeamMemberInput] = Field(max_length=TEAM_SIZE)
    #: 队伍所在版本，决定 Showdown 里是否输出太晶属性、默认等级等。
    format_key: str = Field(default="sv", description="bdsp / swsh / sv / champions")
    #: 是否调用 LLM 生成建议；False 时只返回属性层面的计算（响应更快）。
    use_llm: bool = Field(default=True, description="是否调用 LLM 生成改进建议与玩法推荐")


class StoredAnalysis(BaseModel):
    """落库的队伍评价（列表 / 详情里带出）。

    `stale=True` 表示评价生成后队伍成员又改过，这份结论已不对应当前配置，
    前端应提示「队伍已改动，建议更新评价」而不是继续当成最新结论展示。
    """

    analysis: TeamAnalysis
    generated_at: str | None = None
    stale: bool = False


class TeamSummary(BaseModel):
    """列表项。"""

    id: int
    name: str
    format_key: str
    format_label: str | None = None
    note: str | None = None
    member_count: int = 0
    updated_at: str | None = None
    #: 是否有已保存的队伍评价（列表只给标志，详情才带完整内容）。
    has_analysis: bool = False


class TeamDetail(TeamSummary):
    members: list[TeamMemberView] = []
    trade_prefix: str | None = None
    default_level: int = 50
    points_kind: Literal["ev", "stat_points"] = "ev"
    #: 上次保存的队伍评价（未评价过为 None）。
    analysis: StoredAnalysis | None = None


class TeamReorderRequest(BaseModel):
    """拖拽排序后的完整队伍 id 列表（按显示顺序）。"""

    team_ids: list[int] = Field(min_length=0, description="队伍 id，按新的显示顺序")


class TeamListResponse(BaseModel):
    items: list[TeamSummary]
    formats: list[dict] = Field(
        default_factory=list, description="可建队的格式（已导入统计的版本）"
    )


class TeamFormatsResponse(BaseModel):
    formats: list[dict]


class TeamImportRequest(BaseModel):
    """导入 Showdown 队伍文本。"""

    format_key: str = Field(description="bdsp / swsh / sv / champions")
    text: str = Field(min_length=1, max_length=20_000, description="Showdown 导出的队伍代码")


class TeamImportResponse(BaseModel):
    """导入结果：解析出的成员 + 跳过原因。

    `members` 不落库，前端拿到后进编辑器让用户确认；`problems` 是未能导入的条目
    （物种名无法识别、重复、超过 6 只…），如实列出而不是静默丢弃。
    """

    format_key: str
    members: list[TeamMemberInput] = []
    problems: list[str] = []
    warnings: list[str] = []


class TeamBatchRequest(BaseModel):
    """批量修改成员配置（不落库，返回改好的成员给前端进草稿）。

    三个字段都是「显式传了才改」：用 `model_fields_set` 区分「没传」与「传了 null」
    —— 前者不动，后者表示恢复默认（等级按格式 / 性别不指定）。
    """

    members: list[TeamMemberInput] = Field(max_length=TEAM_SIZE)
    shine: bool | None = Field(default=None, description="统一设为闪光 / 非闪光")
    level: int | None = Field(
        default=None, ge=1, le=100, description="统一等级；显式传 null 表示按格式默认"
    )
    gender: Literal["M", "F"] | None = Field(
        default=None, description="统一性别；显式传 null 表示不指定"
    )


class TeamBatchResponse(BaseModel):
    """批量修改结果。"""

    members: list[TeamMemberView] = []
    #: 因规则限制保持原样的成员说明（如尼多朗只能雄性）
    skipped: list[str] = []


class TeamOptionUsage(BaseModel):
    """建队时的候选条目（带使用率，供「按推荐默认选择」）。"""

    slug: str
    name: str
    name_en: str | None = None
    type: str | None = None
    icon_url: str | None = None
    pct: float


class TeamFormOption(BaseModel):
    """建队时可选的形态。

    形态决定属性、种族值、专属招式与 Showdown 名（如 `Rotom-Wash`）。
    默认形态也用一项表示（`form=None`），列表顺序即使用率降序 ——
    第一次加入宝可梦时前端直接选第一项。
    """

    #: 本地形态 slug（`pokemon_form.name`）；默认形态为 None
    form: str | None = None
    label: str
    #: Showdown 显示名（导出与统计口径）
    showdown_name: str
    types: list[str] = []
    sprite_url: str | None = None
    #: 该形态在统计里的使用率（百分比）；没有统计时为 None
    usage: float | None = None
    #: 是否为默认形态
    is_default: bool = False


class TeamMemberOptions(BaseModel):
    """某只宝可梦在某个格式下的建队选项。"""

    dex_number: int
    showdown_name: str
    name_zh: str | None = None
    name_en: str | None = None
    types: list[str] = []
    artwork_url: str | None = None
    sprite_url: str | None = None
    gender_rate: int | None = None
    #: 当前生效的形态（默认形态为 None）
    form: str | None = Field(default=None, description="当前形态的本地 slug；默认形态为 null")
    #: 可选形态（按使用率降序；只有一种形态时为空）
    forms: list[TeamFormOption] = Field(
        default_factory=list, description="可切换的形态（含默认形态），按使用率降序"
    )

    legal_moves: list[TeamOptionUsage] = Field(
        default_factory=list, description="该格式可学的全部招式（不在统计里也保留）"
    )
    legal_abilities: list[TeamOptionUsage] = []
    legal_items: list[TeamOptionUsage] = Field(
        default_factory=list,
        description=(
            "该格式统计里出现过的道具（按使用率降序），供下拉框候选；"
            "统计里没有这只宝可梦时为空，前端回落到道具百科的全量列表"
        ),
    )
    recommended: dict | None = Field(
        default=None, description="统计推荐：特性 / 道具 / 招式 / 配点 / 性格 / IV 建议"
    )
    has_stats: bool = Field(default=False, description="该格式是否有这只宝可梦的使用率统计")
    #: 该形态是否能超极巨化（只有剑盾有实际意义；清单来自 Showdown pokedex）
    can_gigantamax: bool = Field(
        default=False, description="是否有超极巨化形态（建队页据此显示开关）"
    )
    #: 超极巨化后的 G 招式名（`G-Max Wildfire`），用于界面说明；没有时为 None
    gigantamax_move: str | None = Field(
        default=None, description="超极巨化专属招式名（如 G-Max Wildfire）"
    )
    #: 请求了 G 形态（`form=xxx-gmax`）时为 True；正常选形态时为 False
    gigantamax: bool = Field(
        default=False, description="是否按超极巨化形态返回（编辑器据此勾选开关）"
    )
