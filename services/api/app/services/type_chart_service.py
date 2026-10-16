"""属性克制数据装配：从 `data/type-chart.json` 加载并校验。

加载时机是进程内惰性单例（图鉴、克制接口、健康检查都会用到），
而不是每个请求读一次磁盘 —— 但提供 `reset_type_chart_cache()` 让测试能换数据。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass

from app.core.config import get_settings


class TypeChartUnavailable(RuntimeError):
    """规范克制数据缺失或损坏。路由层转 503 并提示先运行生成脚本。"""


@dataclass(frozen=True)
class TypeChartDocument:
    """解析后的克制表文档。"""

    chart: dict[str, dict[str, float]]
    types: tuple[tuple[str, str], ...]  # (name, zh)
    label: str
    generation_min: int
    generation_max: int

    @property
    def type_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.types)

    @property
    def zh_lookup(self) -> Mapping[str, str]:
        return dict(self.types)


_lock = threading.Lock()
_cache: TypeChartDocument | None = None


def load_type_chart() -> TypeChartDocument:
    """加载并校验规范克制表；进程内缓存。"""
    global _cache
    with _lock:
        if _cache is not None:
            return _cache

        settings = get_settings()
        path = settings.data_dir / "type-chart.json"
        if not path.exists():
            raise TypeChartUnavailable(
                f"规范克制表不存在：{path}。请先运行 scripts/gen_type_chart.py"
            )

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            types = tuple((t["name"], t["zh"]) for t in payload["types"])
            chart = {
                attack: {defense: float(m) for defense, m in row.items()}
                for attack, row in payload["chart"].items()
            }
            document = TypeChartDocument(
                chart=chart,
                types=types,
                label=payload["label"],
                generation_min=payload["generation"]["min"],
                generation_max=payload["generation"]["max"],
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise TypeChartUnavailable(f"规范克制表损坏（{path}）：{exc}") from exc

        _validate_document(document)
        _cache = document
        return document


def _validate_document(document: TypeChartDocument) -> None:
    """结构与自洽校验：18 属性、图表键一致、倍率合法。"""
    names = set(document.type_names)
    if len(names) != 18:
        raise TypeChartUnavailable(f"属性数量异常：{len(names)}，应为 18")
    if set(document.chart) != names:
        missing = names - set(document.chart)
        extra = set(document.chart) - names
        raise TypeChartUnavailable(f"图表键与属性列表不一致（缺 {missing}，多 {extra}）")
    for attack, row in document.chart.items():
        for defense, multiplier in row.items():
            if defense not in names:
                raise TypeChartUnavailable(f"{attack} 行含未知防守属性 {defense!r}")
            if multiplier not in (0.0, 0.25, 0.5, 2.0, 4.0):
                raise TypeChartUnavailable(
                    f"{attack}→{defense} 倍率异常：{multiplier}（合法值 0/0.25/0.5/2/4）"
                )


def reset_type_chart_cache() -> None:
    """仅供测试：清空进程内缓存，让下一次 load 重新读文件。"""
    global _cache
    with _lock:
        _cache = None
