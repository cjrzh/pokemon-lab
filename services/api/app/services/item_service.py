"""道具参考数据与图标的同步（PokéAPI `/item/{slug}`）。

职责：
  - 解析道具中文名（zh-hans → zh-hant）、英文名、分类、英文短说明与成本；
  - 下载 30×30 图标到 `media/items/{slug}.png`（wsrv 代理 PokéAPI sprites 仓库）；
  - 把结果写入 `item_ref` 表（按 slug 幂等 upsert）。

只同步「双打统计里实际出现过的道具」而不是 PokéAPI 全部 2223 个条目，
避免为了 257 个道具去拉整本图鉴道具库。新增格式数据后重跑一次即可。
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ItemReference

logger = logging.getLogger(__name__)

#: PokéAPI 公开接口（与图鉴同步共用同一个上游，无需密钥）。
POKEAPI_ITEM_URL = "https://pokeapi.co/api/v2/item/{slug}"

#: 图标经 wsrv 代理（直连 raw.githubusercontent 在部分网络下不稳定）。
ITEM_ICON_PROXY = (
    "https://wsrv.nl/?url=raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/{slug}.png"
)

#: PokéAPI 用 `stick` 表示 Showdown 的 `leek`（大葱）。
POKEAPI_SLUG_ALIASES = {"leek": "stick"}

#: 本地标签里存在、但 PokéAPI 没有对应条目的道具：保留手写中文名与图标别名，
#: 不猜译、不虚构图标（`pretty-feather` 在上游没有单独条目）。
LOCAL_ONLY_ITEMS: dict[str, dict] = {
    "pretty-feather": {"zh": "美丽之羽", "name_en": "Pretty Feather", "category": "collectibles"},
}

DEFAULT_CONCURRENCY = 8
DEFAULT_TIMEOUT_SECONDS = 25.0


@dataclass
class ItemSyncResult:
    """一次道具同步的结果。"""

    synced: list[str] = field(default_factory=list)
    icons: int = 0
    failed: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"道具同步：写入 {len(self.synced)} 个，图标 {self.icons} 张，失败 {len(self.failed)}"
        )


@dataclass(frozen=True)
class ItemPayload:
    """解析后的道具条目。"""

    name: str
    zh: str | None
    name_en: str | None
    category: str | None
    effect_en: str | None
    cost: int | None
    icon_url: str | None


def _pick_localized(entries: list[dict], languages: tuple[str, ...]) -> str | None:
    """按优先级取本地化名称（zh-hans 优先，缺失回落 zh-hant）。"""
    by_lang: dict[str, str] = {}
    for entry in entries or []:
        language = (entry.get("language") or {}).get("name")
        value = entry.get("name")
        if language and value:
            by_lang[language] = value
    for language in languages:
        if language in by_lang:
            return by_lang[language]
    return None


def _pick_effect(payload: dict) -> str | None:
    """英文短说明（PokéAPI 的 zh-hans 说明缺失较多，保留英文原文不猜译）。"""
    for entry in payload.get("effect_entries", []) or []:
        if (entry.get("language") or {}).get("name") == "en":
            text = (entry.get("short_effect") or entry.get("effect") or "").strip()
            if text:
                return re.sub(r"\s+", " ", text)
    return None


def parse_item(slug: str, payload: dict) -> ItemPayload:
    """把 PokéAPI `/item/{slug}` 响应解析成 `item_ref` 字段。

    `name` 始终用统计里的 slug（不改成 PokéAPI 的别名），保证与
    `doubles_pokemon_stat.items_json` 中的键一一对应。
    """
    sprites = payload.get("sprites") or {}
    icon = sprites.get("default") if isinstance(sprites, dict) else None
    cost = payload.get("cost")
    return ItemPayload(
        name=slug,
        zh=_pick_localized(payload.get("names", []), ("zh-hans", "zh-hant")),
        name_en=_pick_localized(payload.get("names", []), ("en",)),
        category=(payload.get("category") or {}).get("name"),
        effect_en=_pick_effect(payload),
        cost=cost if isinstance(cost, int) else None,
        icon_url=icon if isinstance(icon, str) and icon else None,
    )


def icon_proxy_url(slug: str) -> str:
    """远程图标地址：优先用 PokéAPI 返回的地址，经 wsrv 代理转换。"""
    return (
        f"https://wsrv.nl/?url=raw.githubusercontent.com/PokeAPI/sprites/"
        f"master/sprites/items/{slug}.png"
    )


def icon_media_url(slug: str, icon_path: str | None) -> str | None:
    """页面使用的图标地址：本地优先，缺失时回落到远程代理；都没有返回 None。"""
    if icon_path:
        return f"/media/{icon_path}"
    if slug in LOCAL_ONLY_ITEMS:
        return None
    return icon_proxy_url(slug)


async def ensure_item_icon(slug: str, *, force: bool = False) -> str | None:
    """确保 `{slug}.png` 已缓存在 media/items；返回相对路径（失败返回 None）。

    图标文件名用**统计里的 slug**（而不是 PokéAPI 的别名），保证 `icon_path`
    与 `doubles_pokemon_stat.items_json` 的键一致；别名只影响上游地址。
    """
    settings = get_settings()
    target = settings.item_icon_dir / f"{slug}.png"
    relative = f"items/{slug}.png"

    if target.exists() and target.stat().st_size > 0 and not force:
        return relative

    upstream = POKEAPI_SLUG_ALIASES.get(slug, slug)
    url = (
        f"https://wsrv.nl/?url=raw.githubusercontent.com/PokeAPI/sprites/"
        f"master/sprites/items/{upstream}.png"
    )
    try:
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
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".png.part")
        tmp.write_bytes(content)
        tmp.replace(target)
        return relative
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("道具图标下载失败（%s）：%s", slug, exc)
        return None


async def fetch_item(client: httpx.AsyncClient, slug: str) -> dict | None:
    """拉取单个道具；PokéAPI 404 时返回 None（调用方回落到本地标签）。"""
    upstream = POKEAPI_SLUG_ALIASES.get(slug, slug)
    response = await client.get(POKEAPI_ITEM_URL.format(slug=upstream))
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def sync_items(
    session: AsyncSession,
    slugs: list[str],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    download_icons: bool = True,
) -> ItemSyncResult:
    """同步指定道具的元数据与图标（幂等）。

    单个道具失败不影响其它条目：失败原因写进结果，已成功的照常落库。
    """
    result = ItemSyncResult()
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
        follow_redirects=True,
    ) as client:

        async def load(slug: str) -> tuple[str, ItemPayload | None, str | None]:
            async with semaphore:
                local = LOCAL_ONLY_ITEMS.get(slug)
                if local is not None:
                    payload = ItemPayload(
                        name=slug,
                        zh=local.get("zh"),
                        name_en=local.get("name_en"),
                        category=local.get("category"),
                        effect_en=None,
                        cost=None,
                        icon_url=None,
                    )
                    return slug, payload, None
                try:
                    payload = await fetch_item(client, slug)
                except httpx.HTTPError as exc:
                    return slug, None, f"上游请求失败：{exc}"
                if payload is None:
                    return slug, None, "PokéAPI 无此道具（404）"
                icon_path = None
                if download_icons:
                    icon_path = await ensure_item_icon(slug)
                return slug, parse_item(slug, payload), icon_path

        rows = await asyncio.gather(*(load(slug) for slug in slugs))

    existing = {
        row.name: row for row in (await session.execute(select(ItemReference))).scalars().all()
    }

    for slug, payload, extra in rows:
        if payload is None:
            result.failed[slug] = extra or "解析失败"
            continue
        icon_path = extra if download_icons else None
        row = existing.get(slug)
        if row is None:
            row = ItemReference(name=slug)
            session.add(row)
        row.zh = payload.zh
        row.name_en = payload.name_en
        row.category = payload.category
        row.effect_en = payload.effect_en
        row.cost = payload.cost
        row.icon_url = payload.icon_url or (
            None if slug in LOCAL_ONLY_ITEMS else icon_proxy_url(slug)
        )
        # 上游图标与本地下载二者取其一：下载成功时记本地路径
        row.icon_path = icon_path or row.icon_path
        result.synced.append(slug)
        if icon_path:
            result.icons += 1

    await session.flush()
    return result


async def list_registered(session: AsyncSession) -> dict[str, ItemReference]:
    """slug → 道具记录（页面组装用）。"""
    rows = (await session.execute(select(ItemReference))).scalars().all()
    return {row.name: row for row in rows}


def icon_file(slug: str) -> Path:
    """本地图标文件路径（不检查存在性）。"""
    return get_settings().item_icon_dir / f"{slug}.png"
