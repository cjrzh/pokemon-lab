"""数据库引擎与会话管理。

设计要点：
  - 引擎与会话工厂**惰性创建**，这样测试可以通过环境变量切到临时目录。
  - 对外只暴露 `session_scope()`（自带提交/回滚）与 `get_db()`（FastAPI 依赖）。
  - `init_db()` 幂等：重复调用不会重复写元数据。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event, select
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

#: SQLite 写锁等待时长（毫秒）。后台同步逐条提交后，正常读写不会互相阻塞；
#: 这个值只用于兜底短暂的写冲突，避免直接抛 "database is locked"。
SQLITE_BUSY_TIMEOUT_MS = 5000


def get_engine() -> AsyncEngine:
    """获取（必要时创建）进程内共享的异步引擎。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.var_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(settings.database_url, future=True)
        _configure_sqlite(_engine)
    return _engine


def _configure_sqlite(engine: AsyncEngine) -> None:
    """WAL 模式 + busy timeout：浏览请求与后台同步并发时不互相卡死。

    WAL 让读不阻塞写、写不阻塞读；busy timeout 让偶发写冲突稍等而不是立刻报错。
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()


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
    """建表并写入结构版本。幂等，可重复调用。

    `create_all` 只建缺失的表，不会给已存在的表加列。P2 打磨新增了图片 / 档案 /
    招式等列，这里用 ALTER TABLE 补齐旧库（SQLite 支持 ADD COLUMN，且这些列都
    可空或有默认值）。正式迁移工具引入后由迁移脚本接管。
    """
    engine = get_engine()
    async with engine.begin() as conn:
        # move_learner 是纯派生表：结构变更时直接丢弃重建，无需保留数据。
        # （create_all 只建缺失的表，不会改列，因此先在这里处理旧结构。）
        await _drop_stale_move_learner(conn)
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_pokemon_columns(conn)
        await _add_missing_doubles_columns(conn)
        await _add_missing_move_columns(conn)

    async with session_scope() as session:
        existing = (
            await session.execute(select(SchemaMeta).where(SchemaMeta.key == "schema_version"))
        ).scalar_one_or_none()
        if existing is None:
            session.add(SchemaMeta(key="schema_version", value=SCHEMA_VERSION))
        elif existing.value != SCHEMA_VERSION:
            # 结构代次不一致时不擅自改写：等引入正式迁移工具后由迁移脚本处理
            existing.value = SCHEMA_VERSION


#: P2 打磨新增的列 → SQLite 列定义。旧库缺列时按此补齐。
_POKEMON_ADDED_COLUMNS: dict[str, str] = {
    "name_ja": "VARCHAR(64)",
    "moves_json": "TEXT NOT NULL DEFAULT '{}'",
    "genus_zh": "VARCHAR(64)",
    "genus_en": "VARCHAR(64)",
    "flavor_zh": "TEXT",
    "flavor_en": "TEXT",
    "flavor_zh_source": "VARCHAR(16)",
    "genus_zh_source": "VARCHAR(16)",
    "artwork_path": "VARCHAR(255)",
    "artwork_url": "VARCHAR(512)",
    "sprite_url": "VARCHAR(512)",
    "sprite_path": "VARCHAR(255)",
    "cry_url": "VARCHAR(512)",
    "is_legendary": "BOOLEAN NOT NULL DEFAULT 0",
    "is_mythical": "BOOLEAN NOT NULL DEFAULT 0",
    "is_baby": "BOOLEAN NOT NULL DEFAULT 0",
    "gender_rate": "INTEGER",
    "capture_rate": "INTEGER",
    "base_happiness": "INTEGER",
    "hatch_counter": "INTEGER",
    "growth_rate": "VARCHAR(32)",
    "habitat": "VARCHAR(32)",
    "color": "VARCHAR(32)",
    "shape": "VARCHAR(32)",
    "egg_groups_json": "TEXT NOT NULL DEFAULT '[]'",
}


async def _add_missing_pokemon_columns(conn) -> None:
    """给已存在的 pokemon 表补齐新列（幂等）。"""
    rows = (await conn.exec_driver_sql("PRAGMA table_info(pokemon)")).fetchall()
    if not rows:
        return  # 表刚由 create_all 建好，列已齐全
    existing_columns = {row[1] for row in rows}
    for column, definition in _POKEMON_ADDED_COLUMNS.items():
        if column in existing_columns:
            continue
        await conn.exec_driver_sql(f'ALTER TABLE pokemon ADD COLUMN "{column}" {definition}')


#: 双打格式表新增的列 → SQLite 列定义（旧库补齐用）。
_DOUBLES_FORMAT_ADDED_COLUMNS: dict[str, str] = {
    "trade_prefix": "VARCHAR(32)",
    "default_level": "INTEGER NOT NULL DEFAULT 50",
}


async def _add_missing_doubles_columns(conn) -> None:
    """给已存在的 doubles_format 表补齐新列（幂等）。"""
    rows = (await conn.exec_driver_sql("PRAGMA table_info(doubles_format)")).fetchall()
    if not rows:
        return
    existing_columns = {row[1] for row in rows}
    for column, definition in _DOUBLES_FORMAT_ADDED_COLUMNS.items():
        if column in existing_columns:
            continue
        await conn.exec_driver_sql(f'ALTER TABLE doubles_format ADD COLUMN "{column}" {definition}')


#: 招式参考表新增的列 → SQLite 列定义（旧库补齐用）。
_MOVE_ADDED_COLUMNS: dict[str, str] = {
    "name_en": "VARCHAR(64)",
    "is_machine": "BOOLEAN NOT NULL DEFAULT 0",
    "learner_count": "INTEGER NOT NULL DEFAULT 0",
}


async def _add_missing_move_columns(conn) -> None:
    """给已存在的 move_ref 表补齐新列（幂等）。"""
    rows = (await conn.exec_driver_sql("PRAGMA table_info(move_ref)")).fetchall()
    if not rows:
        return
    existing_columns = {row[1] for row in rows}
    for column, definition in _MOVE_ADDED_COLUMNS.items():
        if column in existing_columns:
            continue
        await conn.exec_driver_sql(f'ALTER TABLE move_ref ADD COLUMN "{column}" {definition}')


async def _drop_stale_move_learner(conn) -> None:
    """旧结构的 move_learner（缺 version_groups_json）直接删除，交给 create_all 重建。"""
    rows = (await conn.exec_driver_sql("PRAGMA table_info(move_learner)")).fetchall()
    if not rows:
        return
    columns = {row[1] for row in rows}
    if "version_groups_json" not in columns:
        await conn.exec_driver_sql("DROP TABLE move_learner")


async def dispose_engine() -> None:
    """释放引擎与连接池。测试切换配置、进程退出时调用。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
