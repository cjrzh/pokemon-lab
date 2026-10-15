"""日志配置。

刻意保持极简：MVP 阶段不需要结构化日志管道，只要保证「有统一格式、可调级别」。
"""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int | str = logging.INFO) -> None:
    """配置根日志器。重复调用不会叠加 handler。"""
    logging.basicConfig(level=level, format=_LOG_FORMAT, datefmt=_DATE_FORMAT)
