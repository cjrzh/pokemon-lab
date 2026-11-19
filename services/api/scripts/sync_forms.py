"""同步宝可梦形态（机制上不同的其它样子）。

用法（在 services/api 目录下）：
    uv run python scripts/sync_forms.py                 # 同步全部物种的形态
    uv run python scripts/sync_forms.py --range 1-151   # 只同步指定编号区间
    uv run python scripts/sync_forms.py --dex 892       # 只同步指定编号（可重复）

默认只收录「属性 / 种族值 / 特性 / 身高体重」与默认形态不同的形态；
纯外观差异（超极巨化、霸主、性别变体）与只改模型的形态会被跳过。
`--all-forms` 会把其余「非纯外观」形态（如 mega 形态）也写进图鉴表。

无论是否写入图鉴表，所有非纯外观形态的**招式表**都会落库
（`pokemon_form_move`），队伍合法性校验按图鉴编号合并 —— 连击流的水流连打、
蕾冠王的雪矛等形态专属招式才能被正确认可。
形态的中文名来自 `data/forms/zh-hans.json`，缺失时界面显示英文。
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
    parser.add_argument(
        "--all-forms",
        action="store_true",
        help="把与默认形态机制相同的非纯外观形态也写进图鉴表（补齐历史遗漏）",
    )
    args = parser.parse_args()

    await init_db()

    if args.dex:
        dex_numbers = sorted(set(args.dex))
    elif args.range:
        start, end = args.range
        dex_numbers = list(range(start, end + 1))
    else:
        dex_numbers = None  # 全部

    scope = f"编号 {len(dex_numbers)} 个" if dex_numbers else "全部物种"
    print(f"开始同步形态（{scope}）…")
    async with session_scope() as session:
        result = await sync_forms(
            session,
            dex_numbers,
            concurrency=max(1, args.concurrency),
            include_forms=args.all_forms,
        )

    print(result.summary())
    if result.failed:
        for key, reason in sorted(result.failed.items()):
            print(f"  {key}: {reason}")
    return 0 if not result.failed else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
