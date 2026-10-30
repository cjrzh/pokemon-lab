"""立绘缓存服务测试：下载成功写盘、失败不抛异常、已存在时复用。"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.services.artwork_service import ensure_artwork

_PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image"


def _patch_artifact_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """只替换 AsyncClient 的构造：artwork 服务自己创建 client，没有注入点。"""
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.pop("timeout", None)
        original_init(
            self,
            transport=httpx.MockTransport(handler),
            timeout=httpx.Timeout(5),
            **{k: v for k, v in kwargs.items() if k != "base_url"},
        )

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_ensure_artwork_downloads_and_writes_file(
    var_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(200, content=_PNG_BYTES)

    _patch_artifact_transport(monkeypatch, handler)

    relative = await ensure_artwork(1)

    assert relative == "artwork/1.png"
    target = get_settings().artwork_dir / "1.png"
    assert target.read_bytes() == _PNG_BYTES
    assert requested == ["/assets/cms2/img/pokedex/full/001.png"]


async def test_ensure_artwork_reuses_existing_file(
    var_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = get_settings().artwork_dir / "2.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_PNG_BYTES)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("已缓存时不应再请求上游")

    _patch_artifact_transport(monkeypatch, handler)

    assert await ensure_artwork(2) == "artwork/2.png"


async def test_ensure_artwork_returns_none_on_upstream_error(
    var_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    _patch_artifact_transport(monkeypatch, handler)

    assert await ensure_artwork(3) is None
    assert not (get_settings().artwork_dir / "3.png").exists()
