"""双打建队接口测试：CRUD、合法性校验、Showdown 导出与建队选项。"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import DoubleFormat, DoublePokemonStat, ItemReference, MoveReference
from app.repositories import pokemon_repo

TEAMS_URL = "/api/v1/teams"
POKEMON_URL = "/api/v1/pokemon"

def _pokemon(dex: int, name_en: str, name_zh: str, moves: dict, abilities: list[dict]):
    version_groups = {
        vg: {
            "methods": {
                method: [{"name": name, "level": level} for name, level in entries]
            }
        }
        for vg, method_entries in moves.items()
        for method, entries in method_entries.items()
    }
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_zh,
        types_json=json.dumps(["fire"]),
        stats_json=json.dumps({"hp": 78, "attack": 84, "defense": 78, "special-attack": 109,
                               "special-defense": 85, "speed": 100}),
        abilities_json=json.dumps(abilities),
        evolution_json="{}",
        moves_json=json.dumps({"version_groups": version_groups}, ensure_ascii=False),
        source="pokeapi",
        gender_rate=1,
    )


async def _seed(client: AsyncClient) -> None:
    # 标签文件（中英文名）来自仓库 data/doubles/，测试里写一份最小副本，
    # 让「特性下拉框显示中文名、值用 Showdown 英文名」这段逻辑可被覆盖。
    from app.services.doubles_service import reset_labels_cache

    labels_dir = get_settings().data_dir / "doubles"
    labels_dir.mkdir(parents=True, exist_ok=True)
    (labels_dir / "labels.json").write_text(
        json.dumps(
            {
                "abilities": {"blaze": "猛火", "torrent": "激流"},
                "abilities_en": {"blaze": "Blaze", "torrent": "Torrent"},
                "items": {"life-orb": "生命宝珠"},
                "items_en": {"life-orb": "Life Orb"},
                "moves": {},
                "natures": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    reset_labels_cache()

    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                _pokemon(
                    6,
                    "charizard",
                    "喷火龙",
                    {
                        "scarlet-violet": {"level-up": [("flamethrower", 1), ("air-slash", 1)]},
                        "sword-shield": {"machine": [("flamethrower", 0)]},
                    },
                    [{"name": "blaze", "is_hidden": False, "zh": "猛火"}],
                ),
                _pokemon(
                    9,
                    "blastoise",
                    "水箭龟",
                    {"scarlet-violet": {"machine": [("protect", 0), ("surf", 0)]}},
                    [{"name": "torrent", "is_hidden": False, "zh": "激流"}],
                ),
            ]
        )
        session.add_all(
            [
                MoveReference(name="flamethrower", zh="喷射火焰", type="fire",
                              damage_class="special", power=90),
                MoveReference(name="protect", zh="守住", type="normal",
                              damage_class="status"),
                MoveReference(name="surf", zh="冲浪", type="water",
                              damage_class="special", power=90),
                ItemReference(name="life-orb", zh="生命宝珠", name_en="Life Orb",
                              category="held-items", icon_path="items/life-orb.png"),
            ]
        )
        session.add(
            DoubleFormat(
                key="sv",
                label="朱紫 · VGC",
                short_label="朱紫",
                game="Scarlet & Violet",
                ruleset="VGC",
                smogon_format="gen9vgc2026regi",
                month="2026-04",
                cutoff=1630,
                points_kind="ev",
                trade_prefix="!tradeSV",
                default_level=50,
            )
        )
        session.add(
            DoublePokemonStat(
                format_key="sv",
                showdown_name="Charizard",
                dex_number=6,
                rank=10,
                usage=12.5,
                raw_count=1000,
                abilities_json=json.dumps([["blaze", 90.0]]),
                items_json=json.dumps([["life-orb", 60.0]]),
                moves_json=json.dumps([["flamethrower", 80.0], ["air-slash", 40.0]]),
                spreads_json=json.dumps(
                    [{"nature": "timid", "points": [4, 0, 0, 252, 0, 252], "pct": 30.0}]
                ),
                teammates_json="[]",
                tera_types_json="[]",
            )
        )
        await session.commit()


def _member(dex: int, name: str, **overrides) -> dict:
    payload = {
        "dex_number": dex,
        "showdown_name": name,
        "item": None,
        "ability": None,
        "nature": "timid",
        "evs": [4, 0, 0, 252, 0, 252],
        "ivs": [31, 31, 31, 31, 31, 31],
        "moves": [],
    }
    payload.update(overrides)
    return payload


async def test_create_update_delete_team(client: AsyncClient) -> None:
    await _seed(client)

    created = await client.post(
        TEAMS_URL,
        json={
            "name": "测试队",
            "format_key": "sv",
            "members": [
                _member(6, "Charizard", ability="blaze", item="life-orb",
                        moves=["flamethrower", "air-slash"]),
                _member(9, "Blastoise", ability="torrent", moves=["protect", "surf"]),
            ],
        },
    )
    assert created.status_code == 200, created.text
    team = created.json()
    team_id = team["id"]
    assert team["name"] == "测试队"
    assert team["points_kind"] == "ev"
    assert team["trade_prefix"] == "!tradeSV"
    assert [m["position"] for m in team["members"]] == [0, 1]

    # 列表
    listing = (await client.get(TEAMS_URL)).json()
    assert [t["name"] for t in listing["items"]] == ["测试队"]
    assert {fmt["key"] for fmt in listing["formats"]} == {"sv"}

    # 改名 + 删一只
    updated = await client.put(
        f"{TEAMS_URL}/{team_id}",
        json={"name": "改名后的队", "members": [_member(6, "Charizard", ability="blaze")]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "改名后的队"
    assert len(updated.json()["members"]) == 1

    # 删除
    assert (await client.delete(f"{TEAMS_URL}/{team_id}")).status_code == 204
    assert (await client.get(TEAMS_URL)).json()["items"] == []


async def test_teams_are_shared_not_isolated(client: AsyncClient) -> None:
    """个人自用：队伍对所有访问者可见，不再按浏览器隔离。

    即便请求带着不同的（历史遗留的）X-Owner-Key，也能看到全部队伍。
    """
    await _seed(client)
    await client.post(
        TEAMS_URL,
        json={"name": "唯一的队", "format_key": "sv", "members": [_member(6, "Charizard")]},
    )

    seen = (
        await client.get(TEAMS_URL, headers={"X-Owner-Key": "some-other-browser"})
    ).json()
    assert [t["name"] for t in seen["items"]] == ["唯一的队"]


async def test_duplicate_dex_number_rejected(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        TEAMS_URL,
        json={
            "name": "重复队",
            "format_key": "sv",
            "members": [
                _member(6, "Charizard", item="life-orb"),
                _member(6, "Charizard-Mega-Y", item="charizardite-y"),
            ],
        },
    )
    assert response.status_code == 422
    assert any("重复" in message for message in response.json()["detail"])


async def test_duplicate_item_rejected(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        TEAMS_URL,
        json={
            "name": "重复道具",
            "format_key": "sv",
            "members": [
                _member(6, "Charizard", item="life-orb"),
                _member(9, "Blastoise", item="life-orb"),
            ],
        },
    )
    assert response.status_code == 422
    assert any("相同道具" in message for message in response.json()["detail"])


async def test_illegal_move_rejected(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        TEAMS_URL,
        json={
            "name": "非法招式",
            "format_key": "sv",
            "members": [_member(9, "Blastoise", moves=["flamethrower"])],
        },
    )
    assert response.status_code == 422
    assert any("无法学会" in message for message in response.json()["detail"])


async def test_move_legal_in_another_version_rejected(client: AsyncClient) -> None:
    """flamethrower 在剑盾里合法、在朱紫不对 Blastoise 合法；这里用剑盾 vs 朱紫对照。"""
    await _seed(client)
    # Blastoise 在 sv 只有 protect / surf；
    # 换成剑盾格式则本地没有它的剑盾招式数据 → 跳过校验并给出提示
    response = await client.post(
        f"{TEAMS_URL}/validate",
        json={
            "name": "对照",
            "format_key": "swsh",
            "members": [_member(9, "Blastoise", moves=["surf"])],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["warnings"], "缺少该版本招式数据时应给出提示"


async def test_illegal_ability_rejected(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        TEAMS_URL,
        json={
            "name": "非法特性",
            "format_key": "sv",
            "members": [_member(6, "Charizard", ability="drought")],
        },
    )
    assert response.status_code == 422
    assert any("不是该宝可梦可用的特性" in message for message in response.json()["detail"])


async def test_ev_overflow_rejected(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        TEAMS_URL,
        json={
            "name": "EV 超限",
            "format_key": "sv",
            "members": [_member(6, "Charizard", evs=[252, 252, 252, 0, 0, 0])],
        },
    )
    assert response.status_code == 422
    assert any("合计" in message for message in response.json()["detail"])


async def test_validate_endpoint_reports_ok_and_warnings(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        f"{TEAMS_URL}/validate",
        json={
            "name": "校验",
            "format_key": "sv",
            "members": [_member(6, "Charizard", ability="blaze", moves=["flamethrower"])],
        },
    )
    payload = response.json()
    assert payload["ok"] is True
    assert payload["issues"] == []


async def test_showdown_export_has_trade_prefix(client: AsyncClient) -> None:
    await _seed(client)
    team = (
        await client.post(
            TEAMS_URL,
                json={
                "name": "导出队",
                "format_key": "sv",
                "members": [
                    _member(
                        6,
                        "Charizard",
                        ability="Blaze",
                        item="Life Orb",
                        moves=["Flamethrower"],
                        shiny=True,
                        tera_type="Fire",
                        gender="F",
                    ),
                ],
            },
        )
    ).json()

    payload = (await client.get(f"{TEAMS_URL}/{team['id']}/showdown")).json()
    text = payload["text"]
    assert payload["trade_prefix"] == "!tradeSV"
    assert text.split("\n")[0] == "!tradeSV"
    assert "Charizard (F) @ Life Orb" in text
    assert "Ability: Blaze" in text
    assert "Tera Type: Fire" in text
    assert "- Flamethrower" in text
    assert "Timid Nature" in text
    assert "EVs: 4 HP / 252 SpA / 252 Spe" in text
    # IV 全 31 时不输出 IV 行
    assert "IVs:" not in text


async def test_showdown_export_without_prefix_for_champions(client: AsyncClient) -> None:
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        from app.db.models import DoubleFormat

        session.add(
            DoubleFormat(
                key="champions",
                label="宝可梦冠军",
                short_label="冠军",
                game="Pokémon Champions",
                ruleset="VGC",
                smogon_format="gen9champions",
                month="2026-09",
                cutoff=1760,
                points_kind="stat_points",
                trade_prefix=None,
                default_level=50,
            )
        )
        await session.commit()

    team = (
        await client.post(
            TEAMS_URL,
                json={
                "name": "冠军队",
                "format_key": "champions",
                "members": [_member(6, "Charizard", evs=[32, 0, 0, 32, 0, 2], ivs=None)],
            },
        )
    ).json()

    payload = (await client.get(f"{TEAMS_URL}/{team['id']}/showdown")).json()
    assert payload["trade_prefix"] is None
    assert payload["text"].split("\n")[0].startswith("Charizard")
    assert "EVs: 32 HP / 32 SpA / 2 Spe" in payload["text"]


async def test_unknown_team_404(client: AsyncClient) -> None:
    await _seed(client)
    assert (await client.get(f"{TEAMS_URL}/999")).status_code == 404
    assert (await client.delete(f"{TEAMS_URL}/999")).status_code == 404


async def test_dynamax_level_saved_and_exported_for_swsh(client: AsyncClient) -> None:
    """极巨化等级落库并导出到 Showdown 代码（仅在剑盾格式）。"""
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        from app.db.models import DoubleFormat

        session.add(
            DoubleFormat(
                key="swsh",
                label="剑盾 · VGC 2022",
                short_label="剑盾",
                game="Sword & Shield",
                ruleset="VGC 2022",
                smogon_format="gen8vgc2022",
                month="2022-11",
                cutoff=1630,
                points_kind="ev",
                trade_prefix="!tradeSWSH",
                default_level=50,
            )
        )
        await session.commit()

    created = (
        await client.post(
            TEAMS_URL,
            json={
                "name": "极巨化队",
                "format_key": "swsh",
                "members": [
                    _member(6, "Charizard", ability="blaze", moves=["flamethrower"],
                            dynamax_level=7),
                    _member(9, "Blastoise", ability="torrent", moves=["surf"],
                            dynamax_level=10),
                ],
            },
        )
    ).json()
    assert [m["dynamax_level"] for m in created["members"]] == [7, 10]

    text = (await client.get(f"{TEAMS_URL}/{created['id']}/showdown")).json()["text"]
    # 剑盾每只都写出极巨化等级：非默认 7，未设置按默认 10
    assert "Dynamax Level: 7" in text
    assert "Dynamax Level: 10" in text
    assert text.count("Dynamax Level") == 2
    # 剑盾导出不带语言标记
    assert "Language:" not in text

    # 详情接口同样带回，重新打开编辑不丢
    detail = (await client.get(f"{TEAMS_URL}/{created['id']}")).json()
    assert detail["members"][0]["dynamax_level"] == 7


async def test_dynamax_level_rejects_out_of_range(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        TEAMS_URL,
        json={
            "name": "坏极巨化",
            "format_key": "sv",
            "members": [_member(6, "Charizard", dynamax_level=11)],
        },
    )
    assert response.status_code == 422


async def test_gigantamax_saved_exported_and_rejected_outside_swsh(
    client: AsyncClient,
) -> None:
    """超极巨化：剑盾可保存并导出 `Gigantamax: Yes`；朱紫拒绝。"""
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        from app.db.models import DoubleFormat

        session.add(
            DoubleFormat(
                key="swsh",
                label="剑盾 · VGC 2022",
                short_label="剑盾",
                game="Sword & Shield",
                ruleset="VGC 2022",
                smogon_format="gen8vgc2022",
                month="2022-11",
                cutoff=1630,
                points_kind="ev",
                trade_prefix="!tradeSWSH",
                default_level=50,
            )
        )
        await session.commit()

    created = (
        await client.post(
            TEAMS_URL,
            json={
                "name": "超极巨化队",
                "format_key": "swsh",
                "members": [
                    _member(6, "Charizard", ability="blaze", moves=["flamethrower"],
                            dynamax_level=10, gigantamax=True),
                ],
            },
        )
    ).json()
    assert created["members"][0]["gigantamax"] is True

    text = (await client.get(f"{TEAMS_URL}/{created['id']}/showdown")).json()["text"]
    assert "Gigantamax: Yes" in text
    # 极巨化等级显式写出（默认 10），复制出去的代码带完整参数
    assert "Dynamax Level: 10" in text
    # 超极巨化紧跟在极巨化等级之后
    lines = [line.rstrip() for line in text.splitlines()]
    assert lines[lines.index("Dynamax Level: 10") + 1] == "Gigantamax: Yes"

    # 详情接口带回，重新打开编辑不丢
    detail = (await client.get(f"{TEAMS_URL}/{created['id']}")).json()
    assert detail["members"][0]["gigantamax"] is True

    # 朱紫没有超极巨化：拒绝
    rejected = await client.post(
        TEAMS_URL,
        json={
            "name": "朱紫超极巨化",
            "format_key": "sv",
            "members": [
                _member(6, "Charizard", ability="blaze", moves=["flamethrower"],
                        gigantamax=True),
            ],
        },
    )
    assert rejected.status_code == 422
    assert any("超极巨化" in message for message in rejected.json()["detail"])


async def test_gigantamax_rejected_for_species_without_g_form(
    client: AsyncClient,
) -> None:
    """雷丘（#26）没有 G 形态：剑盾格式也不能开启超极巨化。"""
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        from app.db.models import DoubleFormat

        session.add(
            DoubleFormat(
                key="swsh",
                label="剑盾 · VGC 2022",
                short_label="剑盾",
                game="Sword & Shield",
                ruleset="VGC 2022",
                smogon_format="gen8vgc2022",
                month="2022-11",
                cutoff=1630,
                points_kind="ev",
                trade_prefix="!tradeSWSH",
                default_level=50,
            )
        )
        await session.commit()

    member = {
        "dex_number": 26,
        "showdown_name": "Raichu",
        "evs": [0, 0, 0, 0, 0, 0],
        "dynamax_level": 10,
        "gigantamax": True,
    }
    rejected = await client.post(
        TEAMS_URL,
        json={"name": "雷丘超极巨化", "format_key": "swsh", "members": [member]},
    )
    assert rejected.status_code == 422
    assert any("没有超极巨化形态" in message for message in rejected.json()["detail"])


