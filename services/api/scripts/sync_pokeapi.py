"""PokéAPI 图鉴同步脚本（手动预拉取，站点脱网可用的基础）。

用法（在 services/api 目录下）：
    uv run python scripts/sync_pokeapi.py                    # 同步 #1-151（MVP 默认范围）
    uv run python scripts/sync_pokeapi.py --range 1-25       # 指定区间
    uv run python scripts/sync_pokeapi.py --dry-run          # 只统计不动库
    uv run python scripts/sync_pokeapi.py --force            # 覆盖手动编辑过的记录

同步规则见 services/dex_sync_service.py 的模块注释（manual 记录默认跳过）。
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
from app.db.engine import init_db, session_scope  # noqa: E402
from app.repositories import pokemon_repo  # noqa: E402
from app.services.dex_sync_service import sync_range  # noqa: E402

RANGE_PATTERN = re.compile(r"^(\d+)-(\d+)$")


def parse_range(value: str) -> tuple[int, int]:
    match = RANGE_PATTERN.match(value.strip())
    if not match:
        raise argparse.ArgumentTypeError(f"区间格式应为 start-end，如 1-151：{value!r}")
    start, end = int(match.group(1)), int(match.group(2))
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError(f"区间不合法：{value!r}（应为 1 ≤ start ≤ end）")
    return start, end


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--range",
        type=parse_range,
        default=(1, 151),
        metavar="START-END",
        help="同步区间，默认 1-151",
    )
    parser.add_argument("--dry-run", action="store_true", help="只拉取与解析，不写库")
    parser.add_argument("--force", action="store_true", help="覆盖手动编辑过的记录（默认跳过）")
    args = parser.parse_args()
    start, end = args.range

    await init_db()

    if args.dry_run:
        overview = await _dry_run(start, end)
        print(f"[dry-run] 目标区间 #{start}-#{end}，当前库中共 {overview['total']} 条记录")
        return 0

    print(f"开始同步 #{start}-#{end}（每只 3 个上游请求，量大时请耐心）…")
    try:
        async with session_scope() as session:
            result = await sync_range(session, start, end, force=args.force)
    except UpstreamError as exc:
        print(f"同步失败：{exc}", file=sys.stderr)
        return 2

    print(result.summary())
    if result.skipped_manual:
        print(f"  手动记录未覆盖：{result.skipped_manual}")
    if result.failed:
        print(f"  失败明细：{result.failed}")
    return 0 if not result.failed else 1


async def _dry_run(start: int, end: int) -> dict:
    """统计现有覆盖情况，不发起网络请求。"""
    async with session_scope() as session:
        return await pokemon_repo.get_sync_overview(session)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
