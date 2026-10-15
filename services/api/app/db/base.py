"""ORM 声明基类。"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。

    保持空实现：表名、字段与索引都由各自模型显式声明，不使用隐式命名约定，
    避免日后重命名模型时表名跟着漂移。
    """
