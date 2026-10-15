"""服务自检（self-check）。

这里回答一个很实际的问题：「这个服务现在到底能不能用？」

原则是**如实报告**：还没实现的东西就报 degraded/error，不假装正常。
比如属性克制数据在 P1 才生成，在那之前 `/health` 会明确显示它是降级状态。
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.config import get_settings
from app.db.engine import session_scope
from app.schemas.health import HealthCheck

logger = logging.getLogger(__name__)


async def check_database() -> HealthCheck:
    """校验数据库可连接、可查询，并返回规模信息。"""
    settings = get_settings()
    try:
        async with session_scope() as session:
            sqlite_version = (await session.execute(text("select sqlite_version()"))).scalar_one()
            table_count = (
                await session.execute(
                    text(
                        "select count(*) from sqlite_master "
                        "where type = 'table' and name not like 'sqlite_%'"
                    )
                )
            ).scalar_one()
    except Exception as exc:
        logger.exception("数据库自检失败")
        return HealthCheck(
            name="database",
            status="error",
            detail=f"{type(exc).__name__}: {exc}",
        )

    return HealthCheck(
        name="database",
        status="ok",
        detail=f"SQLite {sqlite_version} · {settings.database_path.name} · {table_count} 张表",
    )


def check_datasets() -> HealthCheck:
    """校验仓库内规范数据文件是否就绪。"""
    settings = get_settings()

    if not settings.data_dir.is_dir():
        return HealthCheck(
            name="datasets",
            status="error",
            detail=f"规范数据目录不存在：{settings.data_dir}",
        )

    type_chart = settings.data_dir / "type-chart.json"
    if not type_chart.exists():
        return HealthCheck(
            name="datasets",
            status="degraded",
            detail="属性克制数据尚未生成（计划在 P1 交付）",
        )

    return HealthCheck(
        name="datasets",
        status="ok",
        detail=f"规范数据就绪：{type_chart.name}",
    )
