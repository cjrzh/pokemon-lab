"""官方赛事接口的请求 / 响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TournamentSummary(BaseModel):
    """列表 / 详情里共用的赛事摘要。"""

    id: int
    source_id: int
    name: str
    date: str
    ruleset: str
    ruleset_label: str
    event_type: str
    event_type_label: str
    country: str | None = None
    players: int = 0
    winner: str | None = None
    winner_country: str | None = None
    format_key: str | None = Field(
        default=None,
        description="可一键建队的格式（bdsp / swsh / sv / champions）；null 表示本地无法建队",
    )
    standings_count: int = 0
    team_count: int = 0
    has_teamlists: bool = False
    source_url: str | None = None


class RulesetOption(BaseModel):
    identifier: str
    label: str
    game: str = ""
    format_key: str | None = None


class TournamentListResponse(BaseModel):
    items: list[TournamentSummary] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1
    #: 库里有数据的年份（降序）与规则（按世代倒序）
    years: list[int] = []
    rulesets: list[RulesetOption] = []


class StandingView(BaseModel):
    rank: int
    player: str
    country: str | None = None
    #: 成绩页的队伍预览（Showdown 显示名）
    species: list[str] = []
    #: Limitless 的队表 id（有公开队表时）
    team_id: int | None = None


class TeamMemberView(BaseModel):
    position: int
    dex_number: int | None = None
    showdown_name: str
    species_slug: str
    item: str | None = None
    ability: str | None = None
    nature: str | None = None
    tera_type: str | None = None
    moves: list[str] = []
    #: 超极巨化（剑盾）。赛事队表的 `-Gmax` 别名统一折算成基础形态 + 该标记，
    #: 导出的 Showdown 代码只写 `Gigantamax: Yes`。
    gigantamax: bool = False
    #: 极巨化等级 0–10（赛事未公开，按 Showdown 默认值 10）
    dynamax_level: int | None = None


class TeamView(BaseModel):
    id: int
    rank: int
    player: str
    country: str | None = None
    #: 完整 Showdown 文本（可直接复制 / 导入建队页）
    showdown_text: str = ""
    #: 无法映射到图鉴的条目说明
    problems: list[str] = []
    #: 本地规则校验结果（源站笔误如实记录，不阻断建队）
    validation: dict = Field(default_factory=dict)
    members: list[TeamMemberView] = []


class UsageEntry(BaseModel):
    rank: int
    species_slug: str
    showdown_name: str
    dex_number: int | None = None
    count: int = 0
    share: float = 0.0


class TournamentDetail(BaseModel):
    tournament: TournamentSummary
    standings: list[StandingView] = []
    #: 完整队表（赛事没有公开队表时为空）
    teams: list[TeamView] = []
    #: 由全部队表重算的使用率
    usage: list[UsageEntry] = []


class SyncRequest(BaseModel):
    """赛事同步请求。不传参数时：抓全部类型、全部年份、增量跳过已抓过的。"""

    types: list[str] | None = Field(
        default=None,
        description=(
            "赛事类型：regional / international / worlds / special / national / players_cup"
        ),
    )
    date_from: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="只抓该日期之后"
    )
    date_to: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="只抓该日期之前"
    )
    rulesets: list[str] | None = Field(default=None, description="只抓这些规则（m-c / svf …）")
    refresh: bool = Field(default=False, description="强制重抓（默认增量跳过已抓过的赛事）")


class SyncRunView(BaseModel):
    id: int
    status: str
    total: int
    done: int
    created: int
    skipped: int
    failed: int
    current: str | None = None
    message: str | None = None
    scope: dict = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None


class TeamImportView(BaseModel):
    """一键建队：从赛事队伍生成的建队草稿。"""

    tournament: TournamentSummary
    format_key: str
    #: 官方赛事页导出的默认等级（满级 100）
    default_level: int = 100
    trade_prefix: str | None = None
    points_kind: str = "ev"
    team: dict
    #: 与 `TeamCreate.members` 同结构，可直接 POST /teams
    members: list[dict] = []
    #: 本地规则校验结果（源站笔误也如实列出；不阻断，用户可在编辑器里修正）
    validation: dict = Field(default_factory=dict)
