"""双打对战辅助接口的响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DoublesUsage(BaseModel):
    """一条使用率条目（特性 / 道具 / 招式 / 队友 / 太晶属性）。"""

    slug: str
    name: str = Field(description="中文名（缺失时为英文）")
    name_en: str | None = Field(
        default=None, description="Showdown 英文名（生成导出代码用；缺失时回落到 name）"
    )
    type: str | None = Field(default=None, description="招式属性（仅招式条目有值，如 fire）")
    icon_url: str | None = Field(
        default=None, description="道具图标（仅道具条目有值；本地缓存优先，缺失为 null）"
    )
    pct: float = Field(description="使用率百分比（0–100），原样来自统计")


class DoublesSpread(BaseModel):
    """一组主流配点。"""

    nature: str
    nature_label: str
    points: list[int] = Field(
        description=(
            "六项配点：HP / 攻击 / 防御 / 特攻 / 特防 / 速度。旧世代为 EV，Champions 为能力点"
        )
    )
    pct: float


class DoublesIVSuggestion(BaseModel):
    """个体值建议。

    Smogon 只统计配点，不统计 IV；这是按配点与招式推断的**建议值**，
    `inferred` 恒为 true，界面必须标注。
    """

    ivs: dict[str, int]
    reasons: list[str] = []
    inferred: bool = True


class DoublesTeammate(BaseModel):
    showdown_name: str
    dex_number: int | None = Field(default=None, description="可映射到图鉴时给出编号")
    name_zh: str | None = None
    pct: float


class DoublesTeraType(BaseModel):
    type: str
    pct: float


class DoublesProfile(BaseModel):
    """一个格式下某一形态（Showdown 名称）的统计明细。"""

    showdown_name: str = Field(description="Smogon / Showdown 显示名，如 Charizard-Mega-Y")
    rank: int | None = None
    usage: float | None = Field(default=None, description="使用率百分比（0–100）")
    raw_count: int = 0
    abilities: list[DoublesUsage] = []
    items: list[DoublesUsage] = []
    moves: list[DoublesUsage] = []
    teammates: list[DoublesTeammate] = []
    tera_types: list[DoublesTeraType] = []
    spreads: list[DoublesSpread] = []
    ivs: DoublesIVSuggestion | None = None


class DoublesFormatBlock(BaseModel):
    """一个双打格式的元数据与（可能为空的）配装列表。"""

    key: str
    label: str
    short_label: str
    game: str
    ruleset: str
    month: str = Field(description="统计月份（YYYY-MM）")
    cutoff: int = Field(description="Smogon 等级线：仅统计该分段及以上的对战")
    points_kind: Literal["ev", "stat_points"] = "ev"
    battles: int = 0
    trade_prefix: str | None = Field(
        default=None, description="导出 Showdown 代码时使用的交易命令前缀，如 !tradeSV"
    )
    default_level: int = 50
    note: str | None = None
    source_url: str | None = None
    imported_at: str | None = None
    profiles: list[DoublesProfile] = Field(
        default_factory=list, description="同一图鉴编号下的多个形态，按使用率降序"
    )


class DoublesResponse(BaseModel):
    """详情页「双打对战辅助」的完整数据：固定四个格式，无数据的格式也在列表里。"""

    dex_number: int
    formats: list[DoublesFormatBlock] = []
    has_data: bool = Field(description="任意格式是否有统计数据；前端据此决定是否显示空态提示")


class DoublesImportResponse(BaseModel):
    """后台导入结果。"""

    summary: str
    formats: int
    entries: int
    per_format: dict[str, int] = {}
    unresolved: list[str] = []


class DoublesSyncStatus(BaseModel):
    """双打数据现状（后台看板用）。"""

    format_count: int = 0
    entries: int = 0
    formats: list[dict] = Field(
        default_factory=list,
        description="每个格式的 key / 标签 / 月份 / 等级线 / 对战数 / 记录数 / 覆盖图鉴数",
    )
