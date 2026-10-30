"""招式百科公开路由（只读）。

`GET /moves`：11 种筛选 / 排序方式，列表页用；
`GET /moves/{name}`：完整数值、图鉴说明，以及**会这招的宝可梦**
（按图鉴编号排序，可跳转 `/dex/{dex}`）。

双向链接的另一半在 `/pokemon/{dex}`：详情页招式表里的每个招式名都链接到本页。
学习者数据来自 `move_learner` 派生表（见 services/move_service.py）。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.domain.pokemon_parser import DAMAGE_CLASS_ZH
from app.repositories import pokemon_repo
from app.repositories.pokemon_repo import MoveListQuery
from app.schemas.moves import (
    MoveDetail,
    MoveLearnEntry,
    MoveLearnerPokemon,
    MoveListMeta,
    MoveListResponse,
    MoveSummary,
)
from app.services.move_service import method_label, version_label

router = APIRouter(prefix="/moves", tags=["moves"])

#: 与图鉴 / 特性页共用同一套属性键，非法值直接 422。
DAMAGE_CLASSES = ("physical", "special", "status")
SORT_FIELDS = ("name", "power", "accuracy", "pp", "learners")


def _summary(move) -> MoveSummary:
    return MoveSummary(
        name=move.name,
        zh=move.zh,
        name_en=move.name_en or " ".join(part.capitalize() for part in move.name.split("-")),
        type=move.type,
        damage_class=move.damage_class,  # type: ignore[arg-type]
        damage_class_zh=DAMAGE_CLASS_ZH.get(move.damage_class or ""),
        power=move.power,
        accuracy=move.accuracy,
        pp=move.pp,
        description_zh=move.description_zh,
        learner_count=move.learner_count,
        is_machine=move.is_machine,
    )


@router.get(
    "",
    response_model=MoveListResponse,
    summary="招式列表",
    description=(
        "名称 / 说明搜索，按属性、伤害分类、学习器筛选，按威力 / 命中 / PP / 学习者数排序。"
    ),
)
async def list_moves(
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, max_length=64, description="中英文名或说明关键词"),
    type: str | None = Query(default=None, description="属性英文键，如 fire"),
    damage_class: str | None = Query(default=None, description="physical / special / status"),
    machine_only: bool = Query(default=False, description="只看可被招式学习器学会的招式"),
    sort: str = Query(default="name", description=f"排序字段：{', '.join(SORT_FIELDS)}"),
) -> MoveListResponse:
    if damage_class is not None and damage_class not in DAMAGE_CLASSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"damage_class 只接受 {DAMAGE_CLASSES}",
        )
    if sort not in SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"sort 只接受 {SORT_FIELDS}",
        )

    items, total = await pokemon_repo.list_moves(
        session,
        MoveListQuery(
            search=q,
            type_filter=type,
            damage_class=damage_class,
            machine_only=machine_only,
            sort=sort,
            page=page,
            page_size=page_size,
        ),
    )
    return MoveListResponse(
        items=[_summary(move) for move in items],
        meta=MoveListMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, -(-total // page_size)),
        ),
    )


@router.get(
    "/{name}",
    response_model=MoveDetail,
    summary="招式详情",
    description="完整数值与说明，以及会这招的宝可梦（按版本组展示学习方式）。",
)
async def get_move(session: DbSession, name: str) -> MoveDetail:
    move = await pokemon_repo.get_move(session, name)
    if move is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"招式 {name!r} 不存在（尚未同步或拼写有误）",
        )

    learner_rows = await pokemon_repo.get_move_learners(session, name)
    briefs = await pokemon_repo.get_pokemon_briefs(
        session, [row.dex_number for row in learner_rows]
    )

    learners: list[MoveLearnerPokemon] = []
    learners_by_version: dict[str, int] = {}
    method_counts: dict[str, int] = {}

    for row in learner_rows:
        brief = briefs.get(row.dex_number)
        if brief is None:
            continue
        name_zh, name_en, types_json, legendary, mythical = brief
        try:
            version_groups = json.loads(row.version_groups_json or "{}")
        except (json.JSONDecodeError, TypeError):
            version_groups = {}
        try:
            types = json.loads(types_json or "[]")
        except (json.JSONDecodeError, TypeError):
            types = []

        methods: dict[str, list[MoveLearnEntry]] = {}
        for version_group, entries in version_groups.items():
            methods[version_group] = [
                MoveLearnEntry(
                    method=entry["method"],
                    method_label=method_label(entry["method"]),
                    level=int(entry.get("level") or 0),
                )
                for entry in entries
            ]
            learners_by_version[version_group] = learners_by_version.get(version_group, 0) + 1
            for entry in entries:
                method_counts[entry["method"]] = method_counts.get(entry["method"], 0) + 1

        latest = next(iter(version_groups), None)
        learners.append(
            MoveLearnerPokemon(
                dex_number=row.dex_number,
                name_zh=name_zh,
                name_en=name_en,
                types=types,
                is_legendary=legendary,
                is_mythical=mythical,
                version_groups=methods,
                latest_methods=[entry["method"] for entry in version_groups.get(latest, [])],
            )
        )

    return MoveDetail(
        **_summary(move).model_dump(),
        learners=learners,
        learners_by_version=dict(sorted(learners_by_version.items(), key=lambda item: -item[1])),
        method_counts=dict(sorted(method_counts.items(), key=lambda item: -item[1])),
        version_labels={vg: version_label(vg) for vg in learners_by_version},
        method_labels={method: method_label(method) for method in method_counts},
    )
