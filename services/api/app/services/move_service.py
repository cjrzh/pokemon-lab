"""招式百科的数据服务：学习者索引、标签与查询组装。

数据链路：
  `pokemon.moves_json`（同步时写入的「版本组 → 学习方式 → 招式」）
  → `rebuild_move_index()` 展开为 `move_learner` 派生表（每招 × 每只宝可梦一行）
  → `/moves` 列表与 `/moves/{name}` 详情。

设计约定：
  - `move_learner` 是纯派生数据：每次同步 / 回填都整表重建，不接受手工编辑；
  - 招式数值仍在 `move_ref`，这里只补展示用的 `name_en` / `learner_count`；
  - 学习方式与版本组的顺序共享 `domain/pokemon_parser.py` 的常量，避免前后端各自排序。
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MoveLearner, MoveReference, Pokemon
from app.domain.pokemon_parser import (
    LEARN_METHOD_ORDER,
    LEARN_METHOD_ZH,
    MOVE_VERSION_GROUP_ORDER,
    VERSION_GROUP_ZH,
)
from app.services.doubles_service import load_labels

logger = logging.getLogger(__name__)


def _method_rank(method: str) -> int:
    try:
        return LEARN_METHOD_ORDER.index(method)
    except ValueError:
        return len(LEARN_METHOD_ORDER)


def _version_rank(version_group: str) -> int:
    try:
        return MOVE_VERSION_GROUP_ORDER.index(version_group)
    except ValueError:
        return len(MOVE_VERSION_GROUP_ORDER)


def collect_learners(moves_payload: dict) -> dict[str, dict[str, list[dict]]]:
    """把一只宝可梦的 `moves_json` 收窄成「招式 → 版本组 → 学习方式列表」。

    返回结构：{"protect": {"scarlet-violet": [{"method": "machine", "level": 0}]}, ...}
    同一 (版本组, 学习方式) 只保留一条，等级取该方式下最小的正等级。
    """
    learners: dict[str, dict[str, list[dict]]] = {}
    groups = moves_payload.get("version_groups") if isinstance(moves_payload, dict) else None
    if not isinstance(groups, dict):
        return learners

    for version_group, group in groups.items():
        methods = (group or {}).get("methods") or {}
        for method, entries in methods.items():
            for entry in entries or []:
                name = entry.get("name")
                if not name:
                    continue
                level = int(entry.get("level") or 0)
                bucket = learners.setdefault(name, {}).setdefault(version_group, [])
                existing = next((item for item in bucket if item["method"] == method), None)
                if existing is None:
                    bucket.append({"method": method, "level": level})
                elif level and (existing["level"] == 0 or level < existing["level"]):
                    existing["level"] = level

    for version_groups in learners.values():
        for items in version_groups.values():
            items.sort(key=lambda item: (_method_rank(item["method"]), item["level"]))
    return learners


async def rebuild_move_index(session: AsyncSession) -> dict:
    """整表重建 `move_learner`，并刷新 `move_ref` 的 learner_count / is_machine。

    开销：1025 条记录约 21 MB JSON，展开约 8 万行；批量写入后约 3 秒。
    在同步流程末尾调用，与 `sync_abilities()` 并列。
    """
    rows = (await session.execute(select(Pokemon.dex_number, Pokemon.moves_json))).all()

    learn_count: dict[str, set[int]] = {}
    machine_moves: set[str] = set()
    pair_rows: list[dict] = []

    for dex_number, moves_json in rows:
        try:
            payload = json.loads(moves_json or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        learners = collect_learners(payload)
        for move_name, version_groups in learners.items():
            learn_count.setdefault(move_name, set()).add(dex_number)
            for items in version_groups.values():
                if any(item["method"] == "machine" for item in items):
                    machine_moves.add(move_name)
            ordered = dict(sorted(version_groups.items(), key=lambda item: _version_rank(item[0])))
            keys = sorted(
                f"{version_group}:{item['method']}"
                for version_group, items in ordered.items()
                for item in items
            )
            pair_rows.append(
                {
                    "move_name": move_name,
                    "dex_number": dex_number,
                    "version_groups_json": json.dumps(ordered, ensure_ascii=False),
                    "methods_key": "," + ",".join(keys) + ",",
                }
            )

    # 整表重建：8 万行用 executemany 一次写入（逐行 ORM insert 约需 15 秒）
    await session.execute(delete(MoveLearner))
    if pair_rows:
        # 分块 executemany：SQLite 单条语句参数上限 32766，8 万行一次写会超限
        for start in range(0, len(pair_rows), 5000):
            await session.execute(insert(MoveLearner), pair_rows[start : start + 5000])

    # 刷新招式参考表的派生字段
    refs = list((await session.execute(select(MoveReference))).scalars().all())
    for ref in refs:
        ref.learner_count = len(learn_count.get(ref.name, ()))
        ref.is_machine = ref.name in machine_moves
    await session.flush()

    return {
        "moves": len(learn_count),
        "pairs": len(pair_rows),
        "machine_moves": len(machine_moves),
    }


def move_labels(name: str) -> dict:
    """展示用名称：中文优先，英文来自 Showdown 数据，最后回落到 slug。"""
    labels = load_labels()
    zh = labels.get("moves", {}).get(name)
    en = labels.get("moves_en", {}).get(name)
    return {
        "name": name,
        "zh": zh,
        "name_en": en or " ".join(part.capitalize() for part in name.split("-")),
    }


def method_label(method: str) -> str:
    return LEARN_METHOD_ZH.get(method, method)


def version_label(version_group: str) -> str:
    return VERSION_GROUP_ZH.get(version_group, version_group)