def test_team_options_reports_gigantamax_capability(data_dir) -> None:
    """剑盾的喷火龙有 G 形态：选项里带 can_gigantamax 与 G 招式名。"""
    from app.services import form_service

    capability = form_service.gigantamax_info("Charizard")
    assert capability == {
        "showdown_name": "Charizard",
        "gmax_name": "Charizard-Gmax",
        "gmax_move": "G-Max Wildfire",
    }
    # 没有 G 形态的物种（超梦）返回 None
    assert form_service.gigantamax_info("Mewtwo") is None
    # G 形态名也能反查（去掉 -Gmax）
    assert form_service.gigantamax_info("Charizard-Gmax") == capability


async def test_team_options_form_gmax_echoes_gigantamax(client: AsyncClient) -> None:
    """`form=charizard-gmax`：按默认形态取选项，并回显 `gigantamax=True`。

    前端导入 `Charizard-Gmax` 时用它还原开关；G 形态不是 `pokemon_form` 里的
    可选形态，所以不能按普通形态校验（否则 422）。
    """
    await _seed(client)
    payload = (
        await client.get(
            f"{POKEMON_URL}/6/team-options",
            params={"format": "swsh", "form": "charizard-gmax"},
        )
    ).json()

    assert payload["showdown_name"] == "Charizard"
    assert payload["form"] is None
    assert payload["gigantamax"] is True
    assert payload["can_gigantamax"] is True

    # 明确选默认形态时不回显超极巨化
    plain = (
        await client.get(
            f"{POKEMON_URL}/6/team-options", params={"format": "swsh", "form": "default"}
        )
    ).json()
    assert plain["gigantamax"] is False


