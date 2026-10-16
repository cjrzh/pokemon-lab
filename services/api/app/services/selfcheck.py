"""服务自检（self-check）。

这里回答一个很实际的问题：「这个服务现在到底能不能用？」

原则是**如实报告**：还没实现的东西就报 degraded/error，不假装正常。
P1 交付属性克制核心后，datasets 检查会真正解析克制表并校验它的自洽性，
而不只是看文件在不在。
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
    """校验仓库内规范数据文件是否就绪且自洽。

    - 目录缺失 → error（服务无法工作）
    - 克制表缺失 → degraded（P1 后属配置未完成，提示运行生成脚本）
    - 克制表存在但损坏 → degraded（有文件但不可用）
    - 正常 → ok
    """
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
            detail="属性克制数据尚未生成：运行 `uv run python scripts/gen_type_chart.py`",
        )

    # 真正解析一次，确认文件未损坏（与 type_chart_service 的校验逻辑同源）
    try:
        # 延迟导入，避免 selfcheck 在数据缺失时连带触发上游异常栈
        from app.services.type_chart_service import TypeChartUnavailable, load_type_chart

        try:
            document = load_type_chart()
        except TypeChartUnavailable as exc:
            return HealthCheck(
                name="datasets",
                status="degraded",
                detail=f"属性克制数据已存在但无法解析：{exc}",
            )

        return HealthCheck(
            name="datasets",
            status="ok",
            detail=(
                f"规范数据就绪：{type_chart.name}（{len(document.types)} 属性 · {document.label}）"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 自检必须兜住一切，不能自己挂掉
        logger.exception("datasets 自检异常")
        return HealthCheck(
            name="datasets",
            status="degraded",
            detail=f"datasets 自检异常：{type(exc).__name__}: {exc}",
        )
