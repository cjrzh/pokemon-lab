"""属性克制接口的请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

TypeMultiplier = float


class TypeInfo(BaseModel):
    """单个属性的名称（英文键 + 中文名）。"""

    name: str = Field(examples=["fire"])
    zh: str = Field(examples=["火"])


class TypeChartMeta(BaseModel):
    """克制表元信息（数据来源与适用世代）。"""

    label: str
    generation_min: int
    generation_max: int
    note: str = Field(description="世代适用范围说明，如实标注 MVP 边界")


class TypeChartResponse(BaseModel):
    """`GET /types`：属性列表 + 稀疏克制表 + 元信息。"""

    types: list[TypeInfo]
    chart: dict[str, dict[str, float]] = Field(description="attack → {defense: 倍率}，缺省视为 1.0")
    meta: TypeChartMeta


class EvaluateRequest(BaseModel):
    """`POST /types/evaluate` 请求体。"""

    attack: str = Field(examples=["fire"], description="进攻属性英文键")
    defense: list[str] = Field(
        min_length=1,
        max_length=2,
        examples=[["water", "flying"]],
        description="防守属性英文键，1–2 个",
    )


class EvaluateResponse(BaseModel):
    """倍率计算结果。"""

    attack: str
    defense: list[str]
    multiplier: TypeMultiplier
    label: str = Field(description="人可读倍率标签，如 2×、1/2×、无效（免疫）")


class ReverseRequest(BaseModel):
    """`POST /types/reverse`（谁克我）请求体。"""

    defense: list[str] = Field(
        min_length=1,
        max_length=2,
        examples=[["water", "ground"]],
        description="防守属性英文键，1–2 个",
    )


class ReverseEntry(BaseModel):
    """反查结果中的单个进攻属性。"""

    attack: str
    zh: str
    multiplier: float


class ReverseResponse(BaseModel):
    """反查结果：按倍率降序、同倍率按属性序排列。"""

    defense: list[str]
    entries: list[ReverseEntry]
