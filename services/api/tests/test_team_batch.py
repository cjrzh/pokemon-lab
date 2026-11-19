"""批量修改规则测试（纯函数：闪光 / 等级 / 性别）。"""

from __future__ import annotations

import pytest

from app.domain.team_rules import (
    allowed_genders,
    batch_gender,
    batch_level,
    batch_shiny,
)


def _member(dex: int, name: str = "X", **overrides) -> dict:
    payload = {
        "dex_number": dex,
        "showdown_name": name,
        "evs": [0] * 6,
        "moves": [],
    }
    payload.update(overrides)
    return payload


# ---------- 性别合法性 ----------


def test_allowed_genders_reads_pokeapi_scale() -> None:
    """gender_rate：-1 无性别、0 只有雄性、8 只有雌性、其余雌雄都有。"""
    assert allowed_genders(-1) == set()
    assert allowed_genders(0) == {"M"}
    assert allowed_genders(8) == {"F"}
    assert allowed_genders(4) == {"M", "F"}
    assert allowed_genders(1) == {"M", "F"}
    assert allowed_genders(6) == {"M", "F"}
    # 数据缺失时不擅自限制
    assert allowed_genders(None) == {"M", "F"}


def test_batch_gender_sets_compatible_members() -> None:
    members = [_member(25, "Pikachu"), _member(26, "Raichu")]
    updated, skipped = batch_gender(members, "F", {25: 4, 26: 4})

    assert skipped == []
    assert [m["gender"] for m in updated] == ["F", "F"]


def test_batch_gender_keeps_illegal_members_unchanged() -> None:
    """尼多朗只有雄性、尼多兰只有雌性、超梦无性别 —— 一律保持原样并说明原因。"""
    members = [
        _member(32, "Nidoran-M", gender="M"),
        _member(29, "Nidoran-F", gender="F"),
        _member(150, "Mewtwo"),
        _member(25, "Pikachu"),
    ]
    rates = {32: 0, 29: 8, 150: -1, 25: 4}
    updated, skipped = batch_gender(members, "F", rates)

    # 尼多朗（只能雄性）与超梦（无性别）不动；尼多兰本来就是雌性、皮卡丘改为雌性
    assert [m.get("gender") for m in updated] == ["M", "F", None, "F"]
    assert len(skipped) == 2
    assert any("只能为雄性" in item for item in skipped)
    assert any("没有性别" in item for item in skipped)


def test_batch_gender_to_male_skips_female_only() -> None:
    members = [_member(29, "Nidoran-F")]
    updated, skipped = batch_gender(members, "M", {29: 8})

    assert updated[0].get("gender") is None  # 原本没有性别，保持原样
    assert any("只能为雌性" in item for item in skipped)


def test_batch_gender_null_clears_gender() -> None:
    """传 null 表示不指定性别：一律清空，不作为「不合法」提示。"""
    members = [_member(25, "Pikachu", gender="M"), _member(150, "Mewtwo")]
    updated, skipped = batch_gender(members, None, {25: 4, 150: -1})

    assert [m["gender"] for m in updated] == [None, None]
    assert skipped == []


def test_batch_gender_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        batch_gender([_member(25)], "X", {25: 4})


# ---------- 闪光 ----------


def test_batch_shiny_sets_every_member() -> None:
    members = [_member(25), _member(150, "Mewtwo", shiny=False)]
    updated, skipped = batch_shiny(members, True)

    assert skipped == []
    assert all(member["shiny"] is True for member in updated)
    # 原列表不被就地改动（批量操作靠替换，不改已有对象）
    assert members[0].get("shiny") is None


# ---------- 等级 ----------


def test_batch_level_sets_and_resets() -> None:
    members = [_member(25, level=50), _member(150, "Mewtwo")]
    updated, _ = batch_level(members, 100)
    assert [m["level"] for m in updated] == [100, 100]

    # null = 恢复「按格式默认」
    reset, _ = batch_level(updated, None)
    assert [m["level"] for m in reset] == [None, None]


def test_batch_level_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        batch_level([_member(25)], 0)
    with pytest.raises(ValueError):
        batch_level([_member(25)], 101)
