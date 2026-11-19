"""对战分类规则测试：优先级、边界与数据完整性。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain import battle_class

REPO_DATA = Path(__file__).resolve().parents[3] / "data" / "battle-classes.json"


@pytest.fixture()
def table():
    battle_class.reset_battle_class_cache()
    yield battle_class.load_battle_classes()
    battle_class.reset_battle_class_cache()


def test_priority_between_categories(table) -> None:
    # 悖谬优先于一切（部分悖谬在民间也被叫「准神」）
    assert table.classify("flutter-mane", is_legendary=False, is_mythical=False) == "paradox"
    # 幻兽优先于传说
    assert table.classify("mew", is_legendary=True, is_mythical=True) == "mythical"
    # 一级神
    assert table.classify("koraidon", is_legendary=True, is_mythical=False) == "restricted"
    # 传奇但不在 restricted 名单 → 二级神
    assert table.classify("articuno", is_legendary=True, is_mythical=False) == "sub_legendary"
    # 准神
    assert table.classify("garchomp", is_legendary=False, is_mythical=False) == "pseudo_legendary"
    # 普通
    assert table.classify("pikachu", is_legendary=False, is_mythical=False) == "normal"


def test_restricted_not_decided_by_stat_total(table) -> None:
    """一级神是规则定义，不是种族值：超梦 680 属二级神，盾之王 / 太乐巴戈斯是 600 级一级神。"""
    assert table.classify("terapagos", is_legendary=True, is_mythical=False) == "restricted"
    assert table.classify("mewtwo", is_legendary=True, is_mythical=False) == "restricted"


def test_unknown_names_are_normal(table) -> None:
    assert table.classify("not-a-real-pokemon", is_legendary=False, is_mythical=False) == "normal"


def test_names_are_lowercase_and_unique() -> None:
    raw = json.loads(REPO_DATA.read_text(encoding="utf-8"))
    for field in ("pseudo_legendary", "restricted", "paradox"):
        names = raw[field]
        assert names == [name.lower() for name in names], field
        assert len(names) == len(set(names)), f"{field} 有重复"


def test_classify_degrades_when_data_missing(monkeypatch, tmp_path) -> None:
    """数据缺失时按普通处理，不抛异常（图鉴浏览不能因为分类表坏了就挂掉）。"""
    battle_class.reset_battle_class_cache()
    monkeypatch.setenv("POKEMON_LAB_DATA_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert battle_class.classify(
        "koraidon", is_legendary=True, is_mythical=False
    ) == "normal"
    get_settings.cache_clear()
    battle_class.reset_battle_class_cache()
