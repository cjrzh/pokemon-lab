"""ORM 模型。

P0 只包含一张元数据表；图鉴缓存、收藏、笔记、考试等表在 P1–P5 逐步加入。
每张涉及竞技规则的表都必须带 `generation_id` / `ruleset_id` 维度 —— 见 docs/ARCHITECTURE.md。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: 当前数据库结构代次。正式引入迁移工具前，用它判断本地库是否落后于代码。
SCHEMA_VERSION = "0001_p0_skeleton"


class SchemaMeta(Base):
    """键值型元数据表：记录结构版本、初始化时间等运行期信息。"""

    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"SchemaMeta(key={self.key!r}, value={self.value!r})"
