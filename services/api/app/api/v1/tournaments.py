"""官方赛事路由：浏览、同步、一键建队。

`GET  /tournaments`                    赛事列表（规则 / 类型 / 年份 / 搜索）
`GET  /tournaments/{id}`               赛事详情（名次 + 队表 + 使用率）
`GET  /tournaments/{id}/teams/{tid}`   一支队伍的建队草稿（含 Showdown 文本）
`POST /tournaments/sync`               后台同步（增量）
`GET  /tournaments/sync/latest`        最近一次同步
`GET  /tournaments/sync/{run_id}`      同步进度
`POST /tournaments/sync/{run_id}/cancel` 取消

同步用 FastAPI 的 `BackgroundTasks`：请求返回后继续执行；同步服务自建会话。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import DbSession
from app.db.models import TournamentSyncRun
from app.domain import tournament_catalog
from app.domain.tournament_showdown import TOURNAMENT_DEFAULT_LEVEL
from app.schemas.tournaments import (
    SyncRequest,
    SyncRunView,
    TeamImportView,
    TournamentDetail,
    TournamentListResponse,
)
from app.services import tournament_service
from app.services.tournament_service import SyncScope

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


def _run_view(run: TournamentSyncRun) -> SyncRunView:
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
    response_model=TournamentListResponse,
    summary="官方赛事列表",
    description=(
        "官方赛事（地区赛 / 国际赛 / 世锦赛 / 特殊赛事 / 国家赛 / Players Cup）的成绩与队表。"
        "数据来自 Limitless VGC，按需同步、增量更新。"
    ),
)
async def list_tournaments(
    session: DbSession,
    ruleset: str | None = Query(default=None, max_length=32, description="规则标识，如 m-c"),
    event_type: str | None = Query(default=None, max_length=24, description="赛事类型"),
    format_key: str | None = Query(default=None, max_length=16, description="可建队的格式"),
    year: int | None = Query(default=None, ge=2010, le=2100),
    q: str | None = Query(default=None, max_length=64, description="赛事名或冠军"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> TournamentListResponse:
    if ruleset is not None and ruleset not in tournament_catalog.RULESET_BY_ID:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"未知规则 {ruleset!r}；可选值见 GET /tournaments 的 rulesets 字段",
        )
    if event_type is not None and event_type not in tournament_catalog.EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"赛事类型只接受 {tuple(tournament_catalog.EVENT_TYPES)}",
        )
    data = await tournament_service.list_tournaments(
        session,
        ruleset=ruleset,
        event_type=event_type,
        format_key=format_key,
        year=year,
        search=q,
        page=page,
        page_size=page_size,
    )
    return TournamentListResponse(**data)


@router.post(
    "/sync",
    response_model=SyncRunView,
    status_code=status.HTTP_202_ACCEPTED,
    summary="同步官方赛事",
    description=(
        "后台抓取 Limitless VGC 的赛事列表、成绩与队表。**增量**：已抓过且有队表的赛事跳过；"
        "`refresh=true` 强制重抓。不传参数时抓全部类型与全部年份。"
    ),
)
async def start_sync(
    session: DbSession, background: BackgroundTasks, payload: SyncRequest
) -> SyncRunView:
    running = await tournament_service.latest_run(session)
    if running is not None and running.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"已有赛事同步任务在运行（#{running.id}），请等待完成",
        )

    scope = SyncScope(
        types=tuple(payload.types) if payload.types else None,
        date_from=payload.date_from,
        date_to=payload.date_to,
        rulesets=tuple(payload.rulesets) if payload.rulesets else None,
        refresh=payload.refresh,
    )
    run = await tournament_service.start_sync(session, scope)
    run_id = run.id
    view = _run_view(run)
    # 请求结束后继续执行；同步服务自建会话（请求会话会被关闭）
    background.add_task(tournament_service.run_sync, scope, run_id)
    return view


@router.get(
    "/sync/latest",
    response_model=SyncRunView | None,
    summary="最近一次赛事同步",
)
async def latest_sync(session: DbSession) -> SyncRunView | None:
    run = await tournament_service.latest_run(session)
    return _run_view(run) if run is not None else None


@router.get(
    "/sync/{run_id}",
    response_model=SyncRunView,
    summary="赛事同步进度",
)
async def get_sync(session: DbSession, run_id: int) -> SyncRunView:
    run = await session.get(TournamentSyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="同步任务不存在")
    return _run_view(run)


@router.post(
    "/sync/{run_id}/cancel",
    response_model=SyncRunView,
    summary="取消赛事同步",
    description="标记为 cancelled；已完成的赛事保留，下次增量会继续。",
)
async def cancel_sync(session: DbSession, run_id: int) -> SyncRunView:
    run = await session.get(TournamentSyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="同步任务不存在")
    if run.status != "running":
        return _run_view(run)
    run.status = "cancelled"
    run.finished_at = datetime.now(UTC)
    run.current = None
    return _run_view(run)


@router.get(
    "/formats/options",
    summary="可选规则与赛事类型",
    description="前端筛选项：库里有数据的规则（含展示名与可建队格式）与赛事类型。",
)
async def format_options(session: DbSession) -> dict:
    rulesets = await tournament_service.stored_rulesets(session)
    return {
        "rulesets": [
            {
                "identifier": identifier,
                "label": tournament_catalog.ruleset_label(identifier),
                "format_key": tournament_catalog.format_key_for(identifier),
                # 赛事页代码 / 一键建队统一按满级 100
                "default_level": TOURNAMENT_DEFAULT_LEVEL,
            }
            for identifier in rulesets
        ],
        "event_types": [
            {"identifier": key, "label": label}
            for key, label in tournament_catalog.EVENT_TYPES.items()
        ],
    }


@router.get(
    "/{tournament_id}",
    response_model=TournamentDetail,
    summary="赛事详情",
    description="名次表 + 完整队表（含 Showdown 文本）+ 由全部队表重算的使用率。",
)
async def get_tournament(session: DbSession, tournament_id: int) -> TournamentDetail:
    data = await tournament_service.get_tournament(session, tournament_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="赛事不存在")
    return TournamentDetail(**data)


@router.get(
    "/{tournament_id}/teams/{team_id}",
    response_model=TeamImportView,
    summary="一键建队",
    description=(
        "把赛事里的一支队伍转成建队草稿（成员字段与 `POST /teams` 相同）。"
        "**不落库**：前端拿到后进入建队页，确认后再保存。"
        "赛事未公开 EV / IV，草稿里的配点为 0、等级按格式默认。"
    ),
)
async def tournament_team(
    session: DbSession, tournament_id: int, team_id: int
) -> TeamImportView:
    data = await tournament_service.usable_team(session, tournament_id, team_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="队伍不存在，或该赛事的规则本地无法建队",
        )
    return TeamImportView(**data)
