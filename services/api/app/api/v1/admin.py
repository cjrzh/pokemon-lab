"""后台管理路由：手动同步触发、内容编辑、操作日志。

职责边界（与公开 /pokemon 的分离）：
  - 公开前端只读浏览 /api/v1/pokemon；
  - 一切「写」操作（同步触发、字段编辑、手动新增）都在 /api/v1/admin/* 下，
    由后台管理页面使用。公开页面不引用这里的任何接口。

MVP 安全边界（如实声明，不做假安全）：本服务为本地个人站，/admin 无认证。
若将来暴露到公网，必须在网关层加认证后才算安全，见 docs/ARCHITECTURE.md。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.clients.pokeapi import UpstreamError
from app.repositories import pokemon_repo
from app.schemas.pokemon import (
    AdminOpLogEntry,
    AdminOpLogResponse,
    AdminPokemonCreate,
    AdminPokemonEdit,
    AdminSyncRequest,
    AdminSyncResultResponse,
    AdminSyncStatusResponse,
    PokemonDetail,
)
from app.services.dex_sync_service import get_sync_status, sync_range
from app.services.type_chart_service import TypeChartUnavailable, load_type_chart

router = APIRouter(prefix="/admin", tags=["admin"])

#: 单次同步的范围上限：防止误传 1-10000 把请求打到天荒地老。
MAX_SYNC_RANGE_SIZE = 300


@router.get(
    "/pokemon/sync/status",
    response_model=AdminSyncStatusResponse,
    summary="同步状态总览",
)
async def read_sync_status(session: DbSession) -> AdminSyncStatusResponse:
    status_payload = await get_sync_status(session)
    return AdminSyncStatusResponse(**status_payload)


@router.post(
    "/pokemon/sync",
    response_model=AdminSyncResultResponse,
    summary="手动触发图鉴同步",
    description="同步区间内的图鉴到本地库。手动编辑过的记录默认跳过，force 可覆盖。",
)
async def trigger_sync(session: DbSession, request: AdminSyncRequest) -> AdminSyncResultResponse:
    if request.end < request.start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end 不得小于 start",
        )
    if request.end - request.start + 1 > MAX_SYNC_RANGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"单次同步范围上限 {MAX_SYNC_RANGE_SIZE} 条，请缩小区间",
        )

    try:
        result = await sync_range(session, request.start, request.end, force=request.force)
    except UpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"PokéAPI 暂不可用，同步中止：{exc}",
        ) from exc

    return AdminSyncResultResponse(
        synced_count=len(result.synced),
        skipped_manual=result.skipped_manual,
        failed=result.failed,
        summary=result.summary(),
    )


@router.put(
    "/pokemon/{dex_number}",
    response_model=PokemonDetail,
    summary="手动编辑图鉴条目",
    description="只更新给出的字段；编辑后的记录标记为手动维护，后续同步默认不再覆盖。",
)
async def edit_pokemon(
    session: DbSession, dex_number: int, edit: AdminPokemonEdit
) -> PokemonDetail:
    pokemon = await pokemon_repo.get_by_dex_number(session, dex_number)
    if pokemon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"图鉴编号 {dex_number} 不存在，如需新增请用 POST /admin/pokemon",
        )

    fields = _edit_to_fields(edit)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="请求体没有任何可更新字段",
        )
    if "types_json" in fields:
        _validate_types(json.loads(fields["types_json"]))

    await pokemon_repo.update_pokemon_fields(session, pokemon, fields)
    await pokemon_repo.log_admin_op(
        session,
        action="pokemon.edit",
        target=f"#{dex_number}",
        detail=f"更新字段：{sorted(fields)}",
    )

    return _to_detail(pokemon)


@router.post(
    "/pokemon",
    response_model=PokemonDetail,
    summary="手动新增图鉴条目",
    description="适合补充自定义/演示条目；演示数据须显式标记 is_demo。",
)
async def create_pokemon(session: DbSession, payload: AdminPokemonCreate) -> PokemonDetail:
    _validate_types(payload.types)

    record = {
        "dex_number": payload.dex_number,
        "name_en": payload.name_en,
        "name_zh": payload.name_zh,
        "types_json": json.dumps(payload.types, ensure_ascii=False),
        "stats_json": json.dumps(payload.stats, ensure_ascii=False),
        "abilities_json": json.dumps(
            [a.model_dump() for a in payload.abilities], ensure_ascii=False
        ),
        "evolution_json": json.dumps(payload.evolution, ensure_ascii=False),
        "generation_introduced": payload.generation_introduced,
        "height_dm": payload.height_dm,
        "weight_hg": payload.weight_hg,
        "is_demo": payload.is_demo,
    }
    try:
        created = await pokemon_repo.create_manual_pokemon(session, record)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await pokemon_repo.log_admin_op(
        session,
        action="pokemon.create",
        target=f"#{payload.dex_number}",
        detail=f"手动新增 {payload.name_en}",
    )
    return _to_detail(created)


@router.get(
    "/ops",
    response_model=AdminOpLogResponse,
    summary="后台操作日志",
)
async def read_op_logs(
    session: DbSession, limit: int = Query(default=50, ge=1, le=200)
) -> AdminOpLogResponse:
    logs = await pokemon_repo.list_admin_ops(session, limit=limit)
    return AdminOpLogResponse(
        items=[
            AdminOpLogEntry(
                id=log.id,
                action=log.action,
                target=log.target,
                detail=log.detail,
                operator=log.operator,
                created_at=log.created_at.isoformat() if log.created_at else "",
            )
            for log in logs
        ]
    )


def _edit_to_fields(edit: AdminPokemonEdit) -> dict:
    """把请求模型转成仓储接受的字段（JSON 字段序列化）。"""
    fields: dict = {}
    if edit.name_en is not None:
        fields["name_en"] = edit.name_en
    if edit.name_zh is not None:
        fields["name_zh"] = edit.name_zh
    if edit.types is not None:
        fields["types_json"] = json.dumps(edit.types, ensure_ascii=False)
    if edit.stats is not None:
        fields["stats_json"] = json.dumps(edit.stats, ensure_ascii=False)
    if edit.abilities is not None:
        fields["abilities_json"] = json.dumps(
            [a.model_dump() for a in edit.abilities], ensure_ascii=False
        )
    if edit.evolution is not None:
        fields["evolution_json"] = json.dumps(edit.evolution, ensure_ascii=False)
    if edit.generation_introduced is not None:
        fields["generation_introduced"] = edit.generation_introduced
    if edit.height_dm is not None:
        fields["height_dm"] = edit.height_dm
    if edit.weight_hg is not None:
        fields["weight_hg"] = edit.weight_hg
    if edit.is_demo is not None:
        fields["is_demo"] = edit.is_demo
    return fields


def _validate_types(types: list[str]) -> None:
    """属性值合法性来自规范克制表 —— 编辑入口同样不接受任意字符串。"""
    try:
        document = load_type_chart()
    except TypeChartUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    for type_name in types:
        if type_name not in document.zh_lookup:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"属性 {type_name!r} 不存在（合法值：{sorted(document.zh_lookup)}）",
            )


def _to_detail(pokemon) -> PokemonDetail:
    fields = pokemon_repo.parse_json_fields(pokemon)
    return PokemonDetail(
        dex_number=fields["dex_number"],
        name_en=fields["name_en"],
        name_zh=fields["name_zh"],
        types=fields["types"],
        stats=fields["stats"],
        abilities=fields["abilities"],
        evolution=fields["evolution"],
        generation_introduced=fields["generation_introduced"],
        height_dm=fields["height_dm"],
        weight_hg=fields["weight_hg"],
        source=fields["source"],
        source_label=PokemonDetail.source_label_of(fields["source"]),
        is_demo=fields["is_demo"],
        synced_at=fields["synced_at"],
    )
