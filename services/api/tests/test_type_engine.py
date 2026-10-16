"""domain/type_engine 纯函数测试。

关键：这里用 **仓库根部同一份** `data/type-chart.cases.json` 作为测试向量，
前端 Vitest 也读这同一份 —— 两端结果必须一致。生成脚本 gen_type_chart.py 会
校验向量本身与 PokéAPI 数据一致，避免「两端一致地错」。

克制表同样直接读取仓库根 `data/type-chart.json`（单一真相），不内联副本。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.type_engine import evaluate, format_multiplier, reverse

_REPO_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _load(name: str) -> dict:
    path = _REPO_DATA_DIR / name
    if not path.exists():
        pytest.fail(
            f"仓库缺少 {path}：请先运行 `uv run python scripts/gen_type_chart.py` 生成",
        )
    return json.loads(path.read_text(encoding="utf-8"))


#: 仓库根规范克制表（与 PokéAPI 对齐，由生成脚本产出）。
TEST_CHART: dict[str, dict[str, float]] = _load("type-chart.json")["chart"]

#: 前后端共享测试向量。
SHARED_CASES: list[dict] = _load("type-chart.cases.json")["cases"]


@pytest.mark.parametrize("case", SHARED_CASES, ids=lambda c: c["id"])
def test_shared_cases(case: dict) -> None:
    """前后端共用向量：evaluate 与 reverse 结果与期望一致。"""
    if case["kind"] == "evaluate":
        actual = evaluate(case["attack"], case["defense"], TEST_CHART)
        assert abs(actual - float(case["expected"])) < 1e-9, case["id"]
    elif case["kind"] == "reverse":
        actual = reverse(case["defense"], TEST_CHART, include_neutral=False)
        expected = {k: float(v) for k, v in case["expected"].items()}
        # 非中性项必须恰好等于期望（多列少列都算错）
        assert set(actual) == set(expected), (
            f"{case['id']}: 反查 {case['defense']} 非中性项不一致 "
            f"（多 {set(actual) - set(expected)}，少 {set(expected) - set(actual)}）"
        )
        for attack, multiplier in expected.items():
            assert abs(actual[attack] - multiplier) < 1e-9, f"{case['id']}: {attack}"


def test_evaluate_single_neutral() -> None:
    assert evaluate("normal", ["grass"], TEST_CHART) == 1.0


def test_evaluate_single_immune_is_zero() -> None:
    assert evaluate("normal", ["ghost"], TEST_CHART) == 0.0


def test_evaluate_dual_4x() -> None:
    # 火 → 草/冰 = 2 × 2 = 4
    assert evaluate("fire", ["grass", "ice"], TEST_CHART) == 4.0


def test_evaluate_dual_cancels_to_neutral() -> None:
    # 火 → 水（0.5）× 草（2）= 1
    assert evaluate("fire", ["water", "grass"], TEST_CHART) == 1.0


def test_evaluate_immune_dominates_dual() -> None:
    # 格斗 → 幽灵 = 免疫；即便另一防守属性被克制，整体仍为 0
    assert evaluate("fighting", ["ghost", "normal"], TEST_CHART) == 0.0


def test_evaluate_unknown_attack_raises() -> None:
    with pytest.raises(KeyError, match="不在克制表中"):
        evaluate("shadow", ["normal"], TEST_CHART)


def test_evaluate_unknown_defense_treated_neutral() -> None:
    # 防守属性不在行的显式列表里 → 缺省 1.0（不抛错，因为克不到 = 中性）
    assert evaluate("fire", ["normal"], TEST_CHART) == 1.0


def test_reverse_excludes_neutral_by_default() -> None:
    result = reverse(["fire"], TEST_CHART)
    assert "fire" in result  # 0.5
    assert "normal" not in result  # 1.0 被排除


def test_reverse_can_include_neutral() -> None:
    result = reverse(["fire"], TEST_CHART, include_neutral=True)
    assert len(result) == 18


def test_format_multiplier_labels() -> None:
    assert format_multiplier(0.0) == "无效（免疫）"
    assert format_multiplier(0.25) == "1/4×"
    assert format_multiplier(0.5) == "1/2×"
    assert format_multiplier(1.0) == "1×"
    assert format_multiplier(2.0) == "2×"
    assert format_multiplier(4.0) == "4×"
