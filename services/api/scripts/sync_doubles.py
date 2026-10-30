"""双打统计数据导入脚本。

把 `data/doubles/*.json`（由 scripts/fetch_doubles_stats.py 生成）导入本地 SQLite。
不访问网络。

用法（在 services/api 目录下）：
    uv run python scripts/sync_doubles.py                 # 导入全部格式
    uv run python scripts/sync_doubles.py --format sv     # 只导入一个格式（可重复）
    uv run python scripts/sync_doubles.py --fetch         # 先联网抓取再导入
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import init_db, session_scope  # noqa: E402
from app.domain.doubles_formats import FORMAT_BY_KEY  # noqa: E402
from app.services.doubles_service import DoublesDataError, import_datasets  # noqa: E402


async def main(keys: list[str] | None) -> int:
    await init_db()
    try:
        async with session_scope() as session:
            result = await import_datasets(session, keys)
    except DoublesDataError as exc:
        print(f"导入失败：{exc}", file=sys.stderr)
        return 2

    print(
        f"导入完成：{result['formats']} 个格式 / {result['entries']} 条记录 {result['per_format']}"
    )
    if result["unresolved"]:
        print(f"未映射到图鉴的显示名：{result['unresolved']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--format",
        choices=sorted(FORMAT_BY_KEY),
        action="append",
        help="只导入指定格式（可重复）；默认全部",
    )
    parser.add_argument("--fetch", action="store_true", help="先运行抓取脚本，再导入")
    args = parser.parse_args()

    if args.fetch:
        command = [sys.executable, str(Path(__file__).with_name("fetch_doubles_stats.py"))]
        for key in args.format or []:
            command.extend(["--format", key])
        subprocess.run(command, check=True)  # noqa: S603 - 固定本地脚本

    try:
        sys.exit(asyncio.run(main(args.format)))
    except KeyboardInterrupt:
        sys.exit(130)
