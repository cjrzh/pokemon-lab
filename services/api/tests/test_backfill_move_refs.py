"""`move_ref` 回填脚本的纯函数测试：从双打数据里收集实际用到的招式 slug。"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from backfill_move_refs import _doubles_move_slugs  # noqa: E402


def test_doubles_move_slugs_covers_all_formats() -> None:
    """仓库内四个格式的统计里出现过的招式都应被收集（去重）。"""
    slugs = _doubles_move_slugs()

    # 水流连打：PokéAPI 的宝可梦招式表里缺失，但双打统计在用
    assert "surging-strikes" in slugs
    assert "protect" in slugs
    assert len(slugs) > 500


def test_doubles_move_slugs_is_deterministic() -> None:
    assert _doubles_move_slugs() == _doubles_move_slugs()
