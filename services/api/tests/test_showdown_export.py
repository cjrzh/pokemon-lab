"""Showdown 导出纯函数测试：导出格式与解析器往返一致。"""

from __future__ import annotations

from app.domain.showdown_export import render_member, render_team
from app.domain.showdown_parser import parse_showdown

BASE = {
    "showdown_name": "Charizard",
    "nickname": None,
    "item": "Life Orb",
    "ability": "Blaze",
    "nature": "timid",
    "evs": [4, 0, 0, 252, 0, 252],
    "ivs": [31, 31, 31, 31, 31, 31],
    "moves": ["Flamethrower", "Air Slash", "Protect", "Roost"],
    "tera_type": "Fire",
    "gender": "F",
    "shiny": True,
    "level": None,
    "language": "CHS",
}


def test_render_member_full_set() -> None:
    text = render_member(BASE, format_key="sv", default_level=50)

    assert text.startswith("Charizard (F) @ Life Orb")
    assert "Ability: Blaze" in text
    assert "Level: 50" in text
    assert "Shiny: Yes" in text
    assert "Language: CHS" in text
    assert "Tera Type: Fire" in text
    assert "EVs: 4 HP / 252 SpA / 252 Spe" in text
    assert "Timid Nature" in text
    # IV 全 31 时省略
    assert "IVs:" not in text
    assert text.rstrip().endswith("- Roost")


def test_render_omits_tera_outside_sv() -> None:
    """太晶属性只在朱紫（sv）输出。"""
    assert "Tera Type" not in render_member(BASE, format_key="swsh")


def test_render_omits_language_for_swsh() -> None:
    """剑盾的复制 / 导出代码不带 `Language:` 行；其它格式保留。"""
    assert "Language:" not in render_member(BASE, format_key="swsh")
    assert "Language: CHS" in render_member(BASE, format_key="sv")
    assert "Language: CHS" in render_member(BASE, format_key="bdsp")


def test_render_keeps_non_default_ivs() -> None:
    payload = {**BASE, "ivs": [31, 0, 31, 31, 31, 31]}
    assert "IVs: 0 Atk" in render_member(payload, format_key="sv")


def test_render_dynamax_level_only_for_swsh() -> None:
    """极巨化等级只在剑盾输出；未设置时也写默认值 10（复制出去的代码要带这个参数）。"""
    payload = {**BASE, "dynamax_level": 7}
    swsh = render_member(payload, format_key="swsh")
    assert "Dynamax Level: 7" in swsh
    # 朱紫没有极巨化，不输出这一行
    assert "Dynamax Level" not in render_member(payload, format_key="sv")

    # 显式 10 / 未设置都输出 10（不再依赖 Showdown 的隐式默认值）
    assert "Dynamax Level: 10" in render_member(
        {**BASE, "dynamax_level": 10}, format_key="swsh"
    )
    assert "Dynamax Level: 10" in render_member(BASE, format_key="swsh")


def test_render_gigantamax_only_for_swsh() -> None:
    """超极巨化只在剑盾输出，且与 Dynamax Level 相邻（Showdown 的行序）。"""
    payload = {**BASE, "gigantamax": True, "dynamax_level": 10}
    text = render_member(payload, format_key="swsh")
    lines = [line.rstrip() for line in text.splitlines()]
    # Level: 50 → Dynamax Level: 10 → Gigantamax: Yes
    assert lines[lines.index("Level: 50") + 1] == "Dynamax Level: 10"
    assert lines[lines.index("Dynamax Level: 10") + 1] == "Gigantamax: Yes"

    # 朱紫 / BDSP 不支持超极巨化：不输出
    assert "Gigantamax" not in render_member(payload, format_key="sv")
    assert "Gigantamax" not in render_member(payload, format_key="bdsp")

    # 未开启时不输出
    assert "Gigantamax" not in render_member(BASE, format_key="swsh")


def test_dynamax_level_roundtrips_through_parser() -> None:
    text = render_member({**BASE, "dynamax_level": 4}, format_key="swsh")
    parsed = parse_showdown(text)
    assert parsed.sets[0].dynamax_level == 4

    # 未设置时导出补默认值 10：导入端也不需要猜
    parsed_default = parse_showdown(render_member(BASE, format_key="swsh"))
    assert parsed_default.sets[0].dynamax_level == 10


def test_gigantamax_roundtrips_through_parser() -> None:
    payload = {**BASE, "gigantamax": True, "dynamax_level": 8}
    text = render_member(payload, format_key="swsh")
    parsed = parse_showdown(text).sets[0]
    assert parsed.gigantamax is True
    assert parsed.dynamax_level == 8

    # 没写这行 → False
    assert parse_showdown(render_member(BASE, format_key="swsh")).sets[0].gigantamax is False


def test_render_uses_nickname_and_default_level() -> None:
    payload = {**BASE, "nickname": "火龙", "level": None}
    text = render_member(payload, format_key="su", default_level=100)
    assert text.startswith("火龙 (Charizard) (F) @ Life Orb")
    # 默认等级 100 时不写 Level 行
    assert "Level:" not in text


def test_export_roundtrips_through_parser() -> None:
    """导出 → 解析应还原关键字段（两种方向不能各写一套）。"""
    text = render_team(
        [{**BASE, "showdown_name": "Charizard"}],
        format_key="sv",
        default_level=50,
    )
    parsed = parse_showdown(text)

    assert len(parsed.sets) == 1
    parsed_set = parsed.sets[0]
    assert parsed_set.species == "Charizard"
    assert parsed_set.item == "Life Orb"
    assert parsed_set.ability == "Blaze"
    assert parsed_set.nature == "timid"
    assert parsed_set.evs == [4, 0, 0, 252, 0, 252]
    assert parsed_set.moves == ["Flamethrower", "Air Slash", "Protect", "Roost"]
    assert parsed_set.tera_type == "Fire"
    assert parsed_set.shiny is True
    assert parsed_set.language == "CHS"
