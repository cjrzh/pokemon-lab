"""对战使用率排行（公开只读）。

`GET /usage-ranking?format=sv`：返回四个格式的标签元数据，以及所选格式的
排行榜（排名、使用率、图鉴信息、前几项常用配装）。数据与图鉴详情页的
「双打对战辅助」同源（Smogon 月度统计快照），页面必须展示月份与等级线。

未导入数据的格式照样出现在 `formats` 里，`entries=0` —— 前端据此显示空态，
而不是把「没有数据」误报成接口错误。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.domain.doubles_formats import FORMAT_BY_KEY, FORMAT_KEYS, usage_url
from app.schemas.usage import (
    UsageFormatInfo,
    UsageRankingItem,
    UsageRankingMeta,
    UsageRankingResponse,
)
from app.services import doubles_service

router = APIRouter(prefix="/usage-ranking", tags=["doubles"])

DEFAULT_FORMAT = "bdsp"


@router.get(
    "",
    response_model=UsageRankingResponse,
    summary="对战使用率排行",
    description=(
        "按双打格式返回使用率排行榜：排名、使用率、图鉴编号 / 中文名 / 属性 / 立绘，"
        "以及每个条目排名最高的特性、道具、招式与配点。支持按名称或图鉴编号搜索。"
    ),
)
async def get_usage_ranking(
    session: DbSession,
    format: str = Query(default=DEFAULT_FORMAT, description=f"格式：{', '.join(FORMAT_KEYS)}"),
    q: str | None = Query(default=None, max_length=64, description="中文名 / 英文名 / 编号"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> UsageRankingResponse:
    if format not in FORMAT_BY_KEY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"format 只接受 {FORMAT_KEYS}",
        )

    formats = await doubles_service.list_formats(session)
    counts = await doubles_service.format_entry_counts(session)
    present = {fmt.key for fmt in formats}

    # 四个格式都要出现：未导入的使用仓库定义的元数据补位（entries=0、imported=false）
    format_infos = []
    for key in FORMAT_KEYS:
        fmt = FORMAT_BY_KEY[key]
        imported = key in present
        format_infos.append(
            UsageFormatInfo(
                key=key,
                label=fmt.label,
                short_label=fmt.short_label,
                game=fmt.game,
                ruleset=fmt.ruleset,
                month=fmt.month,
                cutoff=fmt.cutoff,
                points_kind=fmt.points_kind,  # type: ignore[arg-type]
                battles=next((row.battles for row in formats if row.key == key), 0),
                note=fmt.note,
                source_url=usage_url(fmt),
                entries=counts.get(key, 0),
                imported=imported,
            )
        )

    current = next((row for row in formats if row.key == format), None)
    items: list[dict] = []
    total = 0
    if current is not None:
        items, total = await doubles_service.list_ranking(
            session, current, search=q, page=page, page_size=page_size
        )

    effective_page = max(1, page)
    effective_size = max(1, min(200, page_size))
    return UsageRankingResponse(
        formats=format_infos,
        format_key=format,
        items=[UsageRankingItem(**item) for item in items],
        meta=UsageRankingMeta(
            page=effective_page,
            page_size=effective_size,
            total=total,
            total_pages=max(1, -(-total // effective_size)),
        ),
        has_data=bool(present),
    )
