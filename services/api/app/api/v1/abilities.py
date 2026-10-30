"""特性公开路由（只读）：列表、详情（含拥有者）、S 级标记。

特性与宝可梦是多对多关系，详情里的 `holders` 直接带宝可梦编号与中文名，
前端可链接到 `/dex/{dex_number}`。写操作（人工改评级）在 /admin/abilities。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.repositories import pokemon_repo
from app.schemas.abilities import (
    AbilityDetail,
    AbilityHolder,
    AbilityListMeta,
    AbilityListResponse,
    AbilitySummary,
)
from app.services.sprite_service import sprite_media_url

router = APIRouter(prefix="/abilities", tags=["abilities"])

#: 与公开图鉴详情一致：响应里直接给媒体路径，由前端补 origin。
MEDIA_URL_PREFIX = "/media"


@router.get(
    "",
    response_model=AbilityListResponse,
    summary="特性列表",
    description="支持按中/英文名与说明搜索、按 S 级筛选、分页；S 级排在前面。",
)
async def list_abilities(
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, max_length=64, description="特性名或说明关键词"),
    tier: str | None = Query(default=None, description="s：只看 S 级；normal：只看普通"),
) -> AbilityListResponse:
    if tier is not None and tier not in ("s", "normal"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="tier 只接受 s 或 normal",
        )

    items, total = await pokemon_repo.list_abilities(
        session, search=q, tier=tier, page=page, page_size=page_size
    )
    s_tier_total = len(await pokemon_repo.get_s_tier_names(session))

    return AbilityListResponse(
        items=[
            AbilitySummary(
                name=ability.name,
                zh=ability.zh,
                effect_zh=ability.effect_zh,
                tier=ability.tier,  # type: ignore[arg-type]
                rating_source=ability.rating_source,  # type: ignore[arg-type]
                rating_note=ability.rating_note,
                holder_count=await _holder_count(session, ability.name),
            )
            for ability in items
        ],
        meta=AbilityListMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=max(1, -(-total // page_size)),
            s_tier_total=s_tier_total,
        ),
    )


@router.get(
    "/{name}",
    response_model=AbilityDetail,
    summary="特性详情",
    description="特效说明、评级与理由，以及拥有该特性的宝可梦列表。",
)
async def get_ability(session: DbSession, name: str) -> AbilityDetail:
    ability = await pokemon_repo.get_ability(session, name)
    if ability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"特性 {name!r} 不存在（尚未同步或拼写有误）",
        )

    holders = await pokemon_repo.get_ability_holders(session, name)
    return AbilityDetail(
        name=ability.name,
        zh=ability.zh,
        effect_zh=ability.effect_zh,
        effect_en=ability.effect_en,
        tier=ability.tier,  # type: ignore[arg-type]
        rating_source=ability.rating_source,  # type: ignore[arg-type]
        rating_note=ability.rating_note,
        holders=[ability_holder(pokemon, name) for pokemon in holders],
    )


async def _holder_count(session, name: str) -> int:
    return len(await pokemon_repo.get_ability_holders(session, name))


def ability_holder(pokemon, ability_name: str) -> AbilityHolder:
    try:
        abilities = json.loads(pokemon.abilities_json or "[]")
    except (json.JSONDecodeError, TypeError):
        abilities = []
    is_hidden = any(
        a.get("name") == ability_name and a.get("is_hidden") for a in abilities
    )
    try:
        types = json.loads(pokemon.types_json or "[]")
    except (json.JSONDecodeError, TypeError):
        types = []
    return AbilityHolder(
        dex_number=pokemon.dex_number,
        name_zh=pokemon.name_zh,
        name_en=pokemon.name_en,
        types=types,
        is_hidden=is_hidden,
        is_legendary=pokemon.is_legendary,
        is_mythical=pokemon.is_mythical,
        sprite_url=sprite_media_url(pokemon.dex_number, pokemon.sprite_path),
    )
