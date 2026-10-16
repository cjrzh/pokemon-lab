"""图鉴公开路由（只读浏览，无任何编辑入口 —— 编辑在 /admin/*）。

参数校验由 Pydantic；查询拼装在仓储；路由只做「取数 → 组响应」。
属性筛选的合法值来自规范克制表（18 属性），不接收任意字符串。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.repositories import pokemon_repo
from app.repositories.pokemon_repo import PokemonListQuery
from app.schemas.pokemon import (
    PokemonAbility,
    PokemonDetail,
    PokemonListMeta,
    PokemonListResponse,
    PokemonSummary,
)
from app.services.type_chart_service import TypeChartUnavailable, load_type_chart

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


@router.get(
    "",
    response_model=PokemonListResponse,
    summary="图鉴列表",
    description="分页 + 搜索（中英文名）+ 属性/世代筛选。按图鉴编号升序。",
)
async def list_pokemon(
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=64, description="名称子串，中英文皆可"),
    type: str | None = Query(default=None, description="属性英文键，如 fire"),
    generation: int | None = Query(default=None, ge=1, le=9),
) -> PokemonListResponse:
    if type is not None:
        _validate_type(type)

    result = await pokemon_repo.list_pokemon(
        session,
        PokemonListQuery(
            search=q, type_filter=type, generation=generation, page=page, page_size=page_size
        ),
    )

    items = [
        PokemonSummary(
            dex_number=p.dex_number,
            name_en=p.name_en,
            name_zh=p.name_zh,
            types=_load_types(p),
            is_demo=p.is_demo,
        )
        for p in result.items
    ]
    return PokemonListResponse(
        items=items,
        meta=PokemonListMeta(
            page=result.page,
            page_size=result.page_size,
            total=result.total,
            total_pages=result.total_pages,
        ),
    )


@router.get(
    "/{dex_number}",
    response_model=PokemonDetail,
    summary="图鉴详情",
    description="属性、种族值、特性、进化链与数据来源标注。编号不存在时返回 404。",
)
async def get_pokemon_detail(session: DbSession, dex_number: int) -> PokemonDetail:
    if dex_number < 1 or dex_number > 10000:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图鉴编号超出范围")

    pokemon = await pokemon_repo.get_by_dex_number(session, dex_number)
    if pokemon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"图鉴编号 {dex_number} 尚未同步或不存在（当前范围见 /pokemon 列表）",
        )

    fields = pokemon_repo.parse_json_fields(pokemon)
    return PokemonDetail(
        dex_number=fields["dex_number"],
        name_en=fields["name_en"],
        name_zh=fields["name_zh"],
        types=fields["types"],
        stats=fields["stats"],
        abilities=[PokemonAbility(**a) for a in fields["abilities"]],
        evolution=fields["evolution"],
        generation_introduced=fields["generation_introduced"],
        height_dm=fields["height_dm"],
        weight_hg=fields["weight_hg"],
        source=fields["source"],
        source_label=PokemonDetail.source_label_of(fields["source"]),
        is_demo=fields["is_demo"],
        synced_at=fields["synced_at"],
    )


def _validate_type(type_name: str) -> None:
    """属性筛选合法值来自规范克制表；表缺失是配置问题，如实 503。"""
    try:
        document = load_type_chart()
    except TypeChartUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if type_name not in document.zh_lookup:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"属性 {type_name!r} 不存在（合法值：{sorted(document.zh_lookup)}）",
        )


def _load_types(pokemon) -> list[str]:
    try:
        return json.loads(pokemon.types_json)
    except (json.JSONDecodeError, TypeError):
        return []
