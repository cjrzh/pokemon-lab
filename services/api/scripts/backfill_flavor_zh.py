"""中文图鉴描述回填脚本。

用途：已有大批量同步数据后，补上 `data/flavor-zh/` 里的项目自译，并记录来源。
不访问网络、不重拉 PokéAPI，只读本地库 + 仓库内译文文件。

用法（在 services/api 目录下）：
    uv run python scripts/backfill_flavor_zh.py            # 应用译文
    uv run python scripts/backfill_flavor_zh.py --dry-run  # 只看会改哪些
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.engine import init_db, session_scope  # noqa: E402
from app.db.models import Pokemon  # noqa: E402
from app.services.flavor_translation_service import (  # noqa: E402
    SOURCE_PROJECT,
    load_genus_translations,
    load_translations,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    args = parser.parse_args()

    await init_db()
    flavor = load_translations()
    genus = load_genus_translations()

    filled_flavor = 0
    filled_genus = 0
    marked_pokeapi = 0
    missing = []

    async with session_scope() as session:
        rows = (await session.execute(select(Pokemon).order_by(Pokemon.dex_number))).scalars().all()
        for pokemon in rows:
            changed = False

            # 已有中文：标为 pokeapi（上游官方文本优先，一律不覆盖）
            if pokemon.flavor_zh:
                if pokemon.flavor_zh_source != "pokeapi":
                    pokemon.flavor_zh_source = "pokeapi"
                    marked_pokeapi += 1
                    changed = True
            elif pokemon.dex_number in flavor:
                pokemon.flavor_zh = flavor[pokemon.dex_number]
                pokemon.flavor_zh_source = SOURCE_PROJECT
                filled_flavor += 1
                changed = True
            else:
                missing.append(pokemon.dex_number)
                pokemon.flavor_zh_source = None

            if pokemon.genus_zh:
                if pokemon.genus_zh_source != "pokeapi":
                    pokemon.genus_zh_source = "pokeapi"
                    changed = True
            elif pokemon.dex_number in genus:
                pokemon.genus_zh = genus[pokemon.dex_number]
                pokemon.genus_zh_source = SOURCE_PROJECT
                filled_genus += 1
                changed = True
            else:
                pokemon.genus_zh_source = None

            if changed and not args.dry_run:
                session.add(pokemon)

        if args.dry_run:
            await session.rollback()

    mode = "[dry-run] " if args.dry_run else ""
    print(
        f"{mode}图鉴描述：补入译文 {filled_flavor} 条，标记官方来源 {marked_pokeapi} 条；"
        f"分类：补入译文 {filled_genus} 条"
    )
    if missing:
        print(f"仍无中文描述的编号（{len(missing)}）：{missing[:20]}…")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
