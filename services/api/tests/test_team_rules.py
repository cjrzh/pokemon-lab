"""队伍合法性规则（纯函数）测试。"""

from __future__ import annotations

from app.domain.team_rules import (
    EV_MAX,
    POINT_MAX,
    TEAM_SIZE,
    validate_points,
    validate_team,
)

#: 一个最小的合法成员。
MEMBER = {
    "dex_number": 6,
    "showdown_name": "Charizard",
    "item": "life-orb",
    "ability": "blaze",
    "moves": ["flamethrower", "protect"],
    "evs": [4, 0, 0, 252, 0, 252],
    "ivs": [31, 31, 31, 31, 31, 31],
}

LEGAL = {6: {"flamethrower", "protect", "air-slash"}}
ABILITIES = {6: {"blaze", "solar-power"}}


def _validate(members, **overrides):
    kwargs = {
        "points_kind": "ev",
        "legal_moves": LEGAL,
        "legal_abilities": ABILITIES,
        "moves_known": True,
    }
    kwargs.update(overrides)
    return validate_team(members, **kwargs)


def test_valid_team_passes() -> None:
    assert _validate([MEMBER]).ok


def test_duplicate_dex_number_rejected() -> None:
    second = {**MEMBER, "item": "choice-specs"}
    result = _validate([MEMBER, second])

    assert not result.ok
    assert any("同一编号不能上两次" in issue.message for issue in result.issues)


def test_duplicate_item_rejected() -> None:
    second = {**MEMBER, "dex_number": 9, "showdown_name": "Blastoise"}
    result = _validate(
        [MEMBER, second],
        legal_moves={**LEGAL, 9: {"protect"}},
        legal_abilities={**ABILITIES, 9: {"blaze"}},
    )

    assert not result.ok
    assert any("相同道具" in issue.message for issue in result.issues)


def test_empty_items_do_not_collide() -> None:
    first = {**MEMBER, "item": None}
    second = {
        **MEMBER,
        "dex_number": 9,
        "item": "",
        "showdown_name": "Blastoise",
        "moves": ["protect"],
    }
    result = _validate(
        [first, second],
        legal_moves={**LEGAL, 9: {"protect"}},
        legal_abilities={**ABILITIES, 9: {"blaze"}},
    )

    assert result.ok


def test_illegal_move_rejected() -> None:
    member = {**MEMBER, "moves": ["flamethrower", "surf"]}
    result = _validate([member])

    assert not result.ok
    assert any("无法学会" in issue.message for issue in result.issues)


def test_illegal_move_skipped_when_data_missing() -> None:
    member = {**MEMBER, "moves": ["flamethrower", "surf"]}
    result = _validate([member], moves_known=False)

    assert result.ok


def test_illegal_ability_rejected() -> None:
    member = {**MEMBER, "ability": "levitate"}
    result = _validate([member])

    assert not result.ok
    assert any("不是该宝可梦可用的特性" in issue.message for issue in result.issues)


def test_too_many_moves_rejected() -> None:
    member = {**MEMBER, "moves": ["flamethrower", "protect", "air-slash", "roost", "toxic"]}
    result = _validate([member])

    assert not result.ok
    assert any("最多 4 个招式" in issue.message for issue in result.issues)


def test_more_than_six_members_rejected() -> None:
    members = [
        {**MEMBER, "dex_number": 100 + index, "showdown_name": f"P{index}", "item": None}
        for index in range(TEAM_SIZE + 1)
    ]
    result = _validate(members)

    assert not result.ok
    assert any("最多 6 只" in issue.message for issue in result.issues)


def test_empty_team_rejected() -> None:
    result = _validate([])
    assert not result.ok
    assert any("至少要有一只" in issue.message for issue in result.issues)


def test_ev_out_of_range() -> None:
    member = {**MEMBER, "evs": [EV_MAX + 4, 0, 0, 0, 0, 0]}
    result = _validate([member])

    assert any("EV单项" in issue.message for issue in result.issues)


def test_ev_total_out_of_range() -> None:
    member = {**MEMBER, "evs": [252, 252, 252, 0, 0, 0]}
    result = _validate([member])

    assert any("合计不能超过" in issue.message for issue in result.issues)


def test_champions_point_limits() -> None:
    member = {**MEMBER, "evs": [POINT_MAX, POINT_MAX, 2, 0, 0, 0], "ivs": None}
    result = _validate([member], points_kind="stat_points")
    assert result.ok

    too_much = {**MEMBER, "evs": [POINT_MAX, POINT_MAX, POINT_MAX, 0, 0, 0], "ivs": None}
    result = _validate([too_much], points_kind="stat_points")
    assert any("能力点合计" in issue.message for issue in result.issues)


def test_iv_out_of_range() -> None:
    member = {**MEMBER, "ivs": [32, 31, 31, 31, 31, 31]}
    result = _validate([member])

    assert any("个体值应在 0–31" in issue.message for issue in result.issues)


def test_validate_points_requires_six_values() -> None:
    from app.domain.team_rules import TeamValidation

    result = TeamValidation()
    validate_points([1, 2, 3], "ev", field_prefix="x", result=result)
    assert any("6 项" in issue.message for issue in result.issues)


# ---------------------------------------------------------------------------
# 超极巨化
# ---------------------------------------------------------------------------

GMAX_ALLOWED = {"charizard", "toxtricity-low-key"}


def test_gigantamax_valid_for_swsh_species_with_g_form() -> None:
    member = {**MEMBER, "showdown_name": "Charizard", "gigantamax": True}
    result = _validate([member], format_key="swsh", gmax_allowed=GMAX_ALLOWED)
    assert result.ok


def test_gigantamax_rejected_outside_swsh() -> None:
    member = {**MEMBER, "showdown_name": "Charizard", "gigantamax": True}
    result = _validate([member], format_key="sv", gmax_allowed=GMAX_ALLOWED)
    assert not result.ok
    assert any("只有剑盾" in issue.message for issue in result.issues)


def test_gigantamax_rejected_for_species_without_g_form() -> None:
    member = {**MEMBER, "showdown_name": "Blastoise", "gigantamax": True}
    result = _validate([member], format_key="swsh", gmax_allowed=GMAX_ALLOWED)
    assert not result.ok
    assert any("没有超极巨化形态" in issue.message for issue in result.issues)


def test_gigantamax_not_checked_without_clist() -> None:
    """清单缺失（gmax_allowed=None）时如实降级：不把「不知道」当成「不合法」。"""
    member = {**MEMBER, "showdown_name": "Blastoise", "gigantamax": True}
    assert _validate([member], format_key="swsh", gmax_allowed=None).ok


def test_gigantamax_accepts_g_suffixed_showdown_name() -> None:
    """`Charizard-Gmax` 这样的写法也能命中清单（去掉 -Gmax 再比）。"""
    member = {**MEMBER, "showdown_name": "Charizard-Gmax", "gigantamax": True}
    assert _validate([member], format_key="swsh", gmax_allowed=GMAX_ALLOWED).ok
