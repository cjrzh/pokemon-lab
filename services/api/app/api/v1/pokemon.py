"""图鉴公开路由（只读浏览，无任何编辑入口 —— 编辑在 /admin/*）。

参数校验由 Pydantic；查询拼装在仓储；路由只做「取数 → 组响应」。
属性筛选的合法值来自规范克制表（18 属性），不接收任意字符串。

图片地址约定：
  - 有本地缓存（`artwork_path`）时返回 `/media/{path}`，由本服务静态托管，离线可用；
  - 没有缓存时返回 pokemon.com 的远程立绘地址；
  - `artwork_fallback_url` 是 PokéAPI official-artwork（经图片代理），供前端 onError 兜底。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.domain.pokemon_parser import (
    DAMAGE_CLASS_ZH,
    LEARN_METHOD_ORDER,
    LEARN_METHOD_ZH,
    VERSION_GROUP_ORDER,
)
from app.repositories import pokemon_repo
from app.repositories.pokemon_repo import PokemonListQuery
from app.schemas.pokemon import (
    PokemonAbility,
    PokemonDetail,
    PokemonListAbility,
    PokemonListMeta,
    PokemonListResponse,
    PokemonMove,
    PokemonMoveMethod,
    PokemonMoves,
    PokemonMoveVersionGroup,
    PokemonNeighbor,
    PokemonSummary,
)
from app.services.sprite_service import sprite_media_url
from app.services.type_chart_service import TypeChartUnavailable, load_type_chart

router = APIRouter(prefix="/pokemon", tags=["pokemon"])

#: 静态图片挂载前缀（main.py 挂载 media 目录到这里）。
MEDIA_URL_PREFIX = "/media"


@router.get(
    "",
    response_model=PokemonListResponse,
    summary="图鉴列表",
    description=(
        "分页 + 搜索（中英文名）+ 属性/世代筛选。"
        "排序：图鉴编号升序（默认）/ 降序，或种族值合计升序 / 降序；"
        "排序作用于筛选后的结果集。"
    ),
)
async def list_pokemon(
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    q: str | None = Query(default=None, max_length=64, description="名称子串，中英文皆可"),
    type: str | None = Query(default=None, description="属性英文键，如 fire"),
    generation: int | None = Query(default=None, ge=1, le=9),
    sort: str = Query(
        default="dex",
        description="排序：dex（编号升序）/ dex_desc / total_stats（种族值降序）/ total_stats_asc",
    ),
) -> PokemonListResponse:
    if type is not None:
        _validate_type(type)
    if sort not in pokemon_repo.POKEMON_SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"sort 只接受 {pokemon_repo.POKEMON_SORT_FIELDS}",
        )

    result = await pokemon_repo.list_pokemon(
        session,
        PokemonListQuery(
            search=q,
            type_filter=type,
            generation=generation,
            sort=sort,
            page=page,
            page_size=page_size,
        ),
    )

    tier_map = await pokemon_repo.get_ability_tier_map(session)
    items = []
    for p in result.items:
        fields = pokemon_repo.parse_json_fields(p)
        items.append(
            PokemonSummary(
                dex_number=p.dex_number,
                name_en=p.name_en,
                name_zh=p.name_zh,
                name_ja=p.name_ja,
                types=fields["types"],
                stats=fields["stats"],
                total_stats=fields["total_stats"],
                artwork_url=_artwork_url(fields),
                artwork_fallback_url=fields["sprite_url"],
                sprite_url=sprite_media_url(p.dex_number, fields.get("sprite_path")),
                is_legendary=p.is_legendary,
                is_mythical=p.is_mythical,
                abilities=[
                    PokemonListAbility(
                        name=ability["name"],
                        zh=ability.get("zh"),
                        is_hidden=bool(ability.get("is_hidden")),
                        is_s_tier=tier_map.get(ability["name"]) == "s",
                    )
                    for ability in fields["abilities"]
                ],
                is_demo=p.is_demo,
            )
        )
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
    description="立绘、分类、图鉴描述、属性、种族值、特性、进化链与升级招式。",
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

    prev, nxt = await pokemon_repo.get_neighbors(session, dex_number)
    return await build_detail(session, pokemon, prev=prev, next_pokemon=nxt)


async def build_detail(
    session: DbSession, pokemon, *, prev=None, next_pokemon=None
) -> PokemonDetail:
    """公开路由与 admin 路由共用的详情组装。

    进化链上游只给英文 slug，这里按已同步记录补中文名；未同步的进化后形态
    保持英文名，不虚构翻译。
    """
    fields = pokemon_repo.parse_json_fields(pokemon)

    evolution = fields["evolution"]
    if isinstance(evolution, dict) and isinstance(evolution.get("chain"), dict):
        chain_dex: list[int] = []
        _collect_chain_dex(evolution["chain"], chain_dex)
        zh_lookup = await pokemon_repo.get_zh_names(session, chain_dex)
        evolution = {
            **evolution,
            "chain": _enrich_chain(evolution["chain"], zh_lookup),
        }

    moves = await _build_moves(session, fields["moves"])
    tier_map = await pokemon_repo.get_ability_tier_map(session)

    return PokemonDetail(
        dex_number=fields["dex_number"],
        name_en=fields["name_en"],
        name_zh=fields["name_zh"],
        name_ja=fields["name_ja"],
        types=fields["types"],
        stats=fields["stats"],
        total_stats=fields["total_stats"],
        abilities=_abilities_with_tier(fields["abilities"], tier_map),
        evolution=evolution,
        moves=moves,
        genus_zh=fields["genus_zh"],
        genus_en=fields["genus_en"],
        flavor_zh=fields["flavor_zh"],
        flavor_en=fields["flavor_en"],
        flavor_zh_source=fields["flavor_zh_source"],
        genus_zh_source=fields["genus_zh_source"],
        artwork_url=_artwork_url(fields),
        artwork_fallback_url=fields["sprite_url"],
        sprite_url=sprite_media_url(fields["dex_number"], fields.get("sprite_path")),
        is_legendary=fields["is_legendary"],
        is_mythical=fields["is_mythical"],
        is_baby=fields["is_baby"],
        gender_rate=fields["gender_rate"],
        capture_rate=fields["capture_rate"],
        base_happiness=fields["base_happiness"],
        hatch_counter=fields["hatch_counter"],
        growth_rate=fields["growth_rate"],
        habitat=fields["habitat"],
        color=fields["color"],
        shape=fields["shape"],
        egg_groups=fields["egg_groups"],
        generation_introduced=fields["generation_introduced"],
        height_dm=fields["height_dm"],
        weight_hg=fields["weight_hg"],
        prev=_neighbor(prev),
        next=_neighbor(next_pokemon),
        source=fields["source"],
        source_label=PokemonDetail.source_label_of(fields["source"]),
        is_demo=fields["is_demo"],
        synced_at=fields["synced_at"],
    )


async def _build_moves(session, payload) -> PokemonMoves:
    """把 moves_json 与共享的 move_ref 数值合并成响应结构。

    moves_json 只存「版本组 → 学习方式 → 招式名/等级」；属性、威力、PP、说明
    来自 move_ref 表（缺失时字段为 None，前端显示「—」，不编造数值）。
    """
    if not isinstance(payload, dict) or not payload.get("version_groups"):
        return PokemonMoves()

    groups: dict = payload["version_groups"]
    names = {
        move["name"]
        for group in groups.values()
        for method in group.get("methods", {}).values()
        for move in method
    }
    refs = await pokemon_repo.get_move_refs(session, list(names))

    def build_move(entry: dict) -> PokemonMove:
        ref = refs.get(entry["name"], {})
        detail = ref.get("damage_class")
        return PokemonMove(
            name=entry["name"],
            zh=ref.get("zh"),
            level=entry.get("level", 0),
            type=ref.get("type"),
            damage_class=detail,
            damage_class_zh=ref.get("damage_class_zh")
            or DAMAGE_CLASS_ZH.get(detail or ""),
            power=ref.get("power"),
            accuracy=ref.get("accuracy"),
            pp=ref.get("pp"),
            description_zh=ref.get("description_zh"),
        )

    def group_rank(key: str) -> int:
        try:
            return VERSION_GROUP_ORDER.index(key)
        except ValueError:
            return len(VERSION_GROUP_ORDER)

    version_groups = []
    # 按「新作品在前」展示；未收录的版本组排在最后（仍完整保留）
    for group_key, group in sorted(groups.items(), key=lambda item: group_rank(item[0])):
        methods = group.get("methods", {})
        ordered = sorted(
            methods.items(),
            key=lambda item: (
                LEARN_METHOD_ORDER.index(item[0])
                if item[0] in LEARN_METHOD_ORDER
                else len(LEARN_METHOD_ORDER),
                item[0],
            ),
        )
        version_groups.append(
            PokemonMoveVersionGroup(
                version_group=group_key,
                label=group.get("label", group_key),
                methods=[
                    PokemonMoveMethod(
                        method=method,
                        label=LEARN_METHOD_ZH.get(method, method),
                        moves=[build_move(move) for move in entries],
                    )
                    for method, entries in ordered
                ],
            )
        )

    return PokemonMoves(
        default_version_group=payload.get("default_version_group"),
        version_groups=version_groups,
    )


def _abilities_with_tier(abilities: list[dict], tier_map: dict[str, str]) -> list[PokemonAbility]:
    """给特性附上 S 级标记（数据来自 ability 参考表）。"""
    result = []
    for ability in abilities:
        tier = tier_map.get(ability["name"], "normal")
        result.append(
            PokemonAbility(
                **ability,
                tier=tier,
                is_s_tier=tier == "s",
            )
        )
    return result


def _artwork_url(fields: dict) -> str | None:
    """本地缓存优先；没有缓存时用远程立绘。"""
    if fields.get("artwork_path"):
        return f"{MEDIA_URL_PREFIX}/{fields['artwork_path']}"
    return fields.get("artwork_url_remote")


def _neighbor(pokemon) -> PokemonNeighbor | None:
    if pokemon is None:
        return None
    return PokemonNeighbor(
        dex_number=pokemon.dex_number,
        name_zh=pokemon.name_zh,
        name_en=pokemon.name_en,
    )


def _collect_chain_dex(node: dict, out: list[int]) -> None:
    dex = node.get("dex")
    if isinstance(dex, int):
        out.append(dex)
    for child in node.get("evolves_to", []) or []:
        if isinstance(child, dict):
            _collect_chain_dex(child, out)


def _enrich_chain(node: dict, zh_lookup: dict[int, str | None]) -> dict:
    dex = node.get("dex")
    return {
        "name": str(node.get("name", "")),
        "dex": int(dex) if isinstance(dex, int) else 0,
        "zh": zh_lookup.get(dex) if isinstance(dex, int) else None,
        "detail": node.get("detail"),
        "evolves_to": [
            _enrich_chain(child, zh_lookup)
            for child in node.get("evolves_to", []) or []
            if isinstance(child, dict)
        ],
    }


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
