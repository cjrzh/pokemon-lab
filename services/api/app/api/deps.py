"""共享依赖注入。

路由层只从这里取会话与身份，不直接触碰引擎与 SQL —— 这条边界让「换数据库」
或「换成真实账号体系」时改动面可控。

P0 阶段 `DbSession` / `OwnerKey` 还没有接口使用：收藏、笔记在 P4 接入，
考试在 P5 接入。先把入口定下来，避免那时各自发明一套。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db

#: 请求级数据库会话（自动提交 / 回滚）
DbSession = Annotated[AsyncSession, Depends(get_db)]

#: 匿名所有者标识对应的请求头名称，与前端 apps/web/src/lib/ownerKey.ts 保持一致
OWNER_KEY_HEADER = "X-Owner-Key"

#: 未带标识时使用的兜底身份
ANONYMOUS_OWNER = "anonymous"


async def get_owner_key(
    x_owner_key: Annotated[str | None, Header(alias=OWNER_KEY_HEADER)] = None,
) -> str:
    """解析匿名所有者标识。

    MVP 不做鉴权：该标识仅用于区分「不同浏览器上的个人数据」，不具备防伪造能力。
    接入真实账号体系时只需替换本函数。
    """
    if x_owner_key and x_owner_key.strip():
        return x_owner_key.strip()
    return ANONYMOUS_OWNER


OwnerKey = Annotated[str, Depends(get_owner_key)]
