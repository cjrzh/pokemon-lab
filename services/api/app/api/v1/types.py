"""属性克制路由。

`/types`：返回完整克制表（供前端离线即时计算）。
`/types/evaluate`：计算单个进攻属性对一组防守属性的倍率（前后端可交叉校验）。
`/types/reverse`：反向查询「谁克我」，按倍率降序。

业务规则不写在这里：参数校验由 Pydantic，计算由 domain/type_engine，数据装配由
services/type_chart_service。路由只做「取数据 → 调引擎 → 组响应」。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.domain.type_engine import evaluate, format_multiplier, reverse
from app.schemas.types import (
    EvaluateRequest,
    EvaluateResponse,
    ReverseEntry,
    ReverseRequest,
    ReverseResponse,
    TypeChartMeta,
    TypeChartResponse,
    TypeInfo,
)
from app.services.type_chart_service import TypeChartUnavailable, load_type_chart

router = APIRouter(prefix="/types", tags=["types"])


@router.get(
    "",
    response_model=TypeChartResponse,
    summary="属性克制表",
    description="返回 18 属性与稀疏克制表，供前端离线即时计算；并附数据来源与适用世代。",
)
async def get_type_chart() -> TypeChartResponse:
    try:
        document = load_type_chart()
    except TypeChartUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return TypeChartResponse(
        types=[TypeInfo(name=name, zh=zh) for name, zh in document.types],
        chart=document.chart,
        meta=TypeChartMeta(
            label=document.label,
            generation_min=document.generation_min,
            generation_max=document.generation_max,
            note=(
                f"第 {document.generation_min} 代起规则一致；"
                "Gen 1–5 差异后续逐代补齐，补齐前不宣称支持"
            ),
        ),
    )


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    summary="计算属性倍率",
    description="给定进攻属性与 1–2 个防守属性，返回最终倍率（双属性相乘，含免疫与 4 倍克制）。",
)
async def evaluate_types(request: EvaluateRequest) -> EvaluateResponse:
    try:
        document = load_type_chart()
    except TypeChartUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    _validate_type(request.attack, document, role="进攻")
    for defense_type in request.defense:
        _validate_type(defense_type, document, role="防守")

    multiplier = evaluate(request.attack, request.defense, document.chart)
    return EvaluateResponse(
        attack=request.attack,
        defense=request.defense,
        multiplier=multiplier,
        label=format_multiplier(multiplier),
    )


@router.post(
    "/reverse",
    response_model=ReverseResponse,
    summary="反向查询：谁克我",
    description="给定 1–2 个防守属性，列出所有进攻属性及其倍率（仅非中性项），按倍率降序。",
)
async def reverse_types(request: ReverseRequest) -> ReverseResponse:
    try:
        document = load_type_chart()
    except TypeChartUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    for defense_type in request.defense:
        _validate_type(defense_type, document, role="防守")

    raw = reverse(request.defense, document.chart, include_neutral=False)
    zh = document.zh_lookup

    # 倍率降序；同倍率按属性在表中的序号，保证输出稳定可复现
    order = {name: i for i, (name, _) in enumerate(document.types)}
    entries = sorted(
        (
            ReverseEntry(attack=attack, zh=zh[attack], multiplier=multiplier)
            for attack, multiplier in raw.items()
        ),
        key=lambda e: (-e.multiplier, order[e.attack]),
    )

    return ReverseResponse(defense=request.defense, entries=entries)


def _validate_type(type_name: str, document, *, role: str) -> None:
    """属性键必须在表中，否则 422 —— 调用方笔误不该返回 503。"""
    if type_name not in document.zh_lookup:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{role}属性 {type_name!r} 不存在（合法值：{sorted(document.zh_lookup)}）",
        )
