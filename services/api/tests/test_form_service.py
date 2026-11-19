"""形态数据的解析 / 比较 / 标签测试（不访问网络）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from sync_forms import parse_range  # noqa: E402

from app.repositories import pokemon_repo  # noqa: E402
from app.services import form_service  # noqa: E402


def _variety_payload(
    *,
    name: str = "urshifu-rapid-strike",
    form_name: str = "rapid-strike",
    types: list[str] | None = None,
    stats: dict[str, int] | None = None,
    abilities: list[tuple[str, bool]] | None = None,
    height: int = 19,
    weight: int = 1050,
) -> dict:
    return {
        "name": name,
        "forms": [{"form_name": form_name, "url": "https://pokeapi.co/api/v2/pokemon-form/1/"}],
        "types": [{"type": {"name": t}} for t in (types or ["fighting", "water"])],
        "stats": [
            {"base_stat": value, "stat": {"name": key}}
            for key, value in (
                stats
                or {
                    "hp": 100,
                    "attack": 130,
                    "defense": 100,
                    "special-attack": 63,
                    "special-defense": 60,
                    "speed": 97,
                }
            ).items()
        ],
        "abilities": [
            {"ability": {"name": ability_name}, "is_hidden": hidden}
            for ability_name, hidden in (abilities or [("unseen-fist", False)])
        ],
        "height": height,
        "weight": weight,
        "sprites": {
            "front_default": f"https://example.test/sprites/{name}.png",
            "other": {
                "official-artwork": {"front_default": f"https://example.test/artwork/{name}.png"}
            },
        },
    }


def _base_pokemon(
    *,
    types: list[str] | None = None,
    stats: dict[str, int] | None = None,
    abilities: list[dict] | None = None,
    height: int = 19,
    weight: int = 1050,
) -> pokemon_repo.Pokemon:
    return pokemon_repo.Pokemon(
        dex_number=892,
        name_en="urshifu-single-strike",
        name_zh="武道熊师",
        types_json=json.dumps(types or ["fighting", "dark"]),
        stats_json=json.dumps(
            stats
            or {
                "hp": 100,
                "attack": 130,
                "defense": 100,
                "special-attack": 63,
                "special-defense": 60,
                "speed": 97,
            }
        ),
        abilities_json=json.dumps(abilities or [{"name": "unseen-fist", "is_hidden": False}]),
        evolution_json="{}",
        moves_json="{}",
        height_dm=height,
        weight_hg=weight,
        source="pokeapi",
    )


def test_parse_variety_extracts_fields() -> None:
    record = form_service.parse_variety(_variety_payload(), base_name="urshifu", position=1)

    assert record["name"] == "urshifu-rapid-strike"
    assert record["suffix"] == "rapid-strike"
    assert json.loads(record["types_json"]) == ["fighting", "water"]
    assert json.loads(record["stats_json"])["attack"] == 130
    assert record["height_dm"] == 19
    assert record["artwork_url"].endswith("artwork/urshifu-rapid-strike.png")


def test_parse_variety_falls_back_to_name_suffix() -> None:
    payload = _variety_payload(name="rotom-wash", form_name="")
    record = form_service.parse_variety(payload, base_name="rotom", position=1)

    assert record["suffix"] == "wash"


def test_differs_from_base_detects_type_change() -> None:
    base = _base_pokemon()
    variety = form_service.parse_variety(_variety_payload(), base_name="urshifu", position=1)

    assert form_service.differs_from_base(variety, base) is True


def test_differs_from_base_is_false_for_cosmetic_only() -> None:
    """属性 / 种族值 / 特性 / 身高体重都相同 → 视为纯外观形态。"""
    base = _base_pokemon(
        types=["fighting", "water"],
        stats={
            "hp": 100,
            "attack": 130,
            "defense": 100,
            "special-attack": 63,
            "special-defense": 60,
            "speed": 97,
        },
        height=19,
        weight=1050,
    )
    variety = form_service.parse_variety(_variety_payload(), base_name="urshifu", position=1)

    assert form_service.differs_from_base(variety, base) is False


def test_differs_from_base_ignores_height_only() -> None:
    """只差身高（骑乘姿态等）不算机制差异。"""
    base = _base_pokemon(
        types=["fighting", "water"],
        stats={
            "hp": 100,
            "attack": 130,
            "defense": 100,
            "special-attack": 63,
            "special-defense": 60,
            "speed": 97,
        },
        height=25,
        weight=1050,
    )
    variety = form_service.parse_variety(
        _variety_payload(height=35), base_name="urshifu", position=1
    )

    assert form_service.differs_from_base(variety, base) is False


def test_differs_from_base_detects_weight_change() -> None:
    """体重会影响重磅冲撞等招式伤害，算机制差异。"""
    base = _base_pokemon(weight=1000)
    variety = form_service.parse_variety(
        _variety_payload(weight=1050), base_name="urshifu", position=1
    )

    assert form_service.differs_from_base(variety, base) is True


def test_differs_from_base_detects_ability_change() -> None:
    base = _base_pokemon(abilities=[{"name": "blaze", "is_hidden": False}])
    variety = form_service.parse_variety(_variety_payload(), base_name="urshifu", position=1)

    assert form_service.differs_from_base(variety, base) is True


def test_form_label_prefers_specific_then_suffix() -> None:
    document = {
        "suffixes": {"mega": "超级进化", "alola": "阿罗拉的样子"},
        "forms": {"necrozma-dusk": "黄昏之鬃"},
    }

    assert form_service.form_label(document, "necrozma-dusk", "dusk") == "黄昏之鬃"
    assert form_service.form_label(document, "charizard-mega", "mega") == "超级进化"
    assert form_service.form_label(document, "unknown-form", "unknown") is None


def test_form_label_handles_compound_suffix() -> None:
    document = {"suffixes": {"zen": "达摩模式"}, "forms": {}}
    assert form_service.form_label(document, "darmanitan-galar-zen", "galar-zen") == "达摩模式"


def test_repository_form_labels_cover_common_forms() -> None:
    """仓库自带的标签文件至少要覆盖武道熊师与常见的超级进化。"""
    document = form_service.load_form_labels()

    assert form_service.form_label(document, "urshifu-rapid-strike", "rapid-strike") == "连击流"
    assert form_service.form_label(document, "charizard-mega-x", "mega-x") == "超级进化 X"


def test_parse_range() -> None:
    assert parse_range("1-151") == (1, 151)
    with pytest.raises(argparse.ArgumentTypeError):
        parse_range("151-1")
