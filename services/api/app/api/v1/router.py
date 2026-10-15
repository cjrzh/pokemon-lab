"""v1 路由聚合。

新增模块时在这里挂载即可，`main.py` 不需要改动。
注意顺序：静态路径必须注册在参数化路径之前，否则会被提前捕获。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
