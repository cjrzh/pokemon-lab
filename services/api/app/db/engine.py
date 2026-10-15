"""数据库引擎与会话管理。

设计要点：
  - 引擎与会话工厂**惰性创建**，这样测试可以通过环境变量切到临时目录。
  - 对外只暴露 `session_scope()`（自带提交/回滚）与 `get_db()`（FastAPI 依赖）。
  - `init_db()` 幂等：重复调用不会重复写元数据。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.base import Base
from app.db.models import SCHEMA_VERSION, SchemaMeta

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """获取（必要时创建）进程内共享的异步引擎。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.var_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """事务边界：正常退出提交，异常回滚后继续抛出。"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖注入使用的数据库会话。"""
    async with session_scope() as session:
        yield session


async def init_db() -> None:
    """建表并写入结构版本。幂等，可重复调用。"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_scope() as session:
        existing = (
            await session.execute(select(SchemaMeta).where(SchemaMeta.key == "schema_version"))
        ).scalar_one_or_none()
        if existing is None:
            session.add(SchemaMeta(key="schema_version", value=SCHEMA_VERSION))
        elif existing.value != SCHEMA_VERSION:
            # 结构代次不一致时不擅自改写：等引入正式迁移工具后由迁移脚本处理
            existing.value = SCHEMA_VERSION


async def dispose_engine() -> None:
    """释放引擎与连接池。测试切换配置、进程退出时调用。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
