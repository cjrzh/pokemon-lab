"""api_cache 仓储：读写 PokéAPI 落盘缓存。

只做 SQL/ORM 读写，不含业务判断。时间统一用 Unix 时间戳（秒）存储 `expires_at`，
这样「是否过期」的判断只需一次数值比较，不依赖数据库时区设置。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiCache


@dataclass(frozen=True)
class CacheEntry:
    """缓存命中结果。`fresh` 为 False 表示已过期但仍可用（降级路径）。"""

    payload: str
    fetched_at: datetime
    expires_at: float
    fresh: bool


async def get_cache_entry(
    session: AsyncSession, cache_key: str, *, now: float
) -> CacheEntry | None:
    """读取缓存条目；不存在返回 None，存在则标注是否仍在有效期内。"""
    row = (
        await session.execute(select(ApiCache).where(ApiCache.cache_key == cache_key))
    ).scalar_one_or_none()
    if row is None:
        return None
    return CacheEntry(
        payload=row.payload,
        fetched_at=row.fetched_at,
        expires_at=row.expires_at,
        fresh=row.expires_at > now,
    )


async def upsert_cache_entry(
    session: AsyncSession,
    cache_key: str,
    url: str,
    payload: str,
    expires_at: float,
) -> None:
    """写入或覆盖一条缓存（命中主键则更新 payload 与时间）。"""
    row = (
        await session.execute(select(ApiCache).where(ApiCache.cache_key == cache_key))
    ).scalar_one_or_none()
    if row is None:
        session.add(
            ApiCache(
                cache_key=cache_key,
                url=url,
                payload=payload,
                expires_at=expires_at,
            )
        )
    else:
        row.url = url
        row.payload = payload
        row.expires_at = expires_at
        row.fetched_at = datetime.now(UTC)
