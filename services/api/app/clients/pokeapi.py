"""PokéAPI 客户端：超时、重试、缓存、降级。

策略（ARCHITECTURE.md §8）：
  1. 超时：connect/read 分别可配，默认 5s/10s。
  2. 重试：最多 N 次（默认 2）指数退避，仅对可恢复错误（5xx、网络）重试；
     4xx 是确定性错误，立即抛出。
  3. 缓存：SQLite api_cache，TTL 默认 7 天。命中未过期缓存返回 hit。
  4. 降级：上游失败且本地有旧缓存 → 返回旧数据并标 stale；
     无缓存 → 抛 UpstreamError（路由层转 503）。

对外只暴露 `fetch_json`，返回 `(payload, cache_state)`。cache_state 为
"hit" / "miss" / "stale"，路由层据此设置 `X-Cache` 响应头。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories.api_cache_repo import get_cache_entry, upsert_cache_entry

logger = logging.getLogger(__name__)

#: 命中/未命中/降级三态，供路由层设 X-Cache 头。
CacheState = str  # "hit" | "miss" | "stale"


class UpstreamError(RuntimeError):
    """PokéAPI 不可用且本地无可用缓存。路由层转 503。"""

    def __init__(self, url: str, detail: str, *, status_code: int | None = None) -> None:
        self.url = url
        self.status_code = status_code
        super().__init__(f"PokéAPI 不可用（{url}）：{detail}")


@dataclass(frozen=True)
class FetchResult:
    """`fetch_json` 的返回值。payload 为原始 JSON 文本，由调用方自行解析。"""

    payload: str
    cache_state: CacheState


def _is_retryable_status(status_code: int) -> bool:
    """429 与 5xx 视为可恢复；4xx（含 404）为确定性错误，不重试。"""
    return status_code == 429 or status_code >= 500


async def fetch_json(
    session: AsyncSession,
    path: str,
    *,
    cache_key: str | None = None,
) -> FetchResult:
    """从 PokéAPI 取 JSON 文本，带缓存与降级。

    Args:
        session: 数据库会话（用于读写 api_cache）。
        path: 相对 base_url 的路径，如 "/pokemon/1"。
        cache_key: 缓存键；默认与 path 相同。不同语义可传入自定义键。
    """
    settings = get_settings()
    key = cache_key or path
    url = f"{settings.pokeapi_base_url}{path}"
    now = time.time()

    # 1) 先查本地缓存
    entry = await get_cache_entry(session, key, now=now)
    if entry is not None and entry.fresh:
        return FetchResult(payload=entry.payload, cache_state="hit")

    # 2) 回源（带重试）
    payload_text: str | None = None
    try:
        payload_text = await _fetch_with_retry(settings, url)
    except UpstreamError:
        # 3) 降级：上游失败，但若有旧缓存就返回旧数据
        if entry is not None:
            logger.warning("PokéAPI 失败，返回旧缓存（stale）：%s", url)
            return FetchResult(payload=entry.payload, cache_state="stale")
        raise

    # 4) 写缓存
    expires_at = now + settings.pokeapi_cache_ttl_seconds
    await upsert_cache_entry(session, key, url, payload_text, expires_at)

    return FetchResult(payload=payload_text, cache_state="miss")


async def _fetch_with_retry(settings, url: str) -> str:
    """带指数退避重试的 HTTP GET。仅在可恢复错误上重试。"""
    timeout = httpx.Timeout(
        settings.pokeapi_read_timeout_seconds,
        connect=settings.pokeapi_connect_timeout_seconds,
    )
    last_status: int | None = None
    for attempt in range(settings.pokeapi_max_retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
        except httpx.TimeoutException as exc:
            last_status = None
            if attempt < settings.pokeapi_max_retries:
                await _backoff(attempt)
                continue
            raise UpstreamError(url, f"请求超时：{exc}") from exc
        except httpx.HTTPError as exc:
            last_status = None
            if attempt < settings.pokeapi_max_retries:
                await _backoff(attempt)
                continue
            raise UpstreamError(url, f"网络错误：{exc}") from exc

        if response.status_code == 200:
            return response.text

        last_status = response.status_code
        if _is_retryable_status(response.status_code) and attempt < settings.pokeapi_max_retries:
            await _backoff(attempt)
            continue

        # 4xx（如 404）或重试用尽的 5xx → 确定性失败
        raise UpstreamError(
            url,
            f"HTTP {response.status_code}",
            status_code=response.status_code,
        )

    # 理论不可达：重试循环要么返回，要么抛出
    raise UpstreamError(url, f"重试用尽（last_status={last_status}）")


async def _backoff(attempt: int) -> None:
    """指数退避：0.5s, 1s, 2s...（attempt 从 0 起）。"""
    import asyncio

    delay = 0.5 * (2**attempt)
    await asyncio.sleep(delay)


def parse_payload(payload: str) -> object:
    """把缓存或响应的 JSON 文本解析为对象。失败的解析视为上游数据损坏。"""
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise UpstreamError("(local)", f"缓存数据损坏，无法解析 JSON：{exc}") from exc
