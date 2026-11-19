"""队伍打击面 / 缺失面分析测试（纯函数）。"""

from __future__ import annotations

import pytest

from app.domain.team_analysis import analyze_team
from app.services.type_chart_service import load_type_chart


@pytest.fixture(scope="module")
def chart():
    return load_type_chart().chart


def test_attack_coverage_lists_super_effective_targets(chart) -> None:
    """火系队伍能打到草 / 虫 / 冰 / 钢。"""
    result = analyze_team([{"dex_number": 6, "types": ["fire"]}], chart)

    fire = next(item for item in result.attack if item.type == "fire")
    assert set(fire.hits) >= {"grass", "bug", "ice", "steel"}
    assert fire.member_count == 1


def test_coverage_counts_members_with_same_type(chart) -> None:
    """同属性多只时 member_count 累加（排序用）。"""
    result = analyze_team(
        [
            {"dex_number": 6, "types": ["fire", "flying"]},
            {"dex_number": 136, "types": ["fire"]},
        ],
        chart,
    )
    fire = next(item for item in result.attack if item.type == "fire")
    assert fire.member_count == 2


def test_gaps_are_types_nobody_can_hit_hard(chart) -> None:
    """纯火系队伍打不动火 / 水 / 龙（缺口）。"""
    result = analyze_team([{"dex_number": 6, "types": ["fire"]}], chart)

    assert "water" in result.gaps
    assert "dragon" in result.gaps
    assert "fire" in result.gaps
    # 能打到的属性不算缺口
    assert "grass" not in result.gaps


def test_hotspots_flag_shared_weaknesses(chart) -> None:
    """两只都被电系 2× 克制 → 电系成为共同弱点。"""
    result = analyze_team(
        [
            {"dex_number": 6, "types": ["fire", "flying"]},
            {"dex_number": 9, "types": ["water"]},
        ],
        chart,
    )

    electric = next(item for item in result.hotspots if item.type == "electric")
    assert sorted(electric.members) == [6, 9]


def test_single_member_weakness_is_not_a_hotspot(chart) -> None:
    """只有一只怕的属性不算「共同弱点」（阈值是 ≥2）。"""
    result = analyze_team(
        [
            {"dex_number": 6, "types": ["fire", "flying"]},
            {"dex_number": 26, "types": ["electric"]},
        ],
        chart,
    )
    # 地面系只克制火飞（喷火龙），雷丘不受影响
    assert all(item.type != "ground" for item in result.hotspots)


def test_empty_team_has_full_gaps(chart) -> None:
    """空队伍：没有打击面，所有属性都是缺口。"""
    result = analyze_team([], chart)

    assert result.attack == []
    assert result.hotspots == []
    assert set(result.gaps) == {defense for row in chart.values() for defense in row}


def test_unknown_types_are_skipped_not_guessed(chart) -> None:
    """属性不在克制表里时跳过，不猜也不报错。"""
    result = analyze_team(
        [{"dex_number": 6, "types": ["fire", "not-a-type"]}], chart
    )
    assert all(item.type != "not-a-type" for item in result.attack)
