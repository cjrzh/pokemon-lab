"""图鉴同步服务：编排 PokéAPI 拉取、解析、落库。

被两处复用：
  - scripts/sync_pokeapi.py（命令行手动同步）
  - api/v1/admin.py 的 POST /admin/pokemon/sync（后台页面触发）

同步规则：
  - 按 dex_number upsert；`source=manual`（后台手动编辑过）的记录**跳过不覆盖**，
    保护人工修正不被同步冲掉 —— 这是「后端可编辑、同步与编辑共存」的关键边界。
  - 单条解析失败不中断整批：记入 skipped 返回给调用方展示。
  - 每条记录需要 3 个上游请求（pokemon / species / evolution-chain），其中
    evolution-chain 同链共享（妙蛙家族 3 只只拉 1 次链）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.pokeapi import UpstreamError, fetch_json, parse_payload
from app.domain.pokemon_parser import (
    PokemonParseError,
    attach_evolution,
    evolution_chain_url_from_species,
    parse_evolution_chain,
    parse_pokemon,
)
from app.repositories import pokemon_repo

logger = logging.getLogger(__name__)

#: MVP 默认同步范围：关都图鉴 #1-151。
DEFAULT_SYNC_RANGE = (1, 151)


@dataclass
class SyncResult:
    """一次同步的结果汇总。"""

    synced: list[int] = field(default_factory=list)  # 成功落库的 dex_number
    skipped_manual: list[int] = field(default_factory=list)  # 手动编辑过，未覆盖
    failed: dict[int, str] = field(default_factory=dict)  # 失败的 dex_number → 原因

    def summary(self) -> str:
        return (
            f"同步完成：成功 {len(self.synced)}，"
            f"手动记录跳过 {len(self.skipped_manual)}，失败 {len(self.failed)}"
        )


async def sync_range(
    session: AsyncSession, start: int, end: int, *, force: bool = False
) -> SyncResult:
    """同步 [start, end] 闭区间的图鉴编号。

    `force=True` 时手动编辑过的记录也会被覆盖（--force / 管理端明确选择时使用）。
    """
    result = SyncResult()
    # 进化链缓存：同一条链只拉一次（链内多只共享）
    chain_cache: dict[str, dict] = {}

    for dex_number in range(start, end + 1):
        # 先查本地：手动编辑过的记录不覆盖（除非 force），也不浪费上游请求
        existing = await pokemon_repo.get_by_dex_number(session, dex_number)
        if existing is not None and existing.source == "manual" and not force:
            result.skipped_manual.append(dex_number)
            continue

        try:
            record = await _fetch_and_parse_one(session, dex_number, chain_cache)
        except UpstreamError as exc:
            # 上游整体不可用（网络/超时/限流用尽）：继续重试后续编号意义不大，
            # 但单条 404 属确定性失败应跳过 —— UpstreamError.status_code 可区分
            if exc.status_code == 404:
                result.failed[dex_number] = "PokéAPI 无此编号（404）"
                continue
            logger.exception("同步中断：PokéAPI 不可用（dex=%s）", dex_number)
            raise

        if record is None:
            result.failed[dex_number] = "解析失败"
            continue

        await pokemon_repo.upsert_pokemon(session, record)
        result.synced.append(dex_number)

    await pokemon_repo.log_admin_op(
        session,
        action="pokemon.sync",
        target=f"dex {start}-{end}" + ("（force）" if force else ""),
        detail=result.summary(),
    )
    return result


async def _fetch_and_parse_one(
    session: AsyncSession, dex_number: int, chain_cache: dict[str, dict]
) -> dict | None:
    """拉取并解析单只宝可梦；进化链按 URL 缓存共享（同链只拉一次）。"""
    pokemon_payload = _as_dict(
        parse_payload((await fetch_json(session, f"/pokemon/{dex_number}")).payload)
    )
    species_payload = _as_dict(
        parse_payload((await fetch_json(session, f"/pokemon-species/{dex_number}")).payload)
    )

    record = parse_pokemon(pokemon_payload, species_payload)

    chain_url = evolution_chain_url_from_species(species_payload)
    if chain_url:
        if chain_url not in chain_cache:
            chain_payload = _as_dict(
                parse_payload((await fetch_json(session, _path_from_url(chain_url))).payload)
            )
            chain_cache[chain_url] = parse_evolution_chain(chain_payload, dex_number)
        record = attach_evolution(record, chain_cache[chain_url])

    return record


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
