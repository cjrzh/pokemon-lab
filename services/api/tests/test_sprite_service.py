"""小图标服务的纯函数 / 缓存行为测试（不访问网络）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services import sprite_service


def test_sprite_url_uses_proxy() -> None:
    url = sprite_service.sprite_url(25)
    assert "sprites/pokemon/25.png" in url
    assert url.startswith("https://wsrv.nl/")


def test_sprite_media_url_prefers_local() -> None:
    # 有本地缓存 → /media/...
    assert sprite_service.sprite_media_url(25, "sprites/25.png") == "/media/sprites/25.png"
    # 没有 → 远程代理
    assert "sprites/pokemon/25.png" in sprite_service.sprite_media_url(25, None)


async def test_ensure_sprite_reuses_existing_file(var_dir: Path) -> None:
    settings = get_settings()
    target = settings.sprite_dir / "25.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"png")

    # 已存在时直接返回相对路径，不发起网络请求
    assert await sprite_service.ensure_sprite(25) == "sprites/25.png"


async def test_ensure_sprite_returns_none_on_download_failure(
    var_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    async def fail(_url: str) -> bytes:
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(sprite_service, "_download", fail)
    assert await sprite_service.ensure_sprite(26) is None