async def test_team_options_returns_legal_moves_and_recommendations(
    client: AsyncClient,
) -> None:
    await _seed(client)
    payload = (await client.get(f"{POKEMON_URL}/6/team-options", params={"format": "sv"})).json()

    assert payload["dex_number"] == 6
    assert payload["has_stats"] is True
    assert payload["recommended"]["showdown_name"] == "Charizard"

    legal = {move["slug"] for move in payload["legal_moves"]}
    assert {"flamethrower", "air-slash"} <= legal
    assert {ability["slug"] for ability in payload["legal_abilities"]} == {"blaze"}

    # 推荐配置带使用率，供前端默认选择
    assert payload["recommended"]["abilities"][0]["slug"] == "blaze"
    assert payload["recommended"]["items"][0]["slug"] == "life-orb"
    assert payload["recommended"]["moves"][0]["slug"] == "flamethrower"


async def test_team_options_labels_and_items(client: AsyncClient) -> None:
    """特性给 Showdown 英文名（下拉框的值），道具候选来自统计且带图标。"""
    await _seed(client)
    payload = (await client.get(f"{POKEMON_URL}/6/team-options", params={"format": "sv"})).json()

    # 合法特性：本地存 slug，展示用中文名，写进队伍用 Showdown 英文名
    ability = payload["legal_abilities"][0]
    assert ability["slug"] == "blaze"
    assert ability["name"] == "猛火"
    assert ability["name_en"] == "Blaze"

    # 道具候选 = 统计里出现过的那一个（不是全部 257 个），带使用率与图标
    assert [item["slug"] for item in payload["legal_items"]] == ["life-orb"]
    assert payload["legal_items"][0]["pct"] == 60.0
    assert payload["legal_items"][0]["icon_url"] == "/media/items/life-orb.png"


