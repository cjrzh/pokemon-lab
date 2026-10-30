"""双打对战辅助公开路由。

`GET /pokemon/{dex_number}/doubles`：一次返回四个格式（冠军 / 朱紫 / 剑盾 / BDSP）
的使用率、主流配点、道具、特性、招式与常见队友。没有数据的格式也会出现，
`profiles` 为空数组 —— 前端可以据此区分「该格式没有这只宝可梦」与「接口失败」。

数据来自 Smogon 月度统计文本（见 scripts/fetch_doubles_stats.py），
不是实时对局数据；响应始终带统计月份与等级线。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.domain.doubles_formats import FORMAT_KEYS
from app.repositories import pokemon_repo
from app.schemas.doubles import (
    DoublesFormatBlock,
    DoublesProfile,
    DoublesResponse,
)
from app.services import doubles_service

router = APIRouter(prefix="/pokemon", tags=["doubles"])


@router.get(
    "/{dex_number}/doubles",
    response_model=DoublesResponse,
    summary="双打对战辅助",
    description=(
        "按固定四个格式返回 Smogon 公开使用率统计：排名、使用率、配点（性格 / EV 或能力点）、"
        "特性、道具、招式与常见队友。统计为历史快照，页面会展示月份与等级线。"
    ),
)
async def get_doubles(session: DbSession, dex_number: int) -> DoublesResponse:
    pokemon = await pokemon_repo.get_by_dex_number(session, dex_number)
    if pokemon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"图鉴编号 {dex_number} 不存在",
        )

    formats = await doubles_service.list_formats(session)
    if not formats:
        # 数据文件尚未导入：返回 200 + 空列表，让前端显示「尚未导入」而不是报错
        return DoublesResponse(dex_number=dex_number, formats=[], has_data=False)

    # 队友链接需要名称 → 图鉴编号的索引（与导入时同一套规则）
    name_rows = await pokemon_repo.get_name_rows(session)
    index = doubles_service.build_name_index(name_rows)

    stats = await doubles_service.get_all_stats_for_dex(session, dex_number)
    by_format: dict[str, list] = {}
    for stat in stats:
        by_format.setdefault(stat.format_key, []).append(stat)

    # 招式属性：批量查出所有出现过的招式，供前端的属性徽章使用
    move_slugs: set[str] = set()
    item_slugs: set[str] = set()
    for stat in stats:
        move_slugs.update(slug for slug, _ in doubles_service.parse_json(stat.moves_json))
        item_slugs.update(slug for slug, _ in doubles_service.parse_json(stat.items_json))
    move_refs = await pokemon_repo.get_move_refs(session, sorted(move_slugs))
    move_types = {slug: ref["type"] for slug, ref in move_refs.items() if ref.get("type")}
    # 道具图标：同样一次批量查 item_ref，避免每个形态各查一次
    item_icons = doubles_service.item_icon_lookup(
        await doubles_service.load_item_rows(session, item_slugs)
    )
    # 队友名称：只查当前宝可梦各格式里出现过的编号，避免全表加载
    teammate_dex: set[int] = set()
    for stat in stats:
        for name, _ in doubles_service.parse_json(stat.teammates_json):
            resolved = index.resolve(name)
            if resolved is not None:
                teammate_dex.add(resolved)
    dex_names = await pokemon_repo.get_zh_names(session, sorted(teammate_dex))

    blocks: list[DoublesFormatBlock] = []
    order = {key: position for position, key in enumerate(FORMAT_KEYS)}
    for fmt in sorted(formats, key=lambda item: order.get(item.key, len(order))):
        profiles = [
            DoublesProfile(
                **await doubles_service.profile_payload(
                    session, stat, fmt, index, dex_names, move_types, item_icons
                )
            )
            for stat in sorted(
                by_format.get(fmt.key, []),
                key=lambda stat: (stat.usage is None, -(stat.usage or 0), stat.showdown_name),
            )
        ]
        blocks.append(
            DoublesFormatBlock(
                key=fmt.key,
                label=fmt.label,
                short_label=fmt.short_label,
                game=fmt.game,
                ruleset=fmt.ruleset,
                month=fmt.month,
                cutoff=fmt.cutoff,
                points_kind=fmt.points_kind,  # type: ignore[arg-type]
                battles=fmt.battles,
                trade_prefix=fmt.trade_prefix,
                default_level=fmt.default_level,
                note=fmt.note,
                source_url=fmt.source_url,
                imported_at=fmt.imported_at.isoformat() if fmt.imported_at else None,
                profiles=profiles,
            )
        )

    return DoublesResponse(
        dex_number=dex_number,
        formats=blocks,
        has_data=any(block.profiles for block in blocks),
    )
