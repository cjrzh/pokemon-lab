"""Smogon 历史使用率：查询 + 同步接口。

`GET  /usage`                查询（月份 / 格式 / 等级线 / 搜索 / 分页）
`POST /usage/sync`           启动同步（后台任务，立即返回 run id）
`GET  /usage/sync/{id}`      查询同步进度
`GET  /usage/sync/latest`    最近一次同步记录

同步默认只补**最近 3 个月**（增量）；回补历史时显式传 `months` 或
`recent_months`。抓取范围与目录见 `domain/smogon_catalog.py`。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import DbSession
from app.db.models import UsageSyncRun
from app.domain.smogon_catalog import CUTOFFS, FORMAT_BY_ID
from app.schemas.usage_history import (
    SyncRequest,
    SyncRunView,
    UsageQueryResponse,
)
from app.services import usage_sync_service
from app.services.usage_sync_service import SyncScope

router = APIRouter(prefix="/usage", tags=["usage-history"])


def _run_view(run: UsageSyncRun) -> SyncRunView:
    try:
        scope = json.loads(run.scope_json or "{}")
    except json.JSONDecodeError:
        scope = {}
    return SyncRunView(
        id=run.id,
        status=run.status,
        total=run.total,
        done=run.done,
        created=run.created,
        skipped=run.skipped,
        failed=run.failed,
        current=run.current,
        message=run.message,
        scope=scope,
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
    )


@router.get(
    "",
    response_model=UsageQueryResponse,
    summary="历史使用率查询",
    description=(
        "按月份 / 格式 / 等级线查询 Smogon 双打使用率。未指定时返回最新月份与"
        "目录里第一个有数据的格式。同步范围见 `/usage/sync`。"
    ),
)
async def query_usage(
    session: DbSession,
    format: str | None = Query(default=None, max_length=64, description="Smogon 格式 id"),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    cutoff: int | None = Query(default=None, description="等级线：1500 / 1630 / 1760"),
    q: str | None = Query(default=None, max_length=64, description="名称或图鉴编号"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> UsageQueryResponse:
    if format is not None and format not in FORMAT_BY_ID:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"未知格式 {format!r}；可选值见 GET /usage 的 formats 字段",
        )
    if cutoff is not None and cutoff not in CUTOFFS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"cutoff 只接受 {CUTOFFS}",
        )
    data = await usage_sync_service.query_usage(
        session,
        format_id=format,
        month=month,
        cutoff=cutoff,
        search=q,
        page=page,
        page_size=page_size,
    )
    return UsageQueryResponse(**data)


@router.post(
    "/sync",
    response_model=SyncRunView,
    status_code=status.HTTP_202_ACCEPTED,
    summary="同步 Smogon 数据",
    description=(
        "启动后台同步。**增量**：库里已有的 (格式, 月份, 等级线) 直接跳过。"
        "不传参数时只补最近 3 个月；回补历史请显式传 months 或 recent_months。"
        "**单条目同步**：只传 `format_ids`（一个规则）即可只同步该规则的全部历史，"
        "再配合 `months` / `cutoffs` 可收窄到单个快照。"
    ),
)
async def start_sync(
    session: DbSession, background: BackgroundTasks, payload: SyncRequest
) -> SyncRunView:
    cutoffs = tuple(payload.cutoffs) if payload.cutoffs else CUTOFFS
    scope = SyncScope(
        months=payload.months,
        format_ids=payload.format_ids,
        cutoffs=cutoffs,
        recent_months=payload.recent_months if payload.months is None else None,
    )
    try:
        run = await usage_sync_service.start_sync(session, scope)
    except usage_sync_service.SyncBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    run_id = run.id
    view = _run_view(run)

    # 后台执行：用 FastAPI 的 BackgroundTasks（请求结束后仍会跑完），
    # 不能用 asyncio.create_task —— 任务在响应返回后可能被回收。
    # 同步本身会自建会话（请求会话在响应返回后就关闭）。
    background.add_task(usage_sync_service.run_sync, scope, run_id)
    return view


@router.get(
    "/sync/latest",
    response_model=SyncRunView | None,
    summary="最近一次同步",
)
async def latest_sync(session: DbSession) -> SyncRunView | None:
    run = await usage_sync_service.latest_run(session)
    return _run_view(run) if run is not None else None


@router.get(
    "/sync/{run_id}",
    response_model=SyncRunView,
    summary="同步进度",
)
async def get_sync(session: DbSession, run_id: int) -> SyncRunView:
    run = await session.get(UsageSyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="同步任务不存在")
    return _run_view(run)


@router.post(
    "/sync/{run_id}/cancel",
    response_model=SyncRunView,
    summary="取消同步",
    description="把任务标记为 cancelled；已下载的部分保留，下次增量会跳过。",
)
async def cancel_sync(session: DbSession, run_id: int) -> SyncRunView:
    run = await session.get(UsageSyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="同步任务不存在")
    if run.status != "running":
        return _run_view(run)
    run.status = "cancelled"
    run.finished_at = datetime.now(UTC)
    run.current = None
    return _run_view(run)
