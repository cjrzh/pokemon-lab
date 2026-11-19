"""建队的形态选择（洛托姆、厄诡椪、超级进化等）测试。

覆盖三件事：
  1. `/team-options` 在形态多时不再 500（旧实现 `scalar_one_or_none` 会炸）；
  2. 不传 form 时自动选使用率最高的形态，传 form 时按形态返回招式 / 特性；
  3. 保存队伍后按 `showdown_name` 反查形态，导出名称正确。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.db.models import DoubleFormat, DoublePokemonStat, PokemonForm, PokemonFormMove
from app.repositories import pokemon_repo
from app.services import form_service

TEAMS_URL = "/api/v1/teams"
POKEMON_URL = "/api/v1/pokemon"


async def _seed(client: AsyncClient) -> None:
    """一个图鉴编号（洛托姆 #479）+ 五个形态 + 每个形态一条统计。"""
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            DoubleFormat(
                key="sv",
                label="朱紫 · VGC 测试",
                short_label="朱紫",
                game="Scarlet & Violet",
                ruleset="VGC",
                smogon_format="gen9vgc2026regi",
                month="2026-04",
                cutoff=1630,
                points_kind="ev",
                battles=1,
                note="",
                source_url=None,
                trade_prefix="!tradeSV",
                default_level=50,
            )
        )
        session.add(
            pokemon_repo.Pokemon(
                dex_number=479,
                name_en="rotom",
                name_zh="洛托姆",
                types_json=json.dumps(["electric", "ghost"]),
                stats_json=json.dumps({"hp": 50}),
                abilities_json=json.dumps(
                    [{"name": "levitate", "is_hidden": False}], ensure_ascii=False
                ),
                evolution_json="{}",
                moves_json=json.dumps(
                    {
                        "version_groups": {
                            "scarlet-violet": {
                                "methods": {
                                    "level-up": [
                                        {"name": "thunder-shock", "level": 1},
                                        {"name": "thunderbolt", "level": 40},
                                        {"name": "volt-switch", "level": 45},
                                        {"name": "thunder-wave", "level": 1},
                                        {"name": "protect", "level": 1},
                                    ]
                                }
                            }
                        }
                    }
                ),
                source="pokeapi",
                sprite_path="sprites/479.png",
            )
        )
        # 形态：清洗 / 加热（机制不同，各有一条统计）
        forms = {
            "rotom-wash": (["electric", "water"], "清洗洛托姆", "hydro-pump"),
            "rotom-heat": (["electric", "fire"], "加热洛托姆", "overheat"),
        }
        for index, (name, (types, zh, _move)) in enumerate(forms.items(), start=1):
            session.add(
                PokemonForm(
                    name=name,
                    dex_number=479,
                    suffix=name.split("-", 1)[1],
                    zh=zh,
                    types_json=json.dumps(types),
                    stats_json="{}",
                    abilities_json=json.dumps(
                        [{"name": "levitate", "is_hidden": False}], ensure_ascii=False
                    ),
                    position=index,
                    sprite_path=f"forms/sprites/{name}.png",
                )
            )
        # 形态专属招式
        for form, move in (("rotom-wash", "hydro-pump"), ("rotom-heat", "overheat")):
            session.add(
                PokemonFormMove(
                    form_name=form,
                    dex_number=479,
                    version_group="scarlet-violet",
                    methods_json=json.dumps({"level-up": [{"name": move, "level": 1}]}),
                )
            )
        # 统计：清洗 20%、加热 5%、默认 0.5%
        for name, usage, rank in (
            ("Rotom-Wash", 20.0, 10),
            ("Rotom-Heat", 5.0, 100),
            ("Rotom", 0.5, 400),
        ):
            session.add(
                DoublePokemonStat(
                    format_key="sv",
                    showdown_name=name,
                    dex_number=479,
                    rank=rank,
                    usage=usage,
                    raw_count=1,
                    abilities_json=json.dumps([["levitate", 100.0]]),
                    items_json="[]",
                    moves_json=json.dumps([[name.lower(), 100.0]]),
                    spreads_json="[]",
                    teammates_json="[]",
                    tera_types_json="[]",
                )
            )
        await session.commit()


async def test_team_options_does_not_crash_with_multiple_forms(client: AsyncClient) -> None:
    """旧实现会抛 MultipleResultsFound（建队页打开洛托姆 500 的根因）。"""
    await _seed(client)
    response = await client.get(f"{POKEMON_URL}/479/team-options", params={"format": "sv"})
    assert response.status_code == 200
    payload = response.json()

    # 不传 form：自动选使用率最高的清洗洛托姆
    assert payload["showdown_name"] == "Rotom-Wash"
    assert payload["form"] == "rotom-wash"
    assert payload["types"] == ["electric", "water"]

    # 形态清单按使用率降序，默认形态也在里面
    forms = [(item["form"], item["showdown_name"]) for item in payload["forms"]]
    assert forms[0] == ("rotom-wash", "Rotom-Wash")
    assert forms[1] == ("rotom-heat", "Rotom-Heat")
    assert (None, "Rotom") in forms


async def test_team_options_specific_form_uses_its_moves(client: AsyncClient) -> None:
    await _seed(client)
    payload = (
        await client.get(
            f"{POKEMON_URL}/479/team-options",
            params={"format": "sv", "form": "rotom-heat"},
        )
    ).json()

    assert payload["showdown_name"] == "Rotom-Heat"
    assert payload["form"] == "rotom-heat"
    assert payload["types"] == ["electric", "fire"]
    moves = {move["slug"] for move in payload["legal_moves"]}
    assert "overheat" in moves
    # 清洗形态的专属招式不能出现在加热形态里
    assert "hydro-pump" not in moves
    assert payload["recommended"]["showdown_name"] == "Rotom-Heat"


