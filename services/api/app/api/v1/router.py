"""v1 路由聚合。

新增模块时在这里挂载即可，`main.py` 不需要改动。
注意顺序：静态路径必须注册在参数化路径之前，否则会被提前捕获。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import abilities, admin, doubles, health, moves, pokemon, types, usage_ranking

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(types.router)
api_router.include_router(pokemon.router)
# 双打辅助挂在 /pokemon/{dex}/doubles 下，路径更长，不会与 /pokemon/{dex} 冲突
api_router.include_router(doubles.router)
api_router.include_router(abilities.router)
api_router.include_router(moves.router)
api_router.include_router(usage_ranking.router)
api_router.include_router(admin.router)
