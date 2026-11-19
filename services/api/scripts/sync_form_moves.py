"""回填形态招式表（`pokemon_form_move`）。

队伍合法性校验按图鉴编号合并「默认形态 + 全部形态」的招式；形态专属招式
（连击流的水流连打、厄诡椪面具形态的棘藤棒等）只出现在 PokéAPI 的形态响应里，
因此旧库需要跑一次本脚本补齐（`scripts/sync_forms.py` 也会顺带写入）。

用法（在 services/api 目录下）：
    uv run python scripts/sync_form_moves.py                 # 全部物种
    uv run python scripts/sync_form_moves.py --range 1-151   # 指定编号区间
    uv run python scripts/sync_form_moves.py --dex 892       # 指定编号（可重复）

幂等：按形态整体替换招式表，重复执行不会产生重复行。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import init_db, session_scope  # noqa: E402
from app.services.form_service import sync_forms  # noqa: E402


def parse_range(value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise argparse.ArgumentTypeError(f"区间格式应为 start-end：{value!r}")
    start, end = int(parts[0]), int(parts[1])
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError(f"区间不合法：{value!r}")
    return start, end


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--range", type=parse_range, help="编号区间，如 1-151")
    parser.add_argument("--dex", type=int, action="append", help="指定编号（可重复）")
    parser.add_argument("--concurrency", type=int, default=8, help="并发请求数（默认 8）")
    args = parser.parse_args()

    await init_db()
    dex_numbers: list[int] | None
    if args.dex:
        dex_numbers = sorted(set(args.dex))
    elif args.range:
        start, end = args.range
        dex_numbers = list(range(start, end + 1))
    else:
        dex_numbers = None

    print("开始回填形态招式表…")
    async with session_scope() as session:
        result = await sync_forms(session, dex_numbers, concurrency=max(1, args.concurrency))
    print(result.summary())
    return 0 if not result.failed else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