async def test_team_options_without_stats(client: AsyncClient) -> None:
    await _seed(client)
    payload = (await client.get(f"{POKEMON_URL}/9/team-options", params={"format": "sv"})).json()

    assert payload["has_stats"] is False
    assert payload["recommended"] is None
    assert {move["slug"] for move in payload["legal_moves"]} == {"protect", "surf"}
    # 没有统计就没有道具候选，前端回落到道具百科全量列表
    assert payload["legal_items"] == []


# ---------- Showdown 导入 ----------


IMPORT_URL = f"{TEAMS_URL}/import"


async def test_import_showdown_parses_full_set(client: AsyncClient) -> None:
    """从 Showdown 代码导入：字段逐项还原，物种名映射回图鉴编号。"""
    await _seed(client)
    text = """!tradeSV
Zard (Charizard) (F) @ Life Orb
Ability: Blaze
Level: 50
Shiny: Yes
Tera Type: Fire
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
IVs: 0 Atk
- Flamethrower
- Air Slash
"""
    payload = (
        await client.post(
            IMPORT_URL,
                json={"format_key": "sv", "text": text},
        )
    ).json()

    assert payload["problems"] == []
    assert len(payload["members"]) == 1

    member = payload["members"][0]
    assert member["dex_number"] == 6
    assert member["showdown_name"] == "Charizard"
    assert member["nickname"] == "Zard"
    assert member["gender"] == "F"
    assert member["item"] == "Life Orb"
    assert member["ability"] == "Blaze"
    assert member["nature"] == "timid"
    assert member["evs"] == [0, 0, 0, 252, 4, 252]
    assert member["ivs"] == [31, 0, 31, 31, 31, 31]
    assert member["moves"] == ["Flamethrower", "Air Slash"]
    assert member["tera_type"] == "Fire"
    assert member["shiny"] is True
    assert member["level"] == 50
    # 代码里没有 Dynamax Level 行 → 不写入（前端按 Showdown 默认值 10 显示）
    assert member["dynamax_level"] is None
    assert member["gigantamax"] is False


