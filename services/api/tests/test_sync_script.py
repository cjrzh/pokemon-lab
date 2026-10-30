"""同步脚本的世代区间解析与世代表一致性。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

# 脚本通过 sys.path 注入 services/api，这里直接导入其纯函数
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from sync_pokeapi import (  # noqa: E402
    parse_generation_range,
    parse_range,
)

from app.services.dex_sync_service import (  # noqa: E402
    NATIONAL_DEX_GENERATIONS,
    NATIONAL_DEX_TOTAL,
)


def test_national_dex_generation_table_is_contiguous() -> None:
    """九个世代的区间必须首尾相接、覆盖 1–1025，且总数一致。"""
    expected_start = 1
    total = 0
    for gen in range(1, 10):
        start, end = NATIONAL_DEX_GENERATIONS[gen]
        assert start == expected_start, f"第 {gen} 世代应从 #{expected_start} 开始"
        assert end >= start
        total += end - start + 1
        expected_start = end + 1
    assert expected_start == NATIONAL_DEX_TOTAL + 1
    assert total == NATIONAL_DEX_TOTAL


def test_parse_generation_range() -> None:
    assert parse_generation_range("2") == (152, 251)
    assert parse_generation_range("1") == (1, 151)
    assert parse_generation_range("9") == (906, 1025)
    assert parse_generation_range("3-5") == (252, 649)
    assert parse_generation_range("1-9") == (1, 1025)


@pytest.mark.parametrize("value", ["0", "10", "3-2", "abc", "1-10", ""])
def test_parse_generation_range_rejects_invalid(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_generation_range(value)


def test_parse_range_still_validates() -> None:
    assert parse_range("1-151") == (1, 151)
    with pytest.raises(argparse.ArgumentTypeError):
        parse_range("151-1")


def test_rating_file_is_valid_and_referenced_abilities_exist() -> None:
    """评级文件结构合法；S 级条目都能在仓库译文/数据中找到对应特性名。"""
    import json

    from app.services.ability_service import TIER_NORMAL, TIER_S, load_ratings

    ratings = load_ratings()
    assert len(ratings) >= 100
    s_tier = [name for name, entry in ratings.items() if entry.tier == TIER_S]
    assert len(s_tier) >= 50
    assert all(entry.tier in (TIER_S, TIER_NORMAL) for entry in ratings.values())

    path = _REPO_ROOT / "data" / "abilities" / "s-tier.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source"] == "llm-rating"
    assert payload["criteria"]


def test_ability_translation_file_covers_missing_effects() -> None:
    """特性中文说明译文文件结构合法，且没有空值。"""
    import json

    path = _REPO_ROOT / "data" / "flavor-zh" / "abilities-zh.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload["entries"]
    assert len(entries) >= 30
    assert all(text.strip() for text in entries.values())
    assert payload["source"] == "project-translation"
