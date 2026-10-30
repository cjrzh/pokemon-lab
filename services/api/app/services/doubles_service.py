"""双打对战辅助数据的读取、导入与组装。

数据链路：
  Smogon 统计文本 → scripts/fetch_doubles_stats.py → data/doubles/*.json
  → 本模块（导入 SQLite / 查询 / 组装响应）

设计约定：
  - 页面必须能分辨「有统计数据」与「该格式没有这只宝可梦」；
  - 名称映射失败时不隐藏记录，而是保留显示名、`dex_number=None`；
  - 中文标签来自 `data/doubles/labels.json`（PokéAPI zh-hans），缺失时回落到英文；
  - IV 是**推断值**（Smogon 不统计 IV），响应里带 `inferred: true`，界面必须标注。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import DoubleFormat, DoublePokemonStat, Pokemon
from app.domain.doubles_formats import FORMAT_KEYS
from app.domain.smogon_stats import (
    STAT_KEYS,
    detect_points_kind,
    infer_ivs,
    load_nature_zh,
    showdown_slug,
)
from app.repositories import pokemon_repo
from app.services.sprite_service import sprite_media_url

logger = logging.getLogger(__name__)

LABELS_FILE = Path("doubles") / "labels.json"


class DoublesDataError(RuntimeError):
    """仓库内双打数据文件缺失或损坏。"""


# ---------------------------------------------------------------------------
# 名称映射
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DexNameIndex:
    """Showdown 名称 → 全国图鉴编号的解析器。

    规则（从具体到通用）：
      1. 精确匹配本地 `name_en`（含形态后缀，如 `urshifu-single-strike`）；
      2. 逐级向前缀收窄：`Aegislash` → `aegislash-shield`、
         `Urshifu-Rapid-Strike` → `urshifu-single-strike`、
         `Rotom-Wash` → `rotom`。形态只影响显示名，图鉴编号按物种归属；
         若某个词根同时对应多只宝可梦（如 `nidoran`），不猜，交给别名表；
      3. 少量 Showdown 专用写法（`NidoranM` / `NidoranF`）。
    """

    exact: dict[str, int]
    roots: dict[str, int]
    aliases: dict[str, str]

    def resolve(self, showdown_name: str) -> int | None:
        slug = showdown_slug(showdown_name)
        slug = self.aliases.get(slug, slug)
        if slug in self.exact:
            return self.exact[slug]
        # `Aegislash` / `Darmanitan` / `Giratina` 这类单段名，本地库只有带形态后缀的
        # 默认形态（`aegislash-shield` 等）：词根唯一时取它。
        parts = slug.split("-")
        for length in range(len(parts), 0, -1):
            root = "-".join(parts[:length])
            if root in self.roots:
                return self.roots[root]
            if root in self.exact:
                return self.exact[root]
        return None


def build_name_index(pokemon_rows: list[tuple[str, int]]) -> DexNameIndex:
    """从 (name_en, dex_number) 列表建立索引。"""
    exact: dict[str, int] = {}
    candidates: dict[str, set[int]] = {}
    for name, dex in pokemon_rows:
        slug = showdown_slug(name)
        exact[slug] = dex
        candidates.setdefault(slug.split("-")[0], set()).add(dex)
    roots = {root: next(iter(dexes)) for root, dexes in candidates.items() if len(dexes) == 1}
    return DexNameIndex(
        exact=exact,
        roots=roots,
        aliases={"nidoranm": "nidoran-m", "nidoranf": "nidoran-f"},
    )


# ---------------------------------------------------------------------------
# 导入（data/doubles/*.json → SQLite）
# ---------------------------------------------------------------------------

DATA_SUBDIR = Path("doubles")


class DoublesImportResult(dict):
    """导入统计：格式数、记录数、无法映射的宝可梦名称。"""


def resolve_name_index(pokemon_rows: list[tuple[str, int]]) -> DexNameIndex:
    """建立名称索引的公开入口（导入服务与测试共用）。"""
    return build_name_index(pokemon_rows)


async def import_datasets(session: AsyncSession, keys: list[str] | None = None) -> dict:
    """把仓库内 `data/doubles/*.json` 导入数据库。

    幂等：按 (format_key, showdown_name) upsert，不删除已有格式的数据；
    重新抓取后再次导入即可整体刷新。

    Args:
        session: 数据库会话。
        keys: 只导入指定格式；None 表示目录下全部文件。
    """
    data_dir = get_settings().data_dir / DATA_SUBDIR
    if not data_dir.is_dir():
        raise DoublesDataError(
            f"双打数据目录不存在：{data_dir}。请先运行 scripts/fetch_doubles_stats.py"
        )

    paths = sorted(data_dir.glob("*.json"))
    paths = [path for path in paths if path.name != "labels.json"]
    if keys:
        wanted = set(keys)
        paths = [path for path in paths if path.stem in wanted]
    if not paths:
        raise DoublesDataError("没有可导入的双打数据文件（data/doubles/*.json）")

    pokemon_rows = [
        (name, dex)
        for name, dex in (await session.execute(select(Pokemon.name_en, Pokemon.dex_number))).all()
    ]
    if not pokemon_rows:
        raise DoublesDataError("本地图鉴为空，无法把双打统计映射到图鉴编号")

    index = build_name_index(pokemon_rows)
    reset_labels_cache()

    imported_formats = 0
    imported_stats = 0
    unresolved: set[str] = set()
    per_format: dict[str, int] = {}

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            meta = payload["format"]
            entries = payload["entries"]
        except (json.JSONDecodeError, KeyError, OSError, TypeError) as exc:
            raise DoublesDataError(f"双打数据文件损坏（{path}）：{exc}") from exc

        key = meta["key"]
        fmt = await session.get(DoubleFormat, key)
        if fmt is None:
            fmt = DoubleFormat(key=key)
            session.add(fmt)
        fmt.label = meta["label"]
        fmt.short_label = meta["short_label"]
        fmt.game = meta["game"]
        fmt.ruleset = meta["ruleset"]
        fmt.smogon_format = meta["smogon_format"]
        fmt.month = meta["month"]
        fmt.cutoff = int(meta["cutoff"])
        fmt.points_kind = meta.get("points_kind", "ev")
        fmt.battles = int(payload.get("battles") or 0)
        fmt.trade_prefix = meta.get("trade_prefix")
        fmt.default_level = int(meta.get("default_level") or 50)
        fmt.note = meta.get("note")
        fmt.source_url = meta.get("usage_url")
        imported_formats += 1

        existing = {
            row.showdown_name: row
            for row in (
                await session.execute(
                    select(DoublePokemonStat).where(DoublePokemonStat.format_key == key)
                )
            )
            .scalars()
            .all()
        }

        for entry in entries:
            name = entry["name"]
            dex = index.resolve(name)
            if dex is None:
                unresolved.add(name)
            row = existing.get(name)
            if row is None:
                row = DoublePokemonStat(format_key=key, showdown_name=name)
                session.add(row)
            row.dex_number = dex
            row.rank = entry.get("rank")
            row.usage = entry.get("usage")
            row.raw_count = int(entry.get("raw_count") or 0)
            row.abilities_json = json.dumps(entry.get("abilities", []), ensure_ascii=False)
            row.items_json = json.dumps(entry.get("items", []), ensure_ascii=False)
            row.moves_json = json.dumps(entry.get("moves", []), ensure_ascii=False)
            row.spreads_json = json.dumps(entry.get("spreads", []), ensure_ascii=False)
            row.teammates_json = json.dumps(entry.get("teammates", []), ensure_ascii=False)
            row.tera_types_json = json.dumps(entry.get("tera_types", []), ensure_ascii=False)
            imported_stats += 1

        per_format[key] = len(entries)

    await session.flush()
    return {
        "formats": imported_formats,
        "entries": imported_stats,
        "per_format": per_format,
        "unresolved": sorted(unresolved),
    }


# ---------------------------------------------------------------------------
# 标签
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_labels() -> dict:
    """读取 data/doubles/labels.json（进程内缓存）。"""
    path = get_settings().data_dir / LABELS_FILE
    if not path.exists():
        logger.warning("双打标签文件不存在：%s", path)
        return {"items": {}, "moves": {}, "abilities": {}, "natures": load_nature_zh()}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DoublesDataError(f"双打标签文件损坏（{path}）：{exc}") from exc
    for key in ("items", "moves", "abilities"):
        payload.setdefault(key, {})
    payload.setdefault("natures", load_nature_zh())
    return payload


def reset_labels_cache() -> None:
    """清空标签缓存。导入新数据后必须调用，否则界面上仍是旧标签。"""
    load_labels.cache_clear()


def _label(group: str, slug: str) -> str | None:
    value = load_labels().get(group, {}).get(slug)
    return value or None


def _label_en(group: str, slug: str) -> str | None:
    """Showdown 英文名；缺失时返回 None（由调用方回落到显示名）。"""
    labels = load_labels()
    value = labels.get(f"{group}_en", {}).get(slug)
    return value or None


def _usage(
    group: str,
    pairs,
    types: dict[str, str] | None = None,
    icons: dict[str, str | None] | None = None,
) -> list[dict]:
    """把 [slug, pct] 列表转成带中英文名的条目。

    `types` 只对招式生效（属性徽章用），由调用方从 move_ref 批量查好后传入；
    `icons` 只对道具生效（道具图标），来自 item_ref 的本地缓存路径。
    """
    icons = icons if icons is not None else {}
    items = []
    for slug, pct in pairs:
        zh = _label(group, slug)
        en = _label_en(group, slug)
        items.append(
            {
                "slug": slug,
                "name": zh or en or pretty_name(slug),
                "name_en": en,
                "type": (types or {}).get(slug),
                "icon_url": icons.get(slug) if group == "items" else None,
                "pct": pct,
            }
        )
    return items


def item_icon_lookup(icon_rows: dict[str, object]) -> dict[str, str | None]:
    """item_ref 记录 → slug 到「本地优先的图标地址」的映射。

    道具不在 item_ref 里（尚未同步）时返回 None，由前端显示占位，
    而不是拼一个可能 404 的远程地址。
    """
    from app.services.item_service import icon_media_url

    return {
        slug: icon_media_url(slug, getattr(row, "icon_path", None))
        for slug, row in icon_rows.items()
    }


def pretty_name(slug: str) -> str:
    """slug → 可读英文名（中文标签缺失时的兜底，不做猜译）。"""
    return " ".join(part.capitalize() for part in slug.replace("-", " ").split())


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------


async def list_formats(session: AsyncSession) -> list[DoubleFormat]:
    """已导入的格式（按仓库定义的展示顺序）。"""
    rows = list((await session.execute(select(DoubleFormat))).scalars().all())
    order = {key: index for index, key in enumerate(FORMAT_KEYS)}
    return sorted(rows, key=lambda row: order.get(row.key, len(order)))


async def get_format(session: AsyncSession, key: str) -> DoubleFormat | None:
    return (
        await session.execute(select(DoubleFormat).where(DoubleFormat.key == key))
    ).scalar_one_or_none()


async def get_stat(
    session: AsyncSession, dex_number: int, format_key: str
) -> DoublePokemonStat | None:
    return (
        await session.execute(
            select(DoublePokemonStat).where(
                DoublePokemonStat.dex_number == dex_number,
                DoublePokemonStat.format_key == format_key,
            )
        )
    ).scalar_one_or_none()


async def get_all_stats_for_dex(session: AsyncSession, dex_number: int) -> list[DoublePokemonStat]:
    stmt = (
        select(DoublePokemonStat)
        .where(DoublePokemonStat.dex_number == dex_number)
        .order_by(DoublePokemonStat.format_key)
    )
    return list((await session.execute(stmt)).scalars().all())


async def format_entry_counts(session: AsyncSession) -> dict[str, int]:
    """每个格式的统计条目数（排行榜标签上的数字）。"""
    rows = (
        await session.execute(
            select(DoublePokemonStat.format_key, func.count())
            .group_by(DoublePokemonStat.format_key)
        )
    ).all()
    return {key: count for key, count in rows}


async def list_ranking(
    session: AsyncSession,
    fmt: DoubleFormat,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """某一格式的使用率排行榜（按 Rank 升序，缺失名次时按使用率降序）。

    返回已经组装好的条目（中文名 / 属性 / 立绘 / 常用配装），调用方只负责
    加上格式元数据。搜索支持图鉴编号、中文名、英文名与 Showdown 显示名 ——
    形态名（`Urshifu-Rapid-Strike`）与原种名（`urshifu-single-strike`）都能命中。
    """
    table = DoublePokemonStat
    stmt = select(table, Pokemon).outerjoin(Pokemon, Pokemon.dex_number == table.dex_number)
    stmt = stmt.where(table.format_key == fmt.key)

    keyword = (search or "").strip()
    if keyword:
        lowered = f"%{keyword.lower()}%"
        conditions = [
            func.lower(table.showdown_name).like(lowered),
            func.ifnull(func.lower(Pokemon.name_en), "").like(lowered),
            func.ifnull(Pokemon.name_zh, "").like(f"%{keyword}%"),
        ]
        if keyword.isdigit():
            conditions.append(table.dex_number == int(keyword))
        stmt = stmt.where(or_(*conditions))

    return await _ranking_page(session, stmt, page, page_size)


async def _ranking_page(
    session: AsyncSession, stmt, page: int, page_size: int
) -> tuple[list[dict], int]:
    """执行排行榜查询并组装条目（内部函数，供 list_ranking 使用）。"""
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    page = max(1, page)
    page_size = max(1, min(200, page_size))
    order = (
        case((DoublePokemonStat.rank.is_(None), 1), else_=0),
        DoublePokemonStat.rank.asc(),
        case((DoublePokemonStat.usage.is_(None), 1), else_=0),
        DoublePokemonStat.usage.desc(),
        DoublePokemonStat.showdown_name.asc(),
    )
    rows = (
        await session.execute(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size))
    ).all()

    move_slugs: set[str] = set()
    item_slugs: set[str] = set()
    for stat, _ in rows:
        move_slugs.update(slug for slug, _ in parse_json(stat.moves_json))
        item_slugs.update(slug for slug, _ in parse_json(stat.items_json))
    move_refs = await pokemon_repo.get_move_refs(session, sorted(move_slugs))
    move_types = {slug: ref["type"] for slug, ref in move_refs.items() if ref.get("type")}
    item_icons = item_icon_lookup(await _load_item_rows(session, item_slugs))

    natures = load_labels().get("natures", {})
    items: list[dict] = []
    for stat, pokemon in rows:
        spreads = parse_json(stat.spreads_json)
        top_spread = spreads[0] if spreads else None
        items.append(
            {
                "showdown_name": stat.showdown_name,
                "dex_number": stat.dex_number,
                "name_zh": pokemon.name_zh if pokemon else None,
                "name_en": pokemon.name_en if pokemon else None,
                "types": _safe_types(pokemon.types_json) if pokemon else [],
                "artwork_url": _artwork_url(pokemon) if pokemon else None,
                "artwork_fallback_url": pokemon.sprite_url if pokemon else None,
                "sprite_url": (
                    sprite_media_url(pokemon.dex_number, pokemon.sprite_path) if pokemon else None
                ),
                "is_legendary": bool(pokemon.is_legendary) if pokemon else False,
                "is_mythical": bool(pokemon.is_mythical) if pokemon else False,
                "rank": stat.rank,
                "usage": stat.usage,
                "raw_count": stat.raw_count,
                "abilities": _usage("abilities", parse_json(stat.abilities_json))[:3],
                "items": _usage(
                    "items", parse_json(stat.items_json), icons=item_icons
                )[:3],
                "moves": _usage("moves", parse_json(stat.moves_json), move_types)[:4],
                "spread": (
                    {
                        "nature": top_spread["nature"],
                        "nature_label": natures.get(
                            top_spread["nature"], pretty_name(top_spread["nature"])
                        ),
                        "points": top_spread["points"],
                        "pct": top_spread["pct"],
                    }
                    if top_spread
                    else None
                ),
            }
        )
    return items, total


def _safe_types(text: str | None) -> list[str]:
    try:
        value = json.loads(text or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _artwork_url(pokemon: Pokemon) -> str | None:
    """立绘地址：本地缓存优先，失败时前端回落到 `sprite_url`。"""
    if pokemon.artwork_path:
        return f"/media/{pokemon.artwork_path}"
    return pokemon.artwork_url


async def get_status(session: AsyncSession) -> dict:
    """后台看板：已导入格式、记录数、每格式覆盖的图鉴数量。"""
    formats = await list_formats(session)
    total = (
        await session.execute(select(func.count()).select_from(DoublePokemonStat))
    ).scalar_one()

    per_format: dict[str, dict] = {}
    for fmt in formats:
        entries = (
            await session.execute(
                select(func.count()).where(DoublePokemonStat.format_key == fmt.key)
            )
        ).scalar_one()
        dex_covered = (
            await session.execute(
                select(func.count(func.distinct(DoublePokemonStat.dex_number))).where(
                    DoublePokemonStat.format_key == fmt.key,
                    DoublePokemonStat.dex_number.is_not(None),
                )
            )
        ).scalar_one()
        per_format[fmt.key] = {
            "key": fmt.key,
            "label": fmt.label,
            "month": fmt.month,
            "cutoff": fmt.cutoff,
            "points_kind": fmt.points_kind,
            "battles": fmt.battles,
            "trade_prefix": fmt.trade_prefix,
            "default_level": fmt.default_level,
            "entries": entries,
            "dex_covered": dex_covered,
            "imported_at": fmt.imported_at.isoformat() if fmt.imported_at else None,
        }

    return {"format_count": len(formats), "entries": total, "formats": list(per_format.values())}


def parse_json(text: str) -> list:
    try:
        value = json.loads(text or "[]")
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def load_item_rows(session: AsyncSession, slugs: set[str]) -> dict:
    """批量读取道具参考记录（slug → ItemReference），避免逐个查询。"""
    from app.db.models import ItemReference

    if not slugs:
        return {}
    rows = (
        (await session.execute(select(ItemReference).where(ItemReference.name.in_(slugs))))
        .scalars()
        .all()
    )
    return {row.name: row for row in rows}


# 兼容内部旧命名
_load_item_rows = load_item_rows


async def profile_payload(
    session: AsyncSession,
    stat: DoublePokemonStat,
    fmt: DoubleFormat,
    index: DexNameIndex,
    dex_names: dict[int, str] | None = None,
    move_types: dict[str, str] | None = None,
    item_icons: dict[str, str | None] | None = None,
) -> dict:
    """把一条统计整理成前端直接可渲染的结构。

    所有百分比原样返回（0–100），由前端决定保留几位小数。
    `dex_names` 提供「图鉴编号 → 中文名」，用于队友链接的可读名称。
    `item_icons` 是道具图标地址；调用方不传时按本条统计里的道具 slug 现查。
    """
    dex_names = dex_names or {}
    spreads = parse_json(stat.spreads_json)
    points_kind = detect_points_kind(spreads) if spreads else fmt.points_kind

    abilities = _usage("abilities", parse_json(stat.abilities_json))
    if item_icons is None:
        item_slugs = {slug for slug, _ in parse_json(stat.items_json)}
        item_icons = item_icon_lookup(await _load_item_rows(session, item_slugs))
    items = _usage("items", parse_json(stat.items_json), icons=item_icons)
    moves = _usage("moves", parse_json(stat.moves_json), move_types)
    teammates = []
    for name, pct in parse_json(stat.teammates_json):
        teammate_dex = index.resolve(name)
        teammates.append(
            {
                "showdown_name": name,
                "dex_number": teammate_dex,
                "name_zh": dex_names.get(teammate_dex) if teammate_dex else None,
                "pct": pct,
            }
        )
    tera_types = [{"type": slug, "pct": pct} for slug, pct in parse_json(stat.tera_types_json)]

    natures = load_labels().get("natures", {})
    top_spread = spreads[0] if spreads else None
    iv_info = None
    if top_spread:
        iv_info = infer_ivs(
            top_spread["nature"],
            top_spread["points"],
            [move["slug"] for move in moves],
            points_kind=points_kind,
        )

    return {
        "format_key": fmt.key,
        "format_label": fmt.label,
        "short_label": fmt.short_label,
        "game": fmt.game,
        "ruleset": fmt.ruleset,
        "month": fmt.month,
        "cutoff": fmt.cutoff,
        "points_kind": points_kind,
        "battles": fmt.battles,
        "note": fmt.note,
        "source_url": fmt.source_url,
        "imported_at": fmt.imported_at.isoformat() if fmt.imported_at else None,
        "showdown_name": stat.showdown_name,
        "rank": stat.rank,
        "usage": stat.usage,
        "raw_count": stat.raw_count,
        "abilities": abilities,
        "items": items,
        "moves": moves,
        "teammates": teammates,
        "tera_types": tera_types,
        "spreads": [
            {
                "nature": spread["nature"],
                "nature_label": natures.get(spread["nature"], pretty_name(spread["nature"])),
                "points": spread["points"],
                "pct": spread["pct"],
            }
            for spread in spreads
        ],
        "ivs": iv_info,
        "stat_keys": list(STAT_KEYS),
    }
