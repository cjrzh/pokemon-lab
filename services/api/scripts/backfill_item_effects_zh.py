"""道具说明中文回填脚本。

用途：把 `data/items/effects-zh.json` 的项目自译写进 `item_ref.effect_zh`，
并标记来源。不访问网络，只读本地库 + 仓库内译文文件。

用法（在 services/api 目录下）：
    uv run python scripts/backfill_item_effects_zh.py            # 应用译文
    uv run python scripts/backfill_item_effects_zh.py --dry-run  # 只看会改哪些
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.engine import init_db, session_scope  # noqa: E402
from app.db.models import ItemReference  # noqa: E402
from app.services.flavor_translation_service import (  # noqa: E402
    SOURCE_PROJECT,
    load_item_effect_translations,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    args = parser.parse_args()

    await init_db()
    translations = load_item_effect_translations()

    filled = 0
    missing: list[str] = []

    async with session_scope() as session:
        rows = (await session.execute(select(ItemReference))).scalars().all()
        for item in rows:
            translated = translations.get(item.name)
            if not translated:
                missing.append(item.name)
                continue
            if item.effect_zh == translated and item.effect_zh_source == SOURCE_PROJECT:
                continue  # 已是同一份译文，不重复写
            item.effect_zh = translated
            item.effect_zh_source = SOURCE_PROJECT
            filled += 1

    verb = "将写入" if args.dry_run else "已写入"
    print(f"{verb} {filled} 条道具说明译文（共 {len(rows)} 个道具）")
    if missing:
        print(f"缺少译文 {len(missing)} 条：{', '.join(sorted(missing)[:20])}"
              f"{' …' if len(missing) > 20 else ''}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
