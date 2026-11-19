"""回填 `move_ref` 缺失的招式（按 slug 直接查 PokéAPI `/move/{slug}`）。

为什么需要：
  `move_ref` 平时由图鉴同步写入 —— 只收录「某只宝可梦的 moves 列表里出现过」的招式。
  PokéAPI 的 `/pokemon/{id}` 偶尔漏掉某些招式（例如 Urshifu #892 没有「水流连打」），
  而双打统计里又确实用到它，结果详情页与排行页的招式缺属性徽章。

  本脚本按 slug 直接拉 `/move/{slug}`，补齐 `move_ref` 的数值字段；
  不修改 `pokemon.moves_json`（不伪造学习记录），因此「谁会这招」不受影响。

用法（在 services/api 目录下）：
    uv run python scripts/backfill_move_refs.py            # 回填双打统计里缺失的招式
    uv run python scripts/backfill_move_refs.py --slugs surging-strikes
    uv run python scripts/backfill_move_refs.py --all      # 回填 data/doubles 标签里的全部招式
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.pokeapi import UpstreamError, fetch_json, parse_payload  # noqa: E402
from app.db.engine import init_db, session_scope  # noqa: E402
from app.domain.pokemon_parser import PokemonParseError, parse_move_details  # noqa: E402
from app.repositories import pokemon_repo  # noqa: E402
from app.services import doubles_service  # noqa: E402


def _doubles_move_slugs() -> set[str]:
    """双打统计（四个格式）里实际出现过的招式 slug。

    数据目录是仓库根的 `data/doubles`（不是 services/api/data），
    与 `doubles_service.load_labels()` 使用同一份来源。
    """
    slugs: set[str] = set()
    data_dir = Path(__file__).resolve().parents[3] / "data" / "doubles"
    for path in data_dir.glob("*.json"):
        if path.name == "labels.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for entry in payload.get("entries", []):
            slugs.update(slug for slug, _ in entry.get("moves", []))
    return slugs


async def backfill(slugs: list[str]) -> tuple[int, dict[str, str]]:
    """按 slug 拉取招式详情并写入 move_ref；返回（写入数，失败明细）。"""
    written = 0
    failed: dict[str, str] = {}
    async with session_scope() as session:
        existing = await pokemon_repo.get_move_ref_names(session, slugs)
        pending = [slug for slug in slugs if slug not in existing]
        print(f"待回填 {len(pending)} 个招式（已存在 {len(slugs) - len(pending)} 个）")

        details: list[dict] = []
        for slug in pending:
            try:
                payload = parse_payload((await fetch_json(session, f"/move/{slug}")).payload)
                if not isinstance(payload, dict):
                    raise PokemonParseError("上游返回非对象")
                details.append(parse_move_details(payload))
            except (UpstreamError, PokemonParseError) as exc:
                failed[slug] = str(exc)

        written = await pokemon_repo.upsert_move_refs(session, details)
        # 新招式没有学习记录：learner_count 保持 0（重建索引时也会是 0）
    return written, failed


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--slugs", help="逗号分隔的招式 slug；默认取双打统计里缺失的招式")
    parser.add_argument(
        "--all",
        action="store_true",
        help="回填 data/doubles/labels.json 里的全部招式（不只缺失的）",
    )
    args = parser.parse_args()

    if args.slugs:
        slugs = [slug.strip() for slug in args.slugs.split(",") if slug.strip()]
    else:
        labels = doubles_service.load_labels()
        if args.all:
            slugs = sorted(labels.get("moves", {}))
        else:
            slugs = sorted(_doubles_move_slugs() & set(labels.get("moves", {})))

    if not slugs:
        print("没有可回填的招式", file=sys.stderr)
        return 1

    await init_db()
    written, failed = await backfill(slugs)

    print(f"回填完成：写入 {written} 个招式，失败 {len(failed)} 个")
    if failed:
        for slug, reason in sorted(failed.items()):
            print(f"  {slug}: {reason}")
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
