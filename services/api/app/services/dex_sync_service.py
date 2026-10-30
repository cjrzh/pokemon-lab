"""图鉴同步服务：编排 PokéAPI 拉取、解析、落库。

被两处复用：
  - scripts/sync_pokeapi.py（命令行手动同步）
  - api/v1/admin.py 的 POST /admin/pokemon/sync（后台页面触发）

同步规则：
  - 按 dex_number upsert；`source=manual`（后台手动编辑过）的记录**跳过不覆盖**，
    保护人工修正不被同步冲掉 —— 这是「后端可编辑、同步与编辑共存」的关键边界。
  - 单条解析失败不中断整批：记入 skipped 返回给调用方展示。
  - 每条记录需要 4 个上游请求（pokemon / species / ability ×N / move ×N）：
    特性与招式详情全进程共享缓存（关都 151 只之间大量复用），
    evolution-chain 同链共享（妙蛙家族 3 只只拉 1 次链）。
  - 官方立绘下载到本地 media/artwork，站点离线也能看到图片；下载失败只记 warning，
    不阻塞数据落库（前端会回落到远程地址）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.pokeapi import UpstreamError, fetch_json, parse_payload
from app.core.config import get_settings
from app.domain.pokemon_parser import (
    PokemonParseError,
    attach_ability_details,
    attach_evolution,
    attach_moves,
    collect_move_names,
    evolution_chain_url_from_species,
    extract_all_moves,
    parse_ability_details,
    parse_evolution_chain,
    parse_move_details,
    parse_pokemon,
)
from app.repositories import pokemon_repo
from app.services.ability_service import sync_abilities
from app.services.artwork_service import ensure_artwork
from app.services.flavor_translation_service import apply_flavor_fallback
from app.services.move_service import rebuild_move_index
from app.services.sprite_service import ensure_sprite

logger = logging.getLogger(__name__)

#: 全国图鉴（Gen 1–9）的世代区间：gen → (start, end)。
#: 与 scripts/seed_generations.py 的世代划分一致；同步脚本与文档共用这一份。
NATIONAL_DEX_GENERATIONS: dict[int, tuple[int, int]] = {
    1: (1, 151),
    2: (152, 251),
    3: (252, 386),
    4: (387, 493),
    5: (494, 649),
    6: (650, 721),
    7: (722, 809),
    8: (810, 905),
    9: (906, 1025),
}

#: 全国图鉴总数（默认同步范围）。
NATIONAL_DEX_TOTAL = 1025

#: 默认同步范围：全国图鉴 #1-1025（原 MVP 只覆盖关都 #1-151）。
DEFAULT_SYNC_RANGE = (1, NATIONAL_DEX_TOTAL)


@dataclass
class SyncResult:
    """一次同步的结果汇总。"""

    synced: list[int] = field(default_factory=list)  # 成功落库的 dex_number
    skipped_manual: list[int] = field(default_factory=list)  # 手动编辑过，未覆盖
    skipped_existing: list[int] = field(default_factory=list)  # --resume 跳过的已有记录
    failed: dict[int, str] = field(default_factory=dict)  # 失败的 dex_number → 原因

    def summary(self) -> str:
        skipped = len(self.skipped_manual) + len(self.skipped_existing)
        return (
            f"同步完成：成功 {len(self.synced)}，跳过 {skipped}（含手动记录 "
            f"{len(self.skipped_manual)}），失败 {len(self.failed)}"
        )


async def sync_range(
    session: AsyncSession,
    start: int,
    end: int,
    *,
    force: bool = False,
    skip_existing: bool = False,
    progress: object = None,
) -> SyncResult:
    """同步 [start, end] 闭区间的图鉴编号。

    - `force=True`：手动编辑过的记录也会被覆盖（--force / 管理端明确选择时使用）。
    - `skip_existing=True`：本地已有 `source=pokeapi` 的记录直接跳过（断点续传），
      不发起上游请求 —— 与 manual 跳过语义不同，单独记录在 `skipped_existing`。
    - `progress`：可选回调 `(done, total, dex_number)`，长批次（全国 1025 只）时
      由调用方打进度日志，服务本身不 print。
    """
    result = SyncResult()
    # 同一次同步内共享的缓存：进化链（链内多只共享）、特性详情、招式详情
    chain_cache: dict[str, dict] = {}
    ability_cache: dict[str, dict] = {}
    move_cache: dict[str, dict] = {}
    total = end - start + 1
    done = 0
    for dex_number in range(start, end + 1):
        done += 1
        # 先查本地：手动编辑过的记录不覆盖（除非 force）；
        # `--resume` 时已同步过的 pokeapi 记录也跳过，不浪费上游请求。
        existing = await pokemon_repo.get_by_dex_number(session, dex_number)
        if existing is not None:
            if existing.source == "manual" and not force:
                result.skipped_manual.append(dex_number)
                continue
            if existing.source == "pokeapi" and skip_existing:
                result.skipped_existing.append(dex_number)
                continue

        try:
            record = await _fetch_and_parse_one(
                session, dex_number, chain_cache, ability_cache, move_cache
            )
        except UpstreamError as exc:
            # 上游整体不可用（网络/超时/限流用尽）：继续重试后续编号意义不大，
            # 但单条 404 属确定性失败应跳过 —— UpstreamError.status_code 可区分
            if exc.status_code == 404:
                result.failed[dex_number] = "PokéAPI 无此编号（404）"
                continue
            logger.exception("同步中断：PokéAPI 不可用（dex=%s）", dex_number)
            raise
        except PokemonParseError as exc:
            result.failed[dex_number] = str(exc)
            continue

        if record is None:
            result.failed[dex_number] = "解析失败"
            continue

        # 立绘与小图标落盘：失败不阻塞数据写入
        record = await _attach_artwork(record)
        record = await _attach_sprite(record)
        await pokemon_repo.upsert_pokemon(session, record)
        # 逐条提交：批同步可能持续数分钟，若整批一个事务，SQLite 写锁会一直占着，
        # 前端浏览 / 健康检查都会拿到 "database is locked"。
        await session.commit()
        result.synced.append(dex_number)
        if progress is not None:
            progress(done, total, dex_number)

    # 特性参考表：从同步后的宝可梦记录重新汇总（幂等，人工评级不会被覆盖）
    ability_stats = await sync_abilities(session)
    # 招式学习者索引：展开 moves_json，供招式页反查「谁会这招」
    move_stats = await rebuild_move_index(session)
    logger.info("招式索引：%s 个招式 / %s 个学习者组合", move_stats["moves"], move_stats["pairs"])

    await pokemon_repo.log_admin_op(
        session,
        action="pokemon.sync",
        target=f"dex {start}-{end}" + ("（force）" if force else ""),
        detail=(
            result.summary()
            + f"；特性 {ability_stats['abilities']} 个（S 级 {ability_stats['s_tier']}）"
        ),
    )
    return result


async def _fetch_and_parse_one(
    session: AsyncSession,
    dex_number: int,
    chain_cache: dict[str, dict],
    ability_cache: dict[str, dict],
    move_cache: dict[str, dict],
) -> dict | None:
    """拉取并解析单只宝可梦；进化链 / 特性 / 招式详情均按 URL 或名称共享缓存。"""
    pokemon_payload = _as_dict(
        parse_payload((await fetch_json(session, f"/pokemon/{dex_number}")).payload)
    )
    species_payload = _as_dict(
        parse_payload((await fetch_json(session, f"/pokemon-species/{dex_number}")).payload)
    )

    record = apply_flavor_fallback(parse_pokemon(pokemon_payload, species_payload))

    # ---------- 特性详情（全进程共享，关都 151 只仅约 114 种特性） ----------
    ability_details = await _load_details(
        session,
        record.get("abilities_json", "[]"),
        cache=ability_cache,
        path_template="/ability/{name}",
        parser=parse_ability_details,
    )
    record = attach_ability_details(record, ability_details)

    # ---------- 招式：全部版本组 × 全部学习方式 ----------
    # 只存「版本组 → 学习方式 → 招式名/等级」；招式数值写进共享的 move_ref 表。
    move_groups = extract_all_moves(pokemon_payload)
    if move_groups:
        for name in collect_move_names(move_groups):
            if name not in move_cache:
                move_cache[name] = await _load_one_detail(
                    session, f"/move/{name}", parse_move_details
                )
        await pokemon_repo.upsert_move_refs(
            session, [detail for detail in move_cache.values() if detail]
        )
    record = attach_moves(record, move_groups)

    # ---------- 进化链（同链共享） ----------
    chain_url = evolution_chain_url_from_species(species_payload)
    if chain_url:
        if chain_url not in chain_cache:
            chain_payload = _as_dict(
                parse_payload((await fetch_json(session, _path_from_url(chain_url))).payload)
            )
            chain_cache[chain_url] = parse_evolution_chain(chain_payload, dex_number)
        record = attach_evolution(record, chain_cache[chain_url])

    return record


async def _load_details(
    session: AsyncSession,
    payload: str,
    *,
    cache: dict[str, dict],
    path_template: str,
    parser,
) -> dict[str, dict]:
    """从 JSON 列表文本（如 abilities_json）中取 name 并加载详情。"""
    try:
        items = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return {}
    details: dict[str, dict] = {}
    for item in items:
        name = item.get("name") if isinstance(item, dict) else None
        if not name:
            continue
        if name not in cache:
            cache[name] = await _load_one_detail(session, path_template.format(name=name), parser)
        details[name] = cache[name]
    return details


async def _load_one_detail(session: AsyncSession, path: str, parser) -> dict:
    """拉取并解析单个参考条目；失败时返回空 dict（详情缺失不阻塞主体数据）。"""
    try:
        payload = _as_dict(parse_payload((await fetch_json(session, path)).payload))
        return parser(payload)
    except (UpstreamError, PokemonParseError) as exc:
        # 404 等确定性失败不阻塞主体数据；但接口整体不可用时必须中止，
        # 否则会安静地写进一个「没有特性说明 / 没有招式」的半成品。
        if isinstance(exc, UpstreamError) and exc.status_code != 404:
            raise
        logger.warning("参考数据拉取失败（%s）：%s", path, exc)
        return {}


async def _attach_artwork(record: dict) -> dict:
    """把本地立绘路径写回记录；下载失败保留 None（前端回落远程地址）。"""
    settings = get_settings()
    if not settings.artwork_sync_enabled:
        target = settings.artwork_dir / f"{record['dex_number']}.png"
        relative = f"artwork/{record['dex_number']}.png" if target.exists() else None
        return {**record, "artwork_path": relative}
    return {**record, "artwork_path": await ensure_artwork(record["dex_number"])}


async def _attach_sprite(record: dict) -> dict:
    """把本地小图标路径写回记录；下载失败保留 None（前端回落远程小图）。

    注意：`sprite_url` 列继续保存 official-artwork 代理地址（详情页立绘的兜底），
    小图标的远程地址由 `sprite_service.sprite_url()` 在响应组装时生成，
    避免同一列承载两种尺寸的图片。
    """
    settings = get_settings()
    dex = record["dex_number"]
    if not settings.artwork_sync_enabled:
        target = settings.sprite_dir / f"{dex}.png"
        return {**record, "sprite_path": f"sprites/{dex}.png" if target.exists() else None}
    return {**record, "sprite_path": await ensure_sprite(dex)}


def _path_from_url(url: str) -> str:
    """完整 URL → 相对 base_url 的路径（fetch_json 接收路径），去掉尾斜杠。"""
    marker = "/api/v2/"
    path = url.split(marker, 1)[1] if marker in url else url
    return "/" + path.rstrip("/")


def _as_dict(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise PokemonParseError(f"上游返回非对象：{type(payload).__name__}")
    return payload


async def get_sync_status(
    session: AsyncSession, default_range: tuple[int, int] = DEFAULT_SYNC_RANGE
) -> dict:
    """同步状态总览（供管理页）。"""
    overview = await pokemon_repo.get_sync_overview(session)
    start, end = default_range
    expected = end - start + 1
    return {
        **overview,
        "default_range": {"start": start, "end": end},
        "expected_in_range": expected,
        "coverage": round(overview["total"] / expected, 4) if expected else None,
    }
