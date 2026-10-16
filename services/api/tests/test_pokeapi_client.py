"""PokéAPI 客户端测试：缓存命中、TTL、重试、降级。

用 httpx.MockTransport 模拟上游，不依赖网络，也不引入 respx。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.pokeapi import UpstreamError, fetch_json
from app.core.config import get_settings
from app.db.engine import dispose_engine, get_session_factory, init_db
from app.repositories.api_cache_repo import get_cache_entry, upsert_cache_entry


@pytest_asyncio.fixture
async def db_session(var_dir: Path) -> AsyncIterator[AsyncSession]:
    """独立数据库会话（不复用 client 夹具，因为这里测的是 clients 层）。"""
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        yield session
    await dispose_engine()


class FetchResultStub:
    """`fetch_json` 的替身返回值：payload 文本 + 缓存状态。

    供需要 mock 整个 fetch_json 的测试（如 test_dex_api 的同步流程）使用 ——
    比劫持全局 httpx.AsyncClient 更安全，不波及 ASGI 测试客户端本身。
    """

    def __init__(self, payload: str, cache_state: str = "miss") -> None:
        self.payload = payload
        self.cache_state = cache_state


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """把 AsyncClient 的构造替换为带 MockTransport 的版本。

    仅适用于「测试自身不创建其他 httpx.AsyncClient」的场景（本文件的 db_session 夹具）。
    若测试还持有 ASGI 测试客户端，请改用 FetchResultStub + patch fetch_json。
    """
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.pop("timeout", None)
        original_init(
            self,
            transport=httpx.MockTransport(handler),
            timeout=httpx.Timeout(30),
            **{k: v for k, v in kwargs.items() if k != "base_url"},
        )

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_fetch_json_miss_then_hit(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """第一次 miss 并写缓存；第二次同 key 直接命中缓存，不再发请求。"""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"name": "bulbasaur", "id": 1})

    _patch_transport(monkeypatch, handler)

    first = await fetch_json(db_session, "/pokemon/1")
    assert first.cache_state == "miss"
    assert first.payload
    assert calls == ["/api/v2/pokemon/1"]

    second = await fetch_json(db_session, "/pokemon/1")
    assert second.cache_state == "hit"
    assert json.loads(second.payload) == {"name": "bulbasaur", "id": 1}
    # 上游只被请求了一次
    assert calls == ["/api/v2/pokemon/1"]


async def test_fetch_json_retries_on_5xx_then_succeeds(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """5xx 触发重试；重试成功时正常返回 miss。退避被压缩为 0 避免测试变慢。"""
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 2:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr("app.clients.pokeapi._backoff", _fake_backoff)

    result = await fetch_json(db_session, "/pokemon/25")
    assert result.cache_state == "miss"
    assert json.loads(result.payload) == {"ok": True}
    assert len(attempts) == 2


async def test_fetch_json_does_not_retry_on_404(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """404 是确定性错误：立即抛 UpstreamError，不重试。"""
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(404, json={"detail": "Not found."})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr("app.clients.pokeapi._backoff", _fake_backoff)

    with pytest.raises(UpstreamError, match="404"):
        await fetch_json(db_session, "/pokemon/99999")
    assert len(attempts) == 1


async def test_fetch_json_degrades_to_stale_cache(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """上游失败 + 本地有过期缓存 → 返回旧数据并标 stale。"""
    # 预置一条已过期缓存
    await upsert_cache_entry(
        db_session,
        "/pokemon/1",
        "https://pokeapi.co/api/v2/pokemon/1",
        '{"id": 1, "stale": true}',
        expires_at=0.0,
    )
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr("app.clients.pokeapi._backoff", _fake_backoff)

    result = await fetch_json(db_session, "/pokemon/1")
    assert result.cache_state == "stale"
    assert json.loads(result.payload) == {"id": 1, "stale": True}


async def test_fetch_json_raises_upstream_error_when_no_cache(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """上游失败且无缓存 → UpstreamError（路由层转 503），不静默丢请求。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr("app.clients.pokeapi._backoff", _fake_backoff)

    with pytest.raises(UpstreamError):
        await fetch_json(db_session, "/pokemon/2")


async def test_fetch_json_writes_ttl_from_settings(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """缓存过期时间 = now + TTL（默认 7 天）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 3})

    _patch_transport(monkeypatch, handler)

    import time

    before = time.time()
    await fetch_json(db_session, "/pokemon/3")
    settings = get_settings()

    entry = await get_cache_entry(db_session, "/pokemon/3", now=time.time())
    assert entry is not None
    assert entry.fresh
    assert before + settings.pokeapi_cache_ttl_seconds - 5 < entry.expires_at


async def _fake_backoff(_attempt: int) -> None:
    """测试用退避：立即返回，避免指数等待拖慢测试。"""
    return None