async def test_import_showdown_gigantamax_and_gmax_species(client: AsyncClient) -> None:
    """`Charizard-Gmax` 这类写法解析到物种，并标记超极巨化。"""
    await _seed(client)
    text = """Charizard-Gmax @ Heavy-Duty Boots
Ability: blaze
Level: 50
Dynamax Level: 10
Gigantamax: Yes
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Flamethrower
"""
    payload = (
        await client.post(IMPORT_URL, json={"format_key": "swsh", "text": text})
    ).json()

    assert payload["problems"] == []
    member = payload["members"][0]
    assert member["dex_number"] == 6
    # G 后缀被拆掉：队伍里存物种名，超极巨化用标记表达
    assert member["showdown_name"] == "Charizard"
    assert member["gigantamax"] is True
    assert member["dynamax_level"] == 10

    plain = (
        await client.post(
            IMPORT_URL,
            json={"format_key": "swsh", "text": "Charizard @ Heavy-Duty Boots\n- Flamethrower\n"},
        )
    ).json()
    assert plain["members"][0]["gigantamax"] is False


async def test_import_showdown_reports_unknown_species(client: AsyncClient) -> None:
    """认不出的物种如实列在 problems 里，不猜、也不静默丢弃。"""
    await _seed(client)
    text = """Charizard @ Life Orb
- Flamethrower

Missingno @ Life Orb
- Flamethrower
"""
    payload = (
        await client.post(
            IMPORT_URL,
                json={"format_key": "sv", "text": text},
        )
    ).json()

    assert [member["dex_number"] for member in payload["members"]] == [6]
    assert len(payload["problems"]) == 1
    assert "Missingno" in payload["problems"][0]


