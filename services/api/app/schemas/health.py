"""健康检查的响应模型。

字段刻意保持稳定：前端首页直接消费它，用于展示「后端 / 数据库 / 数据文件」三件事的真实状态。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["ok", "degraded", "error"]


class HealthCheck(BaseModel):
    """单项检查结果。"""

    name: str = Field(description="检查项名称，例如 database / datasets")
    status: CheckStatus = Field(description="该项状态")
    detail: str = Field(description="人类可读的补充说明，可直接展示给用户")


class HealthResponse(BaseModel):
    """整体健康状态。任一检查项非 ok 时整体为 degraded。"""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    generated_at: datetime
    checks: list[HealthCheck]
