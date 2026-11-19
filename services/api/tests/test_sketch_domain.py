"""写生招式的纯函数规则（不需要数据库）。"""

from __future__ import annotations

from app.domain.sketch import (
    NON_SKETCHABLE,
    is_smeargle,
    sketchable_moves,
)


def test_is_smeargle_by_dex_or_by_sketch_move() -> None:
    assert is_smeargle(235, {"sketch"})
    # 招式表里带写生的记录也算（防御性：未来若有其它学习写生的数据）
    assert is_smeargle(999, {"sketch"})
    assert not is_smeargle(999, {"tackle"})


def test_sketchable_moves_excludes_blocked() -> None:
    version_moves = {"spore", "dark-void", "follow-me", "tera-starstorm"}
    assert sketchable_moves(version_moves) == {"spore", "follow-me"}


def test_non_sketchable_contains_showdown_flags() -> None:
    for move in ("dark-void", "hyperspace-fury", "revival-blessing", "tera-starstorm"):
        assert move in NON_SKETCHABLE