async def test_import_showdown_dedupes_by_dex_and_caps_at_six(client: AsyncClient) -> None:
    """同一编号出现两次只保留第一只；超过 6 只的部分忽略并提示。"""
    await _seed(client)
    text = """Charizard @ Life Orb
- Flamethrower

Charizard-Mega-Y @ Charizardite Y
- Flamethrower
"""
    payload = (
        await client.post(
            IMPORT_URL,
                json={"format_key": "sv", "text": text},
        )
    ).json()

    assert len(payload["members"]) == 1
    assert payload["members"][0]["showdown_name"] == "Charizard"
    assert any("只保留第一只" in problem for problem in payload["problems"])


async def test_import_showdown_does_not_persist(client: AsyncClient) -> None:
    """导入只解析不落库：用户确认后才会走 POST /teams。"""
    await _seed(client)
    text = "Charizard @ Life Orb\n- Flamethrower\n"
    await client.post(
        IMPORT_URL,
        json={"format_key": "sv", "text": text},
    )

    teams = (await client.get(TEAMS_URL)).json()
    assert teams["items"] == []


async def test_import_showdown_roundtrip(client: AsyncClient) -> None:
    """导出的 Showdown 代码能被导入还原（导出 / 导入互为逆操作）。"""
    await _seed(client)
    created = (
        await client.post(
            TEAMS_URL,
                json={
                "name": "往返队",
                "format_key": "sv",
                "members": [
                    _member(6, "Charizard", ability="Blaze", item="Life Orb",
                            moves=["Flamethrower", "Air Slash"], shiny=True,
                            tera_type="Fire", gender="F"),
                ],
            },
        )
    ).json()

    exported = (
        await client.get(f"{TEAMS_URL}/{created['id']}/showdown")
    ).json()

    imported = (
        await client.post(
            IMPORT_URL,
                json={"format_key": "sv", "text": exported["text"]},
        )
    ).json()

    assert imported["problems"] == []
    member = imported["members"][0]
    assert member["dex_number"] == 6
    assert member["item"] == "Life Orb"
    assert member["ability"] == "Blaze"
    assert member["nature"] == "timid"
    assert member["evs"] == [4, 0, 0, 252, 0, 252]
    assert member["moves"] == ["Flamethrower", "Air Slash"]
    assert member["tera_type"] == "Fire"
    assert member["gender"] == "F"
    assert member["shiny"] is True


async def test_import_showdown_rejects_bad_format(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        IMPORT_URL,
        json={"format_key": "nope", "text": "Charizard"},
    )
    assert response.status_code == 422


# ---------- 语言 / 批量修改 / 队伍数量 ----------

BATCH_URL = f"{TEAMS_URL}/batch"


async def test_showdown_export_includes_language(client: AsyncClient) -> None:
    """Showdown 代码带 `Language:` 行，缺省 CHS。"""
    await _seed(client)
    created = (
        await client.post(
            TEAMS_URL,
                json={"name": "语言队", "format_key": "sv", "members": [_member(6, "Charizard")]},
        )
    ).json()

    exported = (
        await client.get(f"{TEAMS_URL}/{created['id']}/showdown")
    ).json()
    assert "Language: CHS" in exported["text"]

    # 指定语言后写进代码
    updated = (
        await client.put(
            f"{TEAMS_URL}/{created['id']}",
                json={"members": [_member(6, "Charizard", language="ENG")]},
        )
    ).json()
    assert updated["members"][0]["language"] == "ENG"

    exported = (
        await client.get(f"{TEAMS_URL}/{created['id']}/showdown")
    ).json()
    assert "Language: ENG" in exported["text"]


async def test_import_showdown_language(client: AsyncClient) -> None:
    """代码里没有 Language 行时默认 CHS；有则原样带回。"""
    await _seed(client)

    plain = (
        await client.post(
            IMPORT_URL,
                json={"format_key": "sv", "text": "Charizard @ Life Orb\n- Flamethrower\n"},
        )
    ).json()
    assert plain["members"][0]["language"] == "CHS"

    with_lang = (
        await client.post(
            IMPORT_URL,
                json={
                "format_key": "sv",
                "text": "Charizard @ Life Orb\nLanguage: JPN\n- Flamethrower\n",
            },
        )
    ).json()
    assert with_lang["members"][0]["language"] == "JPN"