async def test_team_options_explicit_default_form(client: AsyncClient) -> None:
    await _seed(client)
    payload = (
        await client.get(
            f"{POKEMON_URL}/479/team-options",
            params={"format": "sv", "form": "default"},
        )
    ).json()

    assert payload["form"] is None
    assert payload["showdown_name"] == "Rotom"
    # 默认形态的招式来自主表（含进化链合并）
    moves = {move["slug"] for move in payload["legal_moves"]}
    assert "thunderbolt" in moves


async def test_team_options_rejects_unknown_form(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.get(
        f"{POKEMON_URL}/479/team-options",
        params={"format": "sv", "form": "rotom-nope"},
    )
    assert response.status_code == 422


async def test_saved_team_returns_form_from_showdown_name(client: AsyncClient) -> None:
    """已保存队伍只存 `Rotom-Wash`；详情接口要反查出本地形态。"""
    await _seed(client)
    created = (
        await client.post(
            f"{TEAMS_URL}",
            json={
                "name": "洛托姆测试",
                "format_key": "sv",
                "members": [
                    {
                        "dex_number": 479,
                        "showdown_name": "Rotom-Wash",
                        "item": "Sitrus Berry",
                        "ability": "Levitate",
                        "nature": "calm",
                        "evs": [252, 0, 0, 0, 252, 4],
                        "moves": ["Hydro Pump", "Volt Switch", "Thunderbolt", "Thunder Wave"],
                        "level": 50,
                        "language": "CHS",
                    }
                ],
            },
        )
    ).json()
    assert created["members"][0]["form"] == "rotom-wash"

    # 导出用 Showdown 名（不是 PokéAPI 的 `rotom-wash`）
    exported = (await client.get(f"{TEAMS_URL}/{created['id']}/showdown")).json()
    assert "Rotom-Wash @ Sitrus Berry" in exported["text"]


def test_form_showdown_mapping_covers_all_local_forms() -> None:
    """`data/forms/showdown.json` 必须覆盖全部本地形态（生成脚本的产物）。"""
    mapping = form_service.load_form_showdown_map()
    assert mapping, "缺少 data/forms/showdown.json：请运行 scripts/gen_form_showdown.py"
    for form, showdown in (
        ("rotom-wash", "Rotom-Wash"),
        ("rotom-heat", "Rotom-Heat"),
        ("ogerpon-wellspring-mask", "Ogerpon-Wellspring"),
        ("indeedee-female", "Indeedee-F"),
        ("urshifu-rapid-strike", "Urshifu-Rapid-Strike"),
        ("charizard-mega-y", "Charizard-Mega-Y"),
    ):
        assert mapping.get(form) == showdown
    # 反查：Showdown 名 → 本地形态
    assert form_service.form_for_showdown_name("Rotom-Wash") == "rotom-wash"


async def test_default_forms_are_not_returned_as_form(client: AsyncClient) -> None:
    """默认形态不能回传 `form`：前端会拿它请求 `?form=garchomp` → 422。

    「建队到一半跳走再回来」时详情接口会把每个成员反查一遍；旧实现把默认形态也
    当成形态返回，编辑器随即请求非法形态，显示「无法加载该宝可梦的建队选项」。
    """
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        # 默认形态（洛托姆本身）没有 pokemon_form 记录
        session.add(
            pokemon_repo.Pokemon(
                dex_number=445,
                name_en="garchomp",
                name_zh="烈咬陆鲨",
                types_json=json.dumps(["dragon", "ground"]),
                stats_json="{}",
                abilities_json=json.dumps(
                    [{"name": "rough-skin", "is_hidden": True}], ensure_ascii=False
                ),
                evolution_json="{}",
                moves_json=json.dumps(
                    {
                        "version_groups": {
                            "scarlet-violet": {
                                "methods": {"level-up": [{"name": "earthquake", "level": 1}]}
                            }
                        }
                    }
                ),
                source="pokeapi",
                sprite_path="sprites/445.png",
            )
        )
        await session.commit()

    created = (
        await client.post(
            f"{TEAMS_URL}",
            json={
                "name": "形态回显",
                "format_key": "sv",
                "members": [
                    {
                        "dex_number": 445,
                        "showdown_name": "Garchomp",
                        "ability": "Rough Skin",
                        "nature": "jolly",
                        "evs": [4, 252, 0, 0, 0, 252],
                        "moves": ["Earthquake"],
                        "level": 50,
                        "language": "CHS",
                    },
                    {
                        "dex_number": 479,
                        "showdown_name": "Rotom-Wash",
                        "ability": "Levitate",
                        "nature": "calm",
                        "evs": [252, 0, 0, 0, 252, 4],
                        "moves": ["Hydro Pump", "Volt Switch", "Thunderbolt", "Protect"],
                        "level": 50,
                        "language": "CHS",
                    },
                ],
            },
        )
    ).json()
    forms = {member["showdown_name"]: member["form"] for member in created["members"]}
    # 默认形态返回 `default`（明确选择默认形态），非默认形态正常还原
    assert forms["Garchomp"] == "default"
    assert forms["Rotom-Wash"] == "rotom-wash"

    # 详情接口（跳走再回来的实际调用）同样不能给出非法形态
    detail = (await client.get(f"{TEAMS_URL}/{created['id']}")).json()
    for member in detail["members"]:
        if member["form"] not in (None, "default"):
            response = await client.get(
                f"{POKEMON_URL}/{member['dex_number']}/team-options",
                params={"format": "sv", "form": member["form"]},
            )
            assert response.status_code == 200
