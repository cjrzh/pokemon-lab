"""共享依赖注入。

路由层只从这里取会话，不直接触碰引擎与 SQL —— 这条边界让「换数据库」
改动面可控。

历史上这里还有匿名身份（`X-Owner-Key` 头）的解析，用于按浏览器隔离个人数据。
当前项目为**个人自用**，不做浏览器隔离：所有队伍对所有访问者可见（本地单实例）。
如果将来加登录认证，把身份依赖重新加回这里即可，改动集中在这一处。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db

#: 请求级数据库会话（自动提交 / 回滚）
DbSession = Annotated[AsyncSession, Depends(get_db)]
