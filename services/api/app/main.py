"""FastAPI 应用入口。

启动方式（在 services/api 目录下）：
    uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.engine import dispose_engine, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger.info("启动 %s v%s（%s）", settings.app_name, settings.version, settings.environment)

    await init_db()
    logger.info("数据库就绪：%s", settings.database_path)

    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Pokémon Lab API",
        version=settings.version,
        description=(
            "宝可梦研究所后端：图鉴检索、属性克制计算、个人收藏与笔记、大师考试。"
            "MVP 阶段仅实现上述能力，对战与强化学习不在此服务内。"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Owner-Key"],
        expose_headers=["X-Cache"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    async def read_root() -> dict[str, str]:
        """给人看的入口：直接打开后端根地址时告诉他去哪。"""
        return {
            "service": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
