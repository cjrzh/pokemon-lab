"""同步双打统计里出现的道具：中文名、分类、说明与 30×30 图标。

用法（在 services/api 目录下）：
    uv run python scripts/sync_items.py              # 同步 data/doubles/labels.json 里的全部道具
    uv run python scripts/sync_items.py --no-icons   # 只拉元数据，不下载图标
    uv run python scripts/sync_items.py --slugs leftovers,life-orb

数据来源：PokéAPI `/item/{slug}`（公开接口，无需密钥）。只同步实际被统计引用
的道具（当前约 257 个），不是 PokéAPI 的全部 2223 个条目。
图标经 wsrv 代理下载到 `var/media/items/{slug}.png`，由 `/media` 静态托管。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 允许 `uv run python scripts/sync_items.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import init_db, session_scope  # noqa: E402
from app.services import doubles_service, item_service  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--slugs",
        help="逗号分隔的道具 slug；默认取 data/doubles/labels.json 的全部道具",
    )
    parser.add_argument("--no-icons", action="store_true", help="只同步元数据，不下载图标")
    parser.add_argument("--concurrency", type=int, default=8, help="并发请求数（默认 8）")
    args = parser.parse_args()

    if args.slugs:
        slugs = [slug.strip() for slug in args.slugs.split(",") if slug.strip()]
    else:
        slugs = sorted(doubles_service.load_labels().get("items", {}))
    if not slugs:
        print("没有可同步的道具：data/doubles/labels.json 缺少 items", file=sys.stderr)
        return 1

    await init_db()
    print(f"开始同步 {len(slugs)} 个道具（图标：{'否' if args.no_icons else '是'}）…")
    async with session_scope() as session:
        result = await item_service.sync_items(
            session,
            slugs,
            concurrency=max(1, args.concurrency),
            download_icons=not args.no_icons,
        )

    print(result.summary())
    if result.failed:
        print("失败明细：")
        for slug, reason in sorted(result.failed.items()):
            print(f"  {slug}: {reason}")
    return 0 if not result.failed else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
