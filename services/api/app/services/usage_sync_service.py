"""Smogon 历史使用率的同步编排。

流程：
  1. 发现 Smogon 上的全部月份；
  2. 对「目录里的每个双打/VGC 格式 × 月份 × 三个等级线」枚举候选；
  3. **增量**：库里已有 (format_id, month, cutoff) 的直接跳过，不重复下载；
  4. 下载 → 解析 usage 表 → 落库（快照 + 条目）；
  5. 全程写 `UsageSyncRun` 进度，前端同步按钮据此展示。

并发与礼貌：Smogon 是社区公益站点，这里用**受限并发**（默认 4）并复用连接池，
不做无节制抓取；单次同步按用户选择的范围执行，默认只同步最近几个月。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import session_scope
from app.db.models import UsageSnapshot, UsageSnapshotEntry, UsageSyncRun
from app.domain import smogon_catalog
from app.domain.smogon_catalog import CUTOFFS, FORMAT_BY_ID, SmogonFetchError
from app.domain.smogon_stats import SmogonParseError, parse_usage_table
from app.repositories import pokemon_repo
from app.services.doubles_service import build_name_index

logger = logging.getLogger(__name__)

#: 并发下载数（对 Smogon 保持克制）。
MAX_CONCURRENCY = 4

#: 「检查是否已有任务在跑 + 创建任务」的进程内互斥。
#: 两个请求（双击按钮 / 两个标签页）同时到达时，单靠先查后插会竞态，
#: 结果两个后台任务并发跑同一批快照，后写的撞 `usage_snapshot` 唯一约束。
_START_LOCK = asyncio.Lock()


class SyncBusyError(RuntimeError):
    """已有同步任务在运行。"""

    def __init__(self, run_id: int) -> None:
        super().__init__(f"已有同步任务在运行（#{run_id}）")
        self.run_id = run_id


@dataclass(frozen=True)
class SyncScope:
    """一次同步的范围。`None` 表示「全部」。"""

    months: list[str] | None = None
    format_ids: list[str] | None = None
    cutoffs: tuple[int, ...] = CUTOFFS
    #: 最近 N 个月（与 months 二选一；用于按钮的默认行为）
    recent_months: int | None = None

    def to_json(self) -> dict:
        return {
            "months": self.months,
            "format_ids": self.format_ids,
            "cutoffs": list(self.cutoffs),
            "recent_months": self.recent_months,
        }


async def existing_snapshot_keys(session: AsyncSession) -> set[tuple[str, str, int]]:
    rows = (
        await session.execute(
            select(UsageSnapshot.format_id, UsageSnapshot.month, UsageSnapshot.cutoff)
        )
    ).all()
    return {(format_id, month, cutoff) for format_id, month, cutoff in rows}


async def available_months(session: AsyncSession) -> list[str]:
    """库里已有数据的月份（升序）。"""
    rows = (await session.execute(select(UsageSnapshot.month).distinct())).all()
    return sorted({month for (month,) in rows})


async def plan_targets(
    session: AsyncSession,
    scope: SyncScope,
    all_months: list[str],
) -> tuple[list[tuple[str, str, int]], list[str]]:
    """算出待同步的 (format_id, month, cutoff) 列表与警告。

    增量逻辑：已存在的三元组直接排除；改变范围（例如以后补 0 档）时，
    只补缺的那些，不重下已有数据。
    """
    warnings: list[str] = []

    months = scope.months
    if months is None and scope.recent_months is not None:
        months = all_months[-scope.recent_months :]
    months = [month for month in (months or all_months) if month in set(all_months)]
    if not months:
        warnings.append("所选月份在 Smogon 上没有统计数据")

    format_ids = scope.format_ids or [fmt.format_id for fmt in smogon_catalog.FORMAT_CATALOG]
    unknown = [fid for fid in format_ids if fid not in FORMAT_BY_ID]
    if unknown:
        warnings.append(f"目录里没有这些格式，已跳过：{', '.join(unknown)}")
    format_ids = [fid for fid in format_ids if fid in FORMAT_BY_ID]

    existing = await existing_snapshot_keys(session)
    targets = [
        (fid, month, cutoff)
        for month in months
        for fid in format_ids
        for cutoff in scope.cutoffs
        if (fid, month, cutoff) not in existing
    ]
    return targets, warnings


async def _download(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    format_id: str,
    month: str,
    cutoff: int,
) -> tuple[str, str, int, str | None]:
    async with semaphore:
        text = await smogon_catalog.fetch_usage_text_async(
            format_id, month, cutoff, client
        )
    return format_id, month, cutoff, text


async def run_sync(scope: SyncScope, run_id: int) -> None:
    """执行同步（后台任务）。全程自行管理会话，异常只记入 run 而不抛出。"""
    try:
        await _run_sync_inner(scope, run_id)
    except Exception as exc:  # noqa: BLE001 - 后台任务要把失败写进记录
        logger.exception("Smogon 同步失败")
        async with session_scope() as session:
            run = await session.get(UsageSyncRun, run_id)
            if run is not None:
                run.status = "error"
                run.message = f"{type(exc).__name__}: {exc}"
                run.finished_at = datetime.now(UTC)


async def _run_sync_inner(scope: SyncScope, run_id: int) -> None:
    async with session_scope() as session:
        run = await session.get(UsageSyncRun, run_id)
        if run is None:
            return
        run.status = "running"

    async with smogon_catalog.make_async_client() as client:
        try:
            all_months = await asyncio.wait_for(
                smogon_catalog.discover_months_async(client), timeout=60
            )
        except SmogonFetchError as exc:
            async with session_scope() as session:
                run = await session.get(UsageSyncRun, run_id)
                if run is not None:
                    run.status = "error"
                    run.message = str(exc)
                    run.finished_at = datetime.now(UTC)
            return

        async with session_scope() as session:
            targets, warnings = await plan_targets(session, scope, all_months)
            run = await session.get(UsageSyncRun, run_id)
            if run is not None:
                run.total = len(targets)
                run.message = "；".join(warnings) if warnings else None
                run.scope_json = json.dumps(
                    {**scope.to_json(), "resolved_months": len(all_months)}, ensure_ascii=False
                )

            # 名称索引一次取好（同步期间图鉴不会变）
            pokemon_rows = [
                (name, dex)
                for name, dex in (
                    await session.execute(
                        select(pokemon_repo.Pokemon.name_en, pokemon_repo.Pokemon.dex_number)
                    )
                ).all()
            ]
            index = build_name_index(pokemon_rows)

        if not targets:
            async with session_scope() as session:
                run = await session.get(UsageSyncRun, run_id)
                if run is not None:
                    run.status = "done"
                    run.message = (run.message or "") + "；已是最新，无需同步"
                    run.finished_at = datetime.now(UTC)
            return

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [
            _download(client, semaphore, format_id, month, cutoff)
            for format_id, month, cutoff in targets
        ]

        for coro in asyncio.as_completed(tasks):
            try:
                format_id, month, cutoff, text = await coro
            except Exception as exc:  # noqa: BLE001 - 单个条目失败不中断整批
                logger.warning("下载失败 %s：%s", exc, exc)
                await _record_failure(run_id, f"下载失败：{exc}")
                continue
            await _persist_one(run_id, format_id, month, cutoff, text, index)

        # 兜底：所有条目处理完后必须收尾。以前只在「成功写入快照」的分支里
        # 判断 done >= total —— 最后一个条目若是 404（skipped）或解析失败，
        # 状态会永远停在 running，前端就一直转圈。
        await _finalize_run(run_id)


async def _record_failure(run_id: int, message: str) -> None:
    """记录一个失败条目并推进进度。"""
    async with session_scope() as session:
        run = await session.get(UsageSyncRun, run_id)
        if run is None:
            return
        run.failed += 1
        run.done += 1
        run.message = message
        _maybe_finish(run)


async def _finalize_run(run_id: int) -> None:
    """把仍在 running 的任务收尾（重复调用安全）。"""
    async with session_scope() as session:
        run = await session.get(UsageSyncRun, run_id)
        if run is None or run.status != "running":
            return
        run.status = "done"
        run.current = None
        run.finished_at = datetime.now(UTC)


def _maybe_finish(run: UsageSyncRun) -> None:
    """进度走完时把任务标为 done（在持有会话的事务内调用）。"""
    if run.done >= run.total:
        run.status = "done"
        run.current = None
        run.finished_at = datetime.now(UTC)


async def mark_interrupted_runs(session: AsyncSession) -> int:
    """服务启动时清理残留的 running 任务。返回处理的条数。

    后台任务随进程消失：进程重启 / 崩溃后，库里那条 `running` 记录不会再有人
    更新。不清理的话，前端会一直转圈，而且「同一时间只允许一个任务」的 409
    检查会让之后的同步永远被挡住。

    - 进度已经走完（done >= total）的，直接标为 done（数据都已落库）；
    - 其余标为 error 并写明中断位置。
    """
    rows = list(
        (
            await session.execute(
                select(UsageSyncRun).where(UsageSyncRun.status == "running")
            )
        )
        .scalars()
        .all()
    )
    for run in rows:
        run.current = None
        run.finished_at = datetime.now(UTC)
        if run.total > 0 and run.done >= run.total:
            run.status = "done"
            continue
        run.status = "error"
        prefix = f"{run.message}；" if run.message else ""
        run.message = f"{prefix}服务重启，同步任务被中断（已完成 {run.done}/{run.total}）"
    return len(rows)


async def _persist_one(
    run_id: int,
    format_id: str,
    month: str,
    cutoff: int,
    text: str | None,
    index,
) -> None:
    """落库一个快照，并更新 run 进度。"""
    async with session_scope() as session:
        run = await session.get(UsageSyncRun, run_id)
        if run is not None:
            run.current = f"{format_id} {month} {cutoff}"

        if text is None:
            # 该月/该格式/该档不存在（404）—— 跳过而不是失败
            if run is not None:
                run.skipped += 1
                run.done += 1
                _maybe_finish(run)
            return

        try:
            usage = parse_usage_table(text)
        except SmogonParseError as exc:
            logger.warning("解析失败 %s %s %s：%s", format_id, month, cutoff, exc)
            if run is not None:
                run.failed += 1
                run.done += 1
                run.message = f"解析失败：{format_id} {month} {cutoff}"
                _maybe_finish(run)
            return

        snapshot = UsageSnapshot(
            format_id=format_id,
            month=month,
            cutoff=cutoff,
            battles=usage.battles,
            source_url=smogon_catalog.usage_url(format_id, month, cutoff),
        )
        session.add(snapshot)
        try:
            await session.flush()
        except IntegrityError:
            # 理论上增量计划已排除已有快照；并发任务 / 上一次中断留下的残留
            # 仍可能撞唯一约束。按「已存在」跳过，而不是让整批任务报错。
            await session.rollback()
            logger.warning("快照已存在，跳过 %s %s %s", format_id, month, cutoff)
            run = await session.get(UsageSyncRun, run_id)
            if run is not None:
                run.skipped += 1
                run.done += 1
                _maybe_finish(run)
            return

        entries = []
        for row in usage.rows:
            dex = index.resolve(row.name)
            entries.append(
                UsageSnapshotEntry(
                    snapshot_id=snapshot.id,
                    showdown_name=row.name,
                    dex_number=dex,
                    rank=row.rank,
                    usage=row.usage,
                    raw_count=row.raw_count,
                )
            )
        session.add_all(entries)

        if run is not None:
            run.created += 1
            run.done += 1
            _maybe_finish(run)


async def start_sync(session: AsyncSession, scope: SyncScope) -> UsageSyncRun:
    """创建同步记录并**立即提交**（供后台任务在另一个会话里读取）。

    关键点：
      - 后台任务用自建会话，若这里只 flush 不 commit，后台任务读不到
        这一行（`session.get` 返回 None），整个同步会静默不执行；
      - 「查是否已有任务 + 插入新任务」放在进程内互斥里，避免双击按钮 /
        两个标签页同时请求时各起一个后台任务，并发写同一批快照。
    """
    async with _START_LOCK:
        running = await latest_run(session)
        if running is not None and running.status == "running":
            raise SyncBusyError(running.id)

        run = UsageSyncRun(
            status="running", scope_json=json.dumps(scope.to_json(), ensure_ascii=False)
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        await session.commit()
        return run


async def purge_range(session: AsyncSession, *, before: str | None = None) -> int:
    """删除某个月之前的快照（测试与数据修正用）。"""
    stmt = select(UsageSnapshot.id)
    if before:
        stmt = stmt.where(UsageSnapshot.month < before)
    ids = [row for (row,) in (await session.execute(stmt)).all()]
    if not ids:
        return 0
    await session.execute(delete(UsageSnapshotEntry).where(UsageSnapshotEntry.snapshot_id.in_(ids)))
    await session.execute(delete(UsageSnapshot).where(UsageSnapshot.id.in_(ids)))
    return len(ids)


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------


async def format_options(session: AsyncSession) -> list[dict]:
    """目录里的全部格式 + 各自在库里的月份数。"""
    rows = (
        await session.execute(
            select(UsageSnapshot.format_id, func.count(func.distinct(UsageSnapshot.month)))
            .group_by(UsageSnapshot.format_id)
        )
    ).all()
    counts = dict(rows)
    return [
        {
            "format_id": fmt.format_id,
            "label": fmt.label,
            "game": fmt.game,
            "ruleset": fmt.ruleset,
            "kind": fmt.kind,
            "months": counts.get(fmt.format_id, 0),
        }
        for fmt in smogon_catalog.FORMAT_CATALOG
    ]


async def query_usage(
    session: AsyncSession,
    *,
    format_id: str | None,
    month: str | None,
    cutoff: int | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    """查询某个快照的使用率排行。

    未指定时取「目录里第一个有数据的格式」与「该格式最新月份」，保证打开页面
    就有内容，而不是空白。
    """
    formats = await format_options(session)
    available = [item for item in formats if item["months"] > 0]

    chosen_format = format_id
    if chosen_format is None:
        chosen_format = available[0]["format_id"] if available else (
            smogon_catalog.FORMAT_CATALOG[0].format_id
        )

    months = await usage_months(session, chosen_format)
    chosen_month = month if month in months else (months[-1] if months else (month or ""))

    # 未指定等级线时优先选「该月确实有数据」的那一档，避免默认落到空档
    if cutoff is not None:
        chosen_cutoff = cutoff
    else:
        existing_cutoffs = {
            value
            for (value,) in (
                await session.execute(
                    select(UsageSnapshot.cutoff).where(
                        UsageSnapshot.format_id == chosen_format,
                        UsageSnapshot.month == chosen_month,
                    )
                )
            ).all()
        }
        chosen_cutoff = (
            max(existing_cutoffs) if existing_cutoffs else CUTOFFS[-1]
        )

    snapshot = (
        await session.execute(
            select(UsageSnapshot).where(
                UsageSnapshot.format_id == chosen_format,
                UsageSnapshot.month == chosen_month,
                UsageSnapshot.cutoff == chosen_cutoff,
            )
        )
    ).scalar_one_or_none()

    items: list[dict] = []
    total = 0
    battles = 0
    has_snapshot = snapshot is not None
    if snapshot is not None:
        battles = snapshot.battles
        stmt = select(UsageSnapshotEntry).where(UsageSnapshotEntry.snapshot_id == snapshot.id)
        if search:
            needle = search.strip().lower()
            if needle.isdigit():
                stmt = stmt.where(
                    (UsageSnapshotEntry.dex_number == int(needle))
                    | func.lower(UsageSnapshotEntry.showdown_name).like(f"%{needle}%")
                )
            else:
                stmt = stmt.where(func.lower(UsageSnapshotEntry.showdown_name).like(f"%{needle}%"))
        total = (
            await session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        rows = list(
            (
                await session.execute(
                    stmt.order_by(UsageSnapshotEntry.rank.asc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        items = [await _entry_view(session, row) for row in rows]

    fmt = FORMAT_BY_ID.get(chosen_format)
    return {
        "format_id": chosen_format,
        "format_label": fmt.label if fmt else chosen_format,
        "game": fmt.game if fmt else "",
        "ruleset": fmt.ruleset if fmt else "",
        "month": chosen_month,
        "cutoff": chosen_cutoff,
        "battles": battles,
        "has_snapshot": has_snapshot,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items": items,
        "months": months,
        "formats": formats,
        "cutoffs": list(CUTOFFS),
    }


async def usage_months(session: AsyncSession, format_id: str) -> list[str]:
    rows = (
        await session.execute(
            select(UsageSnapshot.month).where(UsageSnapshot.format_id == format_id).distinct()
        )
    ).all()
    return sorted({month for (month,) in rows})


async def _entry_view(session: AsyncSession, entry: UsageSnapshotEntry) -> dict:
    """给排行榜条目补图鉴信息（中文名 / 属性 / 图标）。"""
    if entry.dex_number is None:
        return {
            "rank": entry.rank,
            "showdown_name": entry.showdown_name,
            "dex_number": None,
            "name_zh": None,
            "name_en": None,
            "types": [],
            "sprite_url": None,
            "usage": entry.usage,
            "raw_count": entry.raw_count,
        }

    briefs = await pokemon_repo.get_pokemon_briefs(session, [entry.dex_number])
    brief = briefs.get(entry.dex_number)
    types = []
    sprite = None
    name_zh = name_en = None
    if brief is not None:
        try:
            types = json.loads(brief[2] or "[]")
        except (json.JSONDecodeError, TypeError):
            types = []
        name_zh, name_en, sprite = brief[0], brief[1], brief[5]
    return {
        "rank": entry.rank,
        "showdown_name": entry.showdown_name,
        "dex_number": entry.dex_number,
        "name_zh": name_zh,
        "name_en": name_en,
        "types": types,
        "sprite_url": f"/media/{sprite}" if sprite else None,
        "usage": entry.usage,
        "raw_count": entry.raw_count,
    }


async def latest_run(session: AsyncSession) -> UsageSyncRun | None:
    return (
        await session.execute(select(UsageSyncRun).order_by(UsageSyncRun.id.desc()).limit(1))
    ).scalar_one_or_none()