async def test_language_rejects_unknown_value(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.post(
        TEAMS_URL,
        json={
            "name": "坏语言",
            "format_key": "sv",
            "members": [_member(6, "Charizard", language="XXX")],
        },
    )
    assert response.status_code == 422


async def test_batch_sets_shiny_level_and_gender(client: AsyncClient) -> None:
    """三个字段一起传；返回改好的成员（不落库）。"""
    await _seed(client)
    response = await client.post(
        BATCH_URL,
        json={
            "members": [_member(6, "Charizard"), _member(9, "Blastoise")],
            "shine": True,
            "level": 100,
            "gender": "F",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["skipped"] == []
    assert all(member["shiny"] is True for member in payload["members"])
    assert all(member["level"] == 100 for member in payload["members"])
    assert all(member["gender"] == "F" for member in payload["members"])

    # 不落库：队伍列表仍是空的
    assert (await client.get(TEAMS_URL)).json()["items"] == []


async def test_batch_gender_keeps_illegal_members(client: AsyncClient) -> None:
    """尼多朗只能雄性：批量设雌性时保持原样并说明。"""
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            pokemon_repo.Pokemon(
                dex_number=32,
                name_en="nidoran-m",
                name_zh="尼多朗",
                types_json=json.dumps(["poison"]),
                stats_json="{}",
                abilities_json="[]",
                evolution_json="{}",
                moves_json="{}",
                source="pokeapi",
                gender_rate=0,
            )
        )
        await session.commit()

    payload = (
        await client.post(
            BATCH_URL,
                json={"members": [_member(32, "Nidoran-M", gender="M")], "gender": "F"},
        )
    ).json()

    assert payload["members"][0]["gender"] == "M"
    assert any("只能为雄性" in item for item in payload["skipped"])


async def test_batch_only_changes_requested_fields(client: AsyncClient) -> None:
    """只传 shine 时，等级 / 性别 / 语言都不动。"""
    await _seed(client)
    payload = (
        await client.post(
            BATCH_URL,
                json={
                "members": [_member(6, "Charizard", level=50, gender="M", language="ESP")],
                "shine": True,
            },
        )
    ).json()

    member = payload["members"][0]
    assert member["shiny"] is True
    assert member["level"] == 50
    assert member["gender"] == "M"
    assert member["language"] == "ESP"


async def test_batch_explicit_null_resets_level_and_gender(client: AsyncClient) -> None:
    """显式传 null = 恢复默认（等级按格式、性别不指定）。"""
    await _seed(client)
    payload = (
        await client.post(
            BATCH_URL,
                json={
                "members": [_member(6, "Charizard", level=100, gender="F")],
                "level": None,
                "gender": None,
            },
        )
    ).json()

    member = payload["members"][0]
    assert member["level"] is None
    assert member["gender"] is None


async def test_teams_have_no_count_limit(client: AsyncClient) -> None:
    """队伍数量不再设上限（旧行为是最多 50 支）。"""
    await _seed(client)
    for index in range(51):
        response = await client.post(
            TEAMS_URL,
                json={
                "name": f"队伍 {index}",
                "format_key": "sv",
                "members": [_member(6, "Charizard")],
            },
        )
        assert response.status_code == 200, response.text

    assert len((await client.get(TEAMS_URL)).json()["items"]) == 51


# ---------------------------------------------------------------------------
# 队伍评价的保存与读取
# ---------------------------------------------------------------------------


async def test_saved_analysis_persists_and_reads_back(
    client: AsyncClient, monkeypatch
) -> None:
    """评价存到队伍上：详情带出快照，列表带 has_analysis 标志。"""
    from app.clients import llm_client

    await _seed(client)

    async def fake_complete(system: str, user: str) -> llm_client.LlmResult:
        return llm_client.LlmResult(text="## 队伍评价\n偏特攻。", model="test-model")

    monkeypatch.setattr(llm_client, "complete", fake_complete)

    created = await client.post(
        TEAMS_URL,
        json={
            "name": "评价队",
            "format_key": "sv",
            "members": [_member(6, "Charizard", ability="blaze", moves=["flamethrower"])],
        },
    )
    team_id = created.json()["id"]
    assert created.json()["analysis"] is None

    # 生成并保存评价
    analyzed = await client.post(
        f"{TEAMS_URL}/{team_id}/analyze"
    )
    assert analyzed.status_code == 200, analyzed.text
    body = analyzed.json()
    stored = body["analysis"]
    assert stored["analysis"]["llm"]["model"] == "test-model"
    assert stored["stale"] is False
    assert stored["generated_at"]
    # 打击面按库里属性算出：喷火龙的火焰能克制草 / 虫
    fire = next(item for item in stored["analysis"]["attack"] if item["type"] == "fire")
    assert "grass" in fire["hits"]

    # 重新拉详情：评价还在
    detail = (await client.get(f"{TEAMS_URL}/{team_id}")).json()
    assert detail["analysis"]["analysis"]["llm"]["text"].startswith("## 队伍评价")

    # 列表：只有标志，没有完整内容
    listing = (await client.get(TEAMS_URL)).json()
    assert listing["items"][0]["has_analysis"] is True


async def test_saved_analysis_marks_stale_after_member_change(
    client: AsyncClient, monkeypatch
) -> None:
    """改过成员后，旧评价标记为过期（stale），但仍能读到。"""
    from app.clients import llm_client

    await _seed(client)
    async def fake_complete(system: str, user: str) -> llm_client.LlmResult:
        return llm_client.LlmResult(text="## 队伍评价\n稳健。", model="test-model")

    monkeypatch.setattr(llm_client, "complete", fake_complete)

    created = await client.post(
        TEAMS_URL,
        json={
            "name": "过期队",
            "format_key": "sv",
            "members": [_member(6, "Charizard", moves=["flamethrower"])],
        },
    )
    team_id = created.json()["id"]
    await client.post(f"{TEAMS_URL}/{team_id}/analyze")

    # 改招式后，评价应对应当前配置失效
    await client.put(
        f"{TEAMS_URL}/{team_id}",
        json={"members": [_member(6, "Charizard", moves=["air-slash"])]},
    )
    detail = (await client.get(f"{TEAMS_URL}/{team_id}")).json()
    assert detail["analysis"]["stale"] is True


async def test_saved_analysis_ignores_only_cosmetic_changes(
    client: AsyncClient, monkeypatch
) -> None:
    """只改昵称 / 语言这类与打击面无关的字段，不把评价标记为过期。"""
    from app.clients import llm_client

    await _seed(client)
    async def fake_complete(system: str, user: str) -> llm_client.LlmResult:
        return llm_client.LlmResult(text="## 队伍评价\n稳健。", model="test-model")

    monkeypatch.setattr(llm_client, "complete", fake_complete)

    created = await client.post(
        TEAMS_URL,
        json={
            "name": "昵称队",
            "format_key": "sv",
            "members": [_member(6, "Charizard", moves=["flamethrower"])],
        },
    )
    team_id = created.json()["id"]
    await client.post(f"{TEAMS_URL}/{team_id}/analyze")

    await client.put(
        f"{TEAMS_URL}/{team_id}",
        json={
            "members": [
                _member(6, "Charizard", moves=["flamethrower"], nickname="火龙", language="ENG")
            ]
        },
    )
    detail = (await client.get(f"{TEAMS_URL}/{team_id}")).json()
    assert detail["analysis"]["stale"] is False


async def test_analyze_saved_team_404_for_missing_team(client: AsyncClient) -> None:
    await _seed(client)
    missing = await client.post(f"{TEAMS_URL}/9999/analyze")
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# 队伍列表排序
# ---------------------------------------------------------------------------


async def test_reorder_teams(client: AsyncClient) -> None:
    """拖拽排序后按提交顺序返回；新队伍插到列表最前面。"""
    await _seed(client)
    created = []
    for index in range(3):
        response = await client.post(
            TEAMS_URL,
            json={
                "name": f"队伍 {index}",
                "format_key": "sv",
                "members": [_member(6, "Charizard")],
            },
        )
        created.append(response.json()["id"])

    ids = [team["id"] for team in (await client.get(TEAMS_URL)).json()["items"]]
    # 新建的队伍依次插到最前面（建完就能在列表顶部看到）
    assert ids == list(reversed(created))

    # 倒序
    reordered = await client.put(
        f"{TEAMS_URL}/order", json={"team_ids": list(reversed(ids))}
    )
    assert reordered.status_code == 200, reordered.text
    assert [team["id"] for team in reordered.json()["items"]] == list(reversed(ids))

    # 再拉一次确认落库
    assert [team["id"] for team in (await client.get(TEAMS_URL)).json()["items"]] == list(
        reversed(ids)
    )


async def test_reorder_ignores_unknown_ids(client: AsyncClient) -> None:
    """不存在的 id 被忽略，而不是 500（另一标签页刚删除的场景）。"""
    await _seed(client)
    created = (
        await client.post(
            TEAMS_URL,
            json={"name": "唯一", "format_key": "sv", "members": [_member(6, "Charizard")]},
        )
    ).json()["id"]

    response = await client.put(
        f"{TEAMS_URL}/order", json={"team_ids": [9999, created, 8888]}
    )
    assert response.status_code == 200, response.text
    assert [team["id"] for team in response.json()["items"]] == [created]


async def test_new_team_goes_to_front_after_reorder(client: AsyncClient) -> None:
    await _seed(client)
    first = (
        await client.post(
            TEAMS_URL,
            json={"name": "A", "format_key": "sv", "members": [_member(6, "Charizard")]},
        )
    ).json()["id"]
    second = (
        await client.post(
            TEAMS_URL,
            json={"name": "B", "format_key": "sv", "members": [_member(6, "Charizard")]},
        )
    ).json()["id"]

    # 先倒序，再新建
    await client.put(f"{TEAMS_URL}/order", json={"team_ids": [second, first]})
    third = (
        await client.post(
            TEAMS_URL,
            json={"name": "C", "format_key": "sv", "members": [_member(6, "Charizard")]},
        )
    ).json()["id"]

    ids = [team["id"] for team in (await client.get(TEAMS_URL)).json()["items"]]
    assert ids == [third, second, first]
