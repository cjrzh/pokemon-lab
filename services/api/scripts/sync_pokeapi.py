"""PokéAPI 图鉴同步脚本（手动预拉取，站点脱网可用的基础）。

用法（在 services/api 目录下）：
    uv run python scripts/sync_pokeapi.py                    # 同步全国图鉴 #1-1025
    uv run python scripts/sync_pokeapi.py --range 1-25       # 指定区间
    uv run python scripts/sync_pokeapi.py --gen 2            # 按世代（可写 3-5）
    uv run python scripts/sync_pokeapi.py --gen 2 --resume   # 跳过已同步，断点续传
    uv run python scripts/sync_pokeapi.py --dry-run          # 只统计不动库
    uv run python scripts/sync_pokeapi.py --force            # 覆盖手动编辑过的记录
    uv run python scripts/sync_pokeapi.py --force-artwork    # 只补立绘
    uv run python scripts/sync_pokeapi.py --sprites          # 只补小图标（96×96）

同步规则见 services/dex_sync_service.py 的模块注释（manual 记录默认跳过）。
全国图鉴共 1025 只（Gen 1–9）；首次全量同步较慢（含招式详情与立绘），
建议按世代分批执行，例如 `--gen 2`、`--gen 3-4`。
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

# 允许 `uv run python scripts/sync_pokeapi.py` 直接运行：把 services/api 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.pokeapi import UpstreamError  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.engine import init_db, session_scope  # noqa: E402
from app.repositories import pokemon_repo  # noqa: E402
from app.services.artwork_service import ensure_artwork  # noqa: E402
from app.services.dex_sync_service import (
    NATIONAL_DEX_GENERATIONS,
    NATIONAL_DEX_TOTAL,
    sync_range,
)  # noqa: E402
from app.services.sprite_service import ensure_sprite  # noqa: E402

RANGE_PATTERN = re.compile(r"^(\d+)-(\d+)$")


def parse_range(value: str) -> tuple[int, int]:
    match = RANGE_PATTERN.match(value.strip())
    if not match:
        raise argparse.ArgumentTypeError(f"区间格式应为 start-end，如 1-151：{value!r}")
    start, end = int(match.group(1)), int(match.group(2))
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError(f"区间不合法：{value!r}（应为 1 ≤ start ≤ end）")
    return start, end


def parse_generation_range(value: str) -> tuple[int, int]:
    """世代区间（如 "2" 或 "3-5"）→ 全国图鉴编号闭区间。"""
    text = value.strip()
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", text)
    if not match:
        raise argparse.ArgumentTypeError(f"世代格式应为 N 或 N-M，如 2 或 3-5：{value!r}")
    first = int(match.group(1))
    last = int(match.group(2) or match.group(1))
    if first < 1 or last > 9 or first > last:
        raise argparse.ArgumentTypeError(f"世代区间不合法：{value!r}（应在 1–9 内且 start ≤ end）")
    return NATIONAL_DEX_GENERATIONS[first][0], NATIONAL_DEX_GENERATIONS[last][1]


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    range_group = parser.add_mutually_exclusive_group()
    range_group.add_argument(
        "--range",
        type=parse_range,
        metavar="START-END",
        help=f"同步区间，默认 1-{NATIONAL_DEX_TOTAL}（全国图鉴）",
    )
    range_group.add_argument(
        "--gen",
        type=parse_generation_range,
        metavar="N[-M]",
        help="按世代同步，如 --gen 2 或 --gen 3-5（包含边界）",
    )
    parser.add_argument(
        "--force-artwork",
        action="store_true",
        help="重新下载已存在的立绘（默认复用本地缓存）",
    )
    parser.add_argument(
        "--sprites",
        action="store_true",
        help="只补小图标（96×96 sprite，图鉴列表与特性页使用），不修改数据正文",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="跳过本地已有且来自 PokéAPI 的记录（断点续传；manual 记录总是跳过）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不动库")
    parser.add_argument("--force", action="store_true", help="覆盖手动编辑过的记录（默认跳过）")
    args = parser.parse_args()

    start, end = args.gen or args.range or (1, NATIONAL_DEX_TOTAL)

    await init_db()

    if args.dry_run:
        overview = await _dry_run()
        print(
            f"[dry-run] 目标区间 #{start}-#{end}，当前库中共 {overview['total']} 条记录"
            f"（目标区间 {end - start + 1} 条）"
        )
        return 0

    if args.force_artwork:
        return await _backfill_artwork(start, end)

    if args.sprites:
        return await _backfill_sprites(start, end)

    print(
        f"开始同步 #{start}-#{end}"
        "（含特性 / 招式详情与立绘；已有上游缓存会复用）…"
    )
    try:
        async with session_scope() as session:
            result = await sync_range(
                session,
                start,
                end,
                force=args.force,
                skip_existing=args.resume,
                progress=_print_progress,
            )
    except UpstreamError as exc:
        print(f"同步失败：{exc}", file=sys.stderr)
        return 2

    print(result.summary())
    if result.skipped_manual:
        print(f"  手动记录未覆盖：{result.skipped_manual}")
    if result.skipped_existing:
        print(f"  已存在记录跳过：{len(result.skipped_existing)} 条")
    if result.failed:
        print(f"  失败明细：{result.failed}")
    return 0 if not result.failed else 1


def _print_progress(done: int, total: int, dex_number: int) -> None:
    """每 10 只输出一次进度（不刷屏，同时能看出同步在前进）。"""
    if done % 10 == 0 or done == total:
        print(f"  [{done}/{total}] 已处理到 #{dex_number:04d}", flush=True)


async def _backfill_artwork(start: int, end: int) -> int:
    """只补立绘：下载缺失图片并把路径写回记录。

    不修改数据正文，也不会把记录标记为 manual。
    """
    settings = get_settings()
    settings.artwork_dir.mkdir(parents=True, exist_ok=True)

    updated = 0
    failed = 0
    async with session_scope() as session:
        records = await pokemon_repo.list_missing_artwork(session)
        for record in records:
            if not (start <= record.dex_number <= end):
                continue
            existed = (settings.artwork_dir / f"{record.dex_number}.png").exists()
            path = await ensure_artwork(record.dex_number)
            if path is None:
                failed += 1
                continue
            await pokemon_repo.set_artwork_path(session, record, path)
            updated += 1
            await session.commit()  # 逐条提交，避免长时间占用写锁
            if not existed:
                print(f"  下载 #{record.dex_number:04d} 立绘")

    print(f"立绘补齐：写入 {updated} 条，失败 {failed} 张")
    return 0 if failed == 0 else 1


async def _backfill_sprites(start: int, end: int, concurrency: int = 8) -> int:
    """同步小图标：下载缺失的 96×96 sprite 并把路径写回记录。

    小文件可以并发下载；每个 worker 各自占一个数据库会话（SQLite 写操作串行，
    但下载耗时占大头）。只更新 `sprite_path`，不改数据正文、不标记 manual。
    """
    settings = get_settings()
    settings.sprite_dir.mkdir(parents=True, exist_ok=True)

    async with session_scope() as session:
        records = [
            record
            for record in await pokemon_repo.list_missing_sprites(session)
            if start <= record.dex_number <= end
        ]
        dex_numbers = [record.dex_number for record in records]

    print(f"需要下载小图标：{len(dex_numbers)} 只（#{start}-#{end}，并发 {concurrency}）")
    semaphore = asyncio.Semaphore(concurrency)
    updated = 0
    failed = 0
    done = 0

    async def worker(dex: int) -> str | None:
        async with semaphore:
            return await ensure_sprite(dex)

    # 分批处理：下载并发，写库逐条（SQLite 同一时刻只有一个写入者）
    batch_size = concurrency * 4
    for offset in range(0, len(dex_numbers), batch_size):
        batch = dex_numbers[offset : offset + batch_size]
        results = await asyncio.gather(*(worker(dex) for dex in batch))
        async with session_scope() as session:
            for dex, path in zip(batch, results, strict=True):
                done += 1
                if path is None:
                    failed += 1
                else:
                    record = await pokemon_repo.get_by_dex_number(session, dex)
                    if record is not None:
                        await pokemon_repo.set_sprite_path(session, record, path)
                        updated += 1
            await session.commit()
        print(f"  进度 {done}/{len(dex_numbers)}（写入 {updated}，失败 {failed}）", flush=True)

    print(f"小图标同步：写入 {updated} 条，失败 {failed} 张")
    return 0 if failed == 0 else 1


async def _dry_run() -> dict:
    """统计现有覆盖情况，不发起网络请求。"""
    async with session_scope() as session:
        return await pokemon_repo.get_sync_overview(session)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
