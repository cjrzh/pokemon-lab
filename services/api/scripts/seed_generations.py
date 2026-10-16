"""世代与规则版本种子脚本（幂等）。

写入 `generations` 与 `rulesets` 两张参考数据表。参考数据只有这一份规范来源：
后续所有个人数据（收藏、笔记、考试成绩）都通过 ruleset_id 关联到这里。

用法（在 services/api 目录下）：
    uv run python scripts/seed_generations.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 允许 `uv run python scripts/seed_generations.py` 直接运行：把 services/api 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.db.engine import init_db, session_scope  # noqa: E402
from app.db.models import Generation, Ruleset  # noqa: E402

#: Gen 1–9 世代参考数据。released_at 只精确到年（不同地区发售年份不同，不做精确日期）。
GENERATIONS: list[dict] = [
    {"id": 1, "label": "第一世代", "region": "关都", "released_at": "1996"},
    {"id": 2, "label": "第二世代", "region": "城都", "released_at": "1999"},
    {"id": 3, "label": "第三世代", "region": "丰缘", "released_at": "2002"},
    {"id": 4, "label": "第四世代", "region": "神奥", "released_at": "2006"},
    {"id": 5, "label": "第五世代", "region": "合众", "released_at": "2010"},
    {"id": 6, "label": "第六世代", "region": "卡洛斯", "released_at": "2013"},
    {"id": 7, "label": "第七世代", "region": "阿罗拉", "released_at": "2016"},
    {"id": 8, "label": "第八世代", "region": "伽勒尔", "released_at": "2019"},
    {"id": 9, "label": "第九世代", "region": "帕底亚", "released_at": "2022"},
]

#: MVP 阶段唯一交付的规则版本：Gen 6+ 标准规则（属性克制部分 6–9 代一致）。
RULESETS: list[dict] = [
    {
        "id": "gen6plus-standard",
        "label": "Gen 6+ 标准",
        "generation_id": 6,
        "notes": "属性克制表自第 6 代起规则一致（6/7/8/9 同表）；MVP 默认规则版本。",
    },
]


async def main() -> int:
    await init_db()

    async with session_scope() as session:
        # 幂等：先数一遍，逐条 upsert
        for gen in GENERATIONS:
            existing = (
                await session.execute(select(Generation).where(Generation.id == gen["id"]))
            ).scalar_one_or_none()
            if existing is None:
                session.add(Generation(**gen))
            else:
                existing.label = gen["label"]
                existing.region = gen["region"]
                existing.released_at = gen["released_at"]

        for ruleset in RULESETS:
            existing = (
                await session.execute(select(Ruleset).where(Ruleset.id == ruleset["id"]))
            ).scalar_one_or_none()
            if existing is None:
                session.add(Ruleset(**ruleset))
            else:
                existing.label = ruleset["label"]
                existing.generation_id = ruleset["generation_id"]
                existing.notes = ruleset["notes"]

        gen_count = (
            await session.execute(select(func.count()).select_from(Generation))
        ).scalar_one()
        ruleset_count = (
            await session.execute(select(func.count()).select_from(Ruleset))
        ).scalar_one()

    print(f"世代种子完成：{gen_count} 条世代，{ruleset_count} 条规则版本")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:
        print(f"种子脚本失败：{exc}", file=sys.stderr)
        sys.exit(1)
