"""ORM 模型。

P0 只有元数据表；P1 加入 PokéAPI 落盘缓存与世代/规则版本参考数据；
图鉴、收藏、笔记、考试等表在 P2–P5 逐步加入。
每张涉及竞技规则的表都必须带 `generation_id` / `ruleset_id` 维度 —— 见 docs/ARCHITECTURE.md。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: 当前数据库结构代次。正式引入迁移工具前，用它判断本地库是否落后于代码。
SCHEMA_VERSION = "0002_p1_type_core"


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


class ApiCache(Base):
    """PokéAPI 落盘缓存（ARCHITECTURE.md §8：TTL 默认 7 天，命中标 X-Cache: hit）。

    `payload` 存原始 JSON 文本；`fetched_at` 与 `expires_at`（Unix 时间戳，秒）
    支撑「上游失败但本地有旧缓存 → 返回旧数据并标 stale」的降级路径。
    """

    __tablename__ = "api_cache"

    cache_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"ApiCache(cache_key={self.cache_key!r}, expires_at={self.expires_at!r})"


class Generation(Base):
    """世代（参考数据，由种子脚本写入，P1 交付）。"""

    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    released_at: Mapped[str | None] = mapped_column(String(16), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Generation(id={self.id!r}, label={self.label!r})"


class Ruleset(Base):
    """规则版本（参考数据，如 gen9-standard）。所有个人数据都可按它区分。"""

    __tablename__ = "rulesets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Ruleset(id={self.id!r}, label={self.label!r})"
