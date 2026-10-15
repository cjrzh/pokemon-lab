"""共享测试夹具。

每个用例使用独立的临时 `var` 目录，避免污染开发用的 SQLite 文件。
`get_settings()` 是 `lru_cache` 单例，所以切换配置后必须清缓存并重建引擎 ——
这由 `var_dir` 夹具统一负责，其他夹具只需依赖它。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.engine import dispose_engine, init_db
from app.main import create_app


@pytest_asyncio.fixture
async def var_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Path]:
    """把运行期目录指向临时路径，并重置配置缓存与数据库引擎。"""
    target = tmp_path / "var"
    monkeypatch.setenv("POKEMON_LAB_VAR_DIR", str(target))

    get_settings.cache_clear()
    await dispose_engine()

    yield target

    await dispose_engine()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(var_dir: Path) -> AsyncIterator[AsyncClient]:
    """进程内 HTTP 客户端。

    使用 ASGITransport 直接调用应用，不占用端口；
    但 ASGITransport 不会触发 lifespan，因此这里显式调用 `init_db()`。
    """
    _ = var_dir
    app = create_app()
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
