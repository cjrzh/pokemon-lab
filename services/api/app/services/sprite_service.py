"""宝可梦小图标（96×96 sprite）的下载与本地缓存。

用途：图鉴列表模式、特性页「拥有者」等需要「一眼认出是哪只」的小尺寸场景。
立绘（475×475）仍由 `artwork_service` 负责，两者互不替代。

来源：PokéAPI/sprites 仓库的普通 sprite（`sprites/pokemon/{dex}.png`），
经 wsrv.nl 图片代理访问 —— 与 official-artwork 同样的原因：raw.githubusercontent
在部分网络环境下直连不稳定，代理可正常返回。代理只是传输通道，图片本身来自
PokéAPI 公开仓库。

设计约定：
  - 下载失败只记 warning，不阻塞图鉴同步；界面回落到远程小图地址。
  - 已存在且非空时直接复用；`force=True` 时重下。
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: 小图标的远程地址（wsrv 代理 PokéAPI sprites 仓库）。
SPRITE_PROXY_URL = (
    "https://wsrv.nl/?url=raw.githubusercontent.com/PokeAPI/sprites/"
    "master/sprites/pokemon/{dex}.png"
)

DEFAULT_TIMEOUT_SECONDS = 20.0


def sprite_url(dex_number: int) -> str:
    """远程小图标地址（本地缓存缺失时前端使用）。"""
    return SPRITE_PROXY_URL.format(dex=dex_number)


def sprite_media_url(dex_number: int, sprite_path: str | None) -> str:
    """小图标的响应地址：本地缓存优先（`/media/...`），缺失时回落远程代理。

    与立绘相同的约定：本地路径由 `/media` 静态托管，前端 `resolveMediaUrl`
    补上 API origin 后即可离线加载。
    """
    if sprite_path:
        return f"/media/{sprite_path}"
    return sprite_url(dex_number)


async def ensure_sprite(dex_number: int, *, force: bool = False) -> str | None:
    """确保 `{dex}.png` 已缓存在 media/sprites；返回相对路径（失败返回 None）。"""
    settings = get_settings()
    target = settings.sprite_dir / f"{dex_number}.png"
    relative = f"sprites/{dex_number}.png"

    if target.exists() and target.stat().st_size > 0 and not force:
        return relative

    url = sprite_url(dex_number)
    try:
        content = await _download(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        # 先写临时文件再替换，避免中断留下半张图
        tmp = target.with_suffix(".png.part")
        tmp.write_bytes(content)
        tmp.replace(target)
        return relative
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("小图标下载失败（dex=%s）：%s", dex_number, exc)
        return None


async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        content = response.content
    if not content:
        raise httpx.HTTPError("空响应")
    return content


def local_sprite_path(dex_number: int) -> Path:
    """本地小图标的文件路径（不检查存在性）。"""
    return get_settings().sprite_dir / f"{dex_number}.png"
