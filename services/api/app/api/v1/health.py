"""健康检查路由。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthCheck, HealthResponse
from app.services.selfcheck import check_database, check_datasets

router = APIRouter(tags=["meta"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="服务健康检查",
    description=(
        "返回后端、数据库与规范数据文件的真实状态。"
        "任一检查项非 ok 时整体状态为 degraded —— 不会为了「看起来正常」而掩盖未完成的模块。"
    ),
)
async def read_health() -> HealthResponse:
    settings = get_settings()

    checks: list[HealthCheck] = [await check_database(), check_datasets()]
    overall = "ok" if all(check.status == "ok" for check in checks) else "degraded"

    return HealthResponse(
        status=overall,
        service=settings.app_name,
        version=settings.version,
        generated_at=datetime.now(UTC),
        checks=checks,
    )
