"""Smogon 历史使用率查询接口的响应模型。"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from app.domain.smogon_catalog import CUTOFFS, FORMAT_BY_ID

_MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


class UsageFormatInfo(BaseModel):
    """可选格式（来自目录，可能有数据也可能没有）。"""

    format_id: str
    label: str
    game: str
    ruleset: str
    kind: str = Field(description="vgc / doubles / other")
    #: 该格式在库里有数据的月份数（0 表示还没同步）
    months: int = 0


class UsageSnapshotInfo(BaseModel):
    """一个已同步的快照。"""

    format_id: str
    month: str
    cutoff: int
    battles: int
    entries: int
    fetched_at: str | None = None


class UsageEntryView(BaseModel):
    rank: int
    showdown_name: str
    dex_number: int | None = None
    name_zh: str | None = None
    name_en: str | None = None
    types: list[str] = []
    sprite_url: str | None = None
    usage: float
    raw_count: int = 0


class UsageQueryResponse(BaseModel):
    """一次查询的结果：元数据 + 排行榜。"""

    format_id: str
    format_label: str
    game: str
    ruleset: str
    month: str
    cutoff: int
    battles: int
    #: 该 (格式, 月份, 等级线) 是否有已同步的快照。False 表示「还没同步」，
    #: 而不是「同步了但榜单为空」—— 页面据此提供单条目同步入口。
    has_snapshot: bool = False
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[UsageEntryView] = []
    #: 当前可选的月份（升序）与格式（含未同步的）
    months: list[str] = []
    formats: list[UsageFormatInfo] = []
    cutoffs: list[int] = []


class SyncRequest(BaseModel):
    """同步请求。

    `recent_months` 用于「同步按钮」的默认行为（只补最近几个月）；
    显式给 `months` 时优先使用它（用于回补历史）。

    **单条目同步**（只同步当前选中的规则）就是只传 `format_ids`：
    该规则的全部历史月份 × 三档等级线都会进入增量计划；再传 `months` /
    `cutoffs` 可把范围收窄到单个快照（页面「同步该月份 / 等级线」按钮）。
    """

    months: list[str] | None = Field(default=None, description="指定月份（YYYY-MM）")
    format_ids: list[str] | None = Field(
        default=None, description="指定格式 id；只传一个即为「单条目同步」"
    )
    cutoffs: list[int] | None = Field(default=None, description="等级线；默认 1500/1630/1760")
    recent_months: int | None = Field(
        default=None, ge=1, le=240, description="只同步最近 N 个月（与 months 二选一）"
    )

    @field_validator("months")
    @classmethod
    def _check_months(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("months 不能为空；要同步全部历史请不传该字段")
        for month in value:
            if not _MONTH_PATTERN.match(month):
                raise ValueError(f"月份格式应为 YYYY-MM：{month!r}")
        return value

    @field_validator("format_ids")
    @classmethod
    def _check_formats(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("format_ids 不能为空；要同步全部格式请不传该字段")
        unknown = [format_id for format_id in value if format_id not in FORMAT_BY_ID]
        if unknown:
            raise ValueError(f"目录里没有这些格式：{', '.join(unknown)}")
        return value

    @field_validator("cutoffs")
    @classmethod
    def _check_cutoffs(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("cutoffs 不能为空；默认三档等级线")
        unknown = [cutoff for cutoff in value if cutoff not in CUTOFFS]
        if unknown:
            raise ValueError(f"cutoff 只接受 {list(CUTOFFS)}")
        return value


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
