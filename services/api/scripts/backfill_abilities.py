"""特性参考表回填脚本。

从本地已同步的宝可梦记录汇总特性到 `ability` 表，并应用
`data/abilities/s-tier.json` 的 LLM 预评。不访问网络。

用法（在 services/api 目录下）：
    uv run python scripts/backfill_abilities.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import init_db, session_scope  # noqa: E402
from app.services.ability_service import sync_abilities  # noqa: E402


async def main() -> int:
    await init_db()
    async with session_scope() as session:
        stats = await sync_abilities(session)
    print(
        f"特性回填完成：共 {stats['abilities']} 个特性，S 级 {stats['s_tier']} 个，"
        f"新增 {stats['new']} 个"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
