"""Smogon 双打统计文本解析的纯函数测试。

用贴近真实文件的片段（含旧格式的 Checks and Counters 重复块、Champions 能力点、
朱紫太晶属性）验证解析与推断规则。
"""

from __future__ import annotations

from app.domain.smogon_stats import (
    detect_points_kind,
    infer_ivs,
    parse_moveset_text,
    parse_usage_table,
    showdown_slug,
)

USAGE_TEXT = """
Total battles: 1827
+ ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
| Rank | Pokemon            | Usage %   | Raw    | %       | Real   | %       |
+ ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
| 1    | Incineroar         | 83.49422% | 1559   | 42.666% | 0      | 0.000%  |
| 2    | Gastrodon          | 81.16168% | 802    | 21.949% | 0      | 0.000%  |
+ ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
"""

MOVESET_TEXT = """
 +----------------------------------------+
 | Incineroar                             |
 +----------------------------------------+
 | Raw count: 1669                        |
 | Avg. weight: 0.0181604902239           |
 | Viability Ceiling: 73                  |
 +----------------------------------------+
 | Abilities                              |
 | Intimidate 99.920%                     |
 | Blaze  0.080%                          |
 +----------------------------------------+
 | Items                                  |
 | Shuca Berry 87.900%                    |
 | Safety Goggles  6.484%                 |
 | Other  0.003%                          |
 +----------------------------------------+
 | Spreads                                |
 | Careful:252/108/148/0/0/0 79.619%      |
 | Careful:252/4/140/0/76/36  5.995%      |
 | Other  3.321%                          |
 +----------------------------------------+
 | Moves                                  |
 | Fake Out 100.000%                      |
 | Parting Shot 100.000%                  |
 | Flare Blitz 100.000%                   |
 | Protect  6.689%                        |
 | Other 14.599%                          |
 +----------------------------------------+
 | Teammates                              |
 | Gastrodon 91.680%                      |
 | Zacian-Crowned 86.516%                 |
 +----------------------------------------+
 | Checks and Counters                    |
 +----------------------------------------+
 +----------------------------------------+
 | Incineroar                             |
 +----------------------------------------+
 | Raw count: 1200                        |
 +----------------------------------------+
 | Abilities                              |
 | Intimidate 50.000%                     |
 +----------------------------------------+
"""

CHAMPIONS_TEXT = """
+----------------------------------------+
| Rillaboom                              |
+----------------------------------------+
| Raw count: 1410840                     |
+----------------------------------------+
| Spreads                                |
| Adamant:32/32/0/0/2/0 4.411%           |
| Jolly:2/32/0/0/0/32 2.867%             |
+----------------------------------------+
| Moves                                  |
| Grassy Glide 98.654%                   |
| Fake Out 98.649%                       |
+----------------------------------------+
"""

SV_TEXT = """
+----------------------------------------+
| Urshifu-Rapid-Strike                   |
+----------------------------------------+
| Abilities                              |
| Unseen Fist 100.000%                   |
+----------------------------------------+
| Spreads                                |
| Adamant:68/236/20/0/4/180 37.593%      |
+----------------------------------------+
| Moves                                  |
| Surging Strikes 99.992%                |
| Close Combat 97.665%                   |
+----------------------------------------+
| Tera Types                             |
| Ghost 60.453%                          |
| Water 20.454%                          |
+----------------------------------------+
"""


def test_parse_usage_table_reads_battles_and_rows() -> None:
    table = parse_usage_table(USAGE_TEXT)

    assert table.battles == 1827
    assert [row.name for row in table.rows] == ["Incineroar", "Gastrodon"]
    assert table.rows[0].rank == 1
    assert table.rows[0].usage == 83.49422


def test_parse_moveset_merges_duplicate_blocks_from_checks_section() -> None:
    blocks = parse_moveset_text(MOVESET_TEXT)

    assert list(blocks) == ["Incineroar"]
    incineroar = blocks["Incineroar"]
    # Raw count 取最大值，Abilities 不会因为 Checks 区重复块而覆盖
    assert incineroar.raw_count == 1669
    assert incineroar.abilities[0] == ("Intimidate", 99.92)
    assert incineroar.items[0] == ("Shuca Berry", 87.9)
    # 「Other」不进入明细
    assert all(name != "Other" for name, _ in incineroar.items)
    assert incineroar.moves[0] == ("Fake Out", 100.0)
    assert incineroar.spreads[0]["nature"] == "careful"
    assert incineroar.spreads[0]["points"] == [252, 108, 148, 0, 0, 0]
    assert incineroar.teammates[0] == ("Gastrodon", 91.68)


def test_parse_moveset_reads_tera_types_when_present() -> None:
    blocks = parse_moveset_text(SV_TEXT)

    assert blocks["Urshifu-Rapid-Strike"].tera_types[0] == ("Ghost", 60.453)
    assert blocks["Urshifu-Rapid-Strike"].tera_types[1] == ("Water", 20.454)


def test_detect_points_kind() -> None:
    assert detect_points_kind([{"points": [252, 0, 4, 0, 0, 252]}]) == "ev"
    assert detect_points_kind([{"points": [32, 32, 0, 0, 2, 0]}]) == "stat_points"
    # 空配点按 EV 处理（旧格式缺数据时最保守的假设）
    assert detect_points_kind([]) == "ev"


def test_showdown_slug_handles_punctuation() -> None:
    assert showdown_slug("Mr. Mime") == "mr-mime"
    assert showdown_slug("Farfetch'd") == "farfetchd"
    assert showdown_slug("Will-O-Wisp") == "will-o-wisp"
    assert showdown_slug("Type: Null") == "type-null"
    assert showdown_slug("Urshifu-Rapid-Strike") == "urshifu-rapid-strike"


def test_infer_ivs_special_attacker_drops_attack() -> None:
    result = infer_ivs(
        "timid", [4, 0, 0, 252, 0, 252], {"protect", "shadow-ball"}, points_kind="ev"
    )

    assert result is not None
    assert result["ivs"]["attack"] == 0
    assert result["ivs"]["speed"] == 31
    assert result["inferred"] is True
    assert result["reasons"]


def test_infer_ivs_trick_room_drops_speed() -> None:
    result = infer_ivs(
        "modest", [252, 0, 4, 252, 0, 0], {"trick-room", "protect"}, points_kind="ev"
    )

    assert result is not None
    assert result["ivs"]["speed"] == 0


def test_infer_ivs_returns_none_for_stat_points() -> None:
    assert infer_ivs("adamant", [32, 32, 0, 0, 2, 0], set(), points_kind="stat_points") is None


def test_infer_ivs_default_is_all_31() -> None:
    result = infer_ivs("adamant", [252, 252, 4, 0, 0, 0], {"earthquake"}, points_kind="ev")

    assert result is not None
    assert set(result["ivs"].values()) == {31}
    assert result["reasons"] == []
