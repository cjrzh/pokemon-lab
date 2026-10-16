"""属性克制引擎（纯函数）。

本模块只回答一个问题：给定进攻属性与 1–2 个防守属性，倍率是多少。

硬性约束（继承自 domain/__init__.py）：
  - 不做 IO，不读文件。克制表由调用方以参数传入。
  - 不用随机与当前时间。
  - 不依赖 FastAPI / SQLAlchemy。

这样 pytest 能直接导入、Vitest 能镜像同一份逻辑，且两端共用同一份测试向量。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

#: 克制表的类型：attack -> {defense: 倍率}，缺省视为 1.0。
TypeChart = Mapping[str, Mapping[str, float]]

#: 倍率允许的离散值（受浮点误差容忍 ±1e-9）。
#: 0 = 免疫，0.25/0.5 = 抗性，1 = 中性，2/4 = 克制。
NEUTRAL = 1.0

_EPSILON = 1e-9


def _is_zero(value: float) -> bool:
    return abs(value) < _EPSILON


def _equals(a: float, b: float) -> bool:
    return abs(a - b) < _EPSILON


def evaluate(attack: str, defense: Sequence[str], chart: TypeChart) -> float:
    """计算单个进攻属性对一组防守属性的最终倍率。

    规则（Gen 6+，适用至今）：
      - 单属性倍率查表，缺省 1.0。
      - 多防守属性时各倍率相乘。
      - 任一为 0（免疫）则整体为 0 —— 这是乘法自然结果，无需特判，
        但浮点累积误差在极端路径上可能产生非零极小值，因此用 epsilon 归零。

    Args:
        attack: 进攻属性名（必须在 chart 中，否则抛 KeyError——克制表不含的属性是配置错误）。
        defense: 防守属性列表，长度 1–2（世代规则允许的双属性上限）。
        chart: 克制表。

    Returns:
        倍率：0 / 0.25 / 0.5 / 1 / 2 / 4 之一。
    """
    row = _attack_row(attack, chart)
    multiplier = 1.0
    for defense_type in defense:
        multiplier *= row.get(defense_type, NEUTRAL)
    return 0.0 if _is_zero(multiplier) else multiplier


def reverse(
    defense: Sequence[str], chart: TypeChart, *, include_neutral: bool = False
) -> dict[str, float]:
    """反向查询：给定防守属性组合，列出所有进攻属性及其倍率。

    Args:
        defense: 防守属性列表（1–2 个）。
        chart: 克制表。
        include_neutral: 是否包含倍率为 1.0 的进攻属性。默认只返回非中性项。

    Returns:
        {attack: multiplier}，按属性在克制表中出现的顺序。
    """
    result: dict[str, float] = {}
    for attack in chart:
        multiplier = evaluate(attack, defense, chart)
        if include_neutral or not _equals(multiplier, NEUTRAL):
            result[attack] = multiplier
    return result


def _attack_row(attack: str, chart: TypeChart) -> Mapping[str, float]:
    """取进攻属性行；克不到任何东西也返回空 Mapping（等价全 1.0）。"""
    if attack not in chart:
        raise KeyError(f"进攻属性 {attack!r} 不在克制表中")
    return chart[attack]


def format_multiplier(multiplier: float) -> str:
    """把倍率转成对人友好的标签（用于 API 响应与界面展示）。"""
    if _is_zero(multiplier):
        return "无效（免疫）"
    if _equals(multiplier, 0.25):
        return "1/4×"
    if _equals(multiplier, 0.5):
        return "1/2×"
    if _equals(multiplier, 1):
        return "1×"
    if _equals(multiplier, 2):
        return "2×"
    if _equals(multiplier, 4):
        return "4×"
    return f"{multiplier:g}×"
