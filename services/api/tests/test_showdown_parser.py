"""Showdown 队伍文本解析测试（纯函数，不碰数据库）。"""

from __future__ import annotations

from app.domain.showdown_parser import parse_head, parse_points, parse_showdown


def test_parse_head_variants() -> None:
    """头行的四种写法：裸名 / 性别 / 道具 / 昵称 + 形态。"""
    assert parse_head("Charizard") == ("Charizard", None, None, None)
    assert parse_head("Charizard (M)") == ("Charizard", None, "M", None)
    assert parse_head("Charizard @ Life Orb") == ("Charizard", None, None, "Life Orb")
    assert parse_head("Zard (Charizard) (F) @ Choice Specs") == (
        "Charizard",
        "Zard",
        "F",
        "Choice Specs",
    )
    # 带连字符的形态名不能被当成昵称括号
    assert parse_head("Urshifu-Rapid-Strike @ Focus Sash") == (
        "Urshifu-Rapid-Strike",
        None,
        None,
        "Focus Sash",
    )


def test_parse_points_uses_default_for_missing_stats() -> None:
    """EV 缺省 0、IV 缺省 31；显式写出的 0 必须保留。"""
    evs, bad = parse_points("252 SpA / 4 SpD / 252 Spe")
    assert evs == [0, 0, 0, 252, 4, 252]
    assert bad == []

    ivs, _ = parse_points("0 Atk", default=31)
    assert ivs == [31, 0, 31, 31, 31, 31]

    # 认不出的项如实返回，不静默改数值
    _, bad = parse_points("252 Foo")
    assert bad == ["252 Foo"]


def test_parse_empty_text() -> None:
    result = parse_showdown("")
    assert result.sets == []
    assert result.problems == []
    # 只有交易前缀也不该报「没有识别到」的错误
    assert parse_showdown("!tradeSV\n").sets == []


def test_parse_full_set() -> None:
    text = """!tradeSV
Charizard (F) @ Choice Specs
Ability: Solar Power
Level: 50
Shiny: Yes
Tera Type: Fire
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
IVs: 0 Atk
- Heat Wave
- Air Slash
"""
    parsed = parse_showdown(text)
    assert parsed.problems == []
    assert len(parsed.sets) == 1

    charizard = parsed.sets[0]
    assert charizard.species == "Charizard"
    assert charizard.gender == "F"
    assert charizard.item == "Choice Specs"
    assert charizard.ability == "Solar Power"
    assert charizard.level == 50
    assert charizard.shiny is True
    assert charizard.tera_type == "Fire"
    assert charizard.nature == "timid"
    assert charizard.evs == [0, 0, 0, 252, 4, 252]
    assert charizard.ivs == [31, 0, 31, 31, 31, 31]
    assert charizard.moves == ["Heat Wave", "Air Slash"]


def test_parse_nickname_and_mega_form() -> None:
    text = """Zard (Charizard-Mega-Y) @ Charizardite Y
Ability: Drought
Modest Nature
- Heat Wave
"""
    parsed = parse_showdown(text)
    member = parsed.sets[0]
    assert member.species == "Charizard-Mega-Y"
    assert member.nickname == "Zard"
    assert member.nature == "modest"
    assert member.ivs is None  # 没写 IV 行 → 交给格式默认
    assert member.moves == ["Heat Wave"]


def test_parse_ignores_unknown_fields_and_keeps_unparseable_lines() -> None:
    """Happiness / Gigantamax 等字段不影响对战配置，忽略即可。"""
    text = """Pikachu @ Light Ball
Ability: Static
Happiness: 160
Gigantamax: Yes
Level: 50
Timid Nature
- Thunderbolt
"""
    parsed = parse_showdown(text)
    assert parsed.problems == []
    assert parsed.sets[0].moves == ["Thunderbolt"]


def test_parse_dynamax_level() -> None:
    """剑盾的极巨化等级 0–10；超出范围按「没写」处理，不写入非法值。"""
    text = """Pikachu @ Light Ball
Ability: Static
Dynamax Level: 7
- Thunderbolt
"""
    assert parse_showdown(text).sets[0].dynamax_level == 7

    bad = text.replace("Dynamax Level: 7", "Dynamax Level: 11")
    assert parse_showdown(bad).sets[0].dynamax_level is None


def test_parse_gigantamax() -> None:
    """`Gigantamax: Yes` → True；其他取值视为否。"""
    text = """Charizard (喷火龙) (M) @ Heavy-Duty Boots
Ability: Blaze
Level: 50
Dynamax Level: 10
Gigantamax: Yes
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Flamethrower
"""
    parsed = parse_showdown(text).sets[0]
    assert parsed.gigantamax is True
    assert parsed.dynamax_level == 10
    assert parsed.species == "Charizard"

    no_line = text.replace("Gigantamax: Yes", "Gigantamax: No")
    assert parse_showdown(no_line).sets[0].gigantamax is False


def test_parse_gigantamax_prefix_in_species_head() -> None:
    """Limitless 写法 `Gigantamax Charizard`：剥掉前缀并标记，物种名仍可查编号。"""
    text = """Gigantamax Charizard @ Charti Berry
Ability: Blaze
Level: 50
Timid Nature
- Protect
"""
    parsed = parse_showdown(text).sets[0]
    assert parsed.species == "Charizard"
    assert parsed.gigantamax is True
    assert parsed.item == "Charti Berry"

    chinese = text.replace("Gigantamax Charizard", "超极巨化 喷火龙")
    parsed_cn = parse_showdown(chinese).sets[0]
    assert parsed_cn.species == "喷火龙"
    assert parsed_cn.gigantamax is True


def test_parse_reports_unrecognizable_blocks() -> None:
    """整块认不出时跳过并记原因，不猜一个配置出来。"""
    text = """@ Life Orb
- Heat Wave

Charizard @ Life Orb
- Heat Wave
"""
    parsed = parse_showdown(text)
    assert len(parsed.sets) == 1
    assert parsed.sets[0].species == "Charizard"
    assert len(parsed.problems) == 1
    assert "第 1 段无法识别" in parsed.problems[0]


def test_parse_caps_moves_at_four() -> None:
    text = """Charizard
- Heat Wave
- Air Slash
- Protect
- Roost
- Dragon Pulse
"""
    parsed = parse_showdown(text)
    assert len(parsed.sets[0].moves) == 4


def test_parse_handles_crlf_and_blank_lines() -> None:
    """从聊天框粘贴的文本常带 \\r\\n 与多余空行。"""
    text = (
        "Charizard @ Life Orb\r\nAbility: Blaze\r\n\r\n\r\n"
        "Pikachu @ Light Ball\r\n- Thunderbolt\r\n"
    )
    parsed = parse_showdown(text)
    assert [item.species for item in parsed.sets] == ["Charizard", "Pikachu"]
