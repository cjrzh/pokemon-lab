"""图鉴立绘的下载与本地缓存。

单独放在 services 层（而不是塞进 sync 服务），因为：
  - 同步脚本与后台「补抓立绘」入口都要用；
  - 图片下载不计入数据正确性 —— 失败只 warning，不影响图鉴记录落库。

图片来源是 pokemon.com 公开图鉴资源（full 475px）；pokemon.com 不可达时
不阻塞，前端会回落到 PokéAPI official-artwork 的图片代理地址。
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: 图片文件较小，单张超时比普通 API 请求宽松一些。
DEFAULT_TIMEOUT_SECONDS = 20.0


async def ensure_artwork(dex_number: int, *, force: bool = False) -> str | None:
    """确保 `{dex}.png` 已缓存在 media/artwork；返回相对路径（失败返回 None）。

    已存在且非空时直接复用（图片极少变化）；`force=True` 时强制重下。
    """
    settings = get_settings()
    target = settings.artwork_dir / f"{dex_number}.png"
    relative = f"artwork/{dex_number}.png"

    if target.exists() and target.stat().st_size > 0 and not force:
        return relative

    url = f"{settings.artwork_base_url}/{dex_number:03d}.png"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
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
        # 先写临时文件再替换，避免中断留下半张图
        tmp = target.with_suffix(".png.part")
        tmp.write_bytes(content)
        tmp.replace(target)
        return relative
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("立绘下载失败（dex=%s）：%s", dex_number, exc)
        return None
