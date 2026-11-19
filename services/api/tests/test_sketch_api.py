"""图图犬「写生」的招式范围与校验。

图图犬（#235）的招式表里只有「写生」，但写生能复制本版本绝大多数招式。
旧实现直接把招式表当合法招式 → 建队页只有 1 个选项。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.db.models import DoubleFormat, DoublePokemonStat, MoveLearner, MoveReference
from app.repositories import pokemon_repo

POKEMON_URL = "/api/v1/pokemon"
TEAMS_URL = "/api/v1/teams"


async def _seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            DoubleFormat(
                key="sv",
                label="朱紫 · 测试",
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
                dex_number=235,
                name_en="smeargle",
                name_zh="图图犬",
                types_json=json.dumps(["normal"]),
                stats_json="{}",
                abilities_json=json.dumps(
                    [{"name": "own-tempo", "is_hidden": False}], ensure_ascii=False
                ),
                evolution_json="{}",
                moves_json=json.dumps(
                    {
                        "version_groups": {
                            "scarlet-violet": {
                                "methods": {"level-up": [{"name": "sketch", "level": 1}]}
                            }
                        }
                    }
                ),
                source="pokeapi",
                sprite_path="sprites/235.png",
            )
        )
        # 其它宝可梦会用的招式（写生来源）+ 一个不能写生的招式
        for move, zh in (
            ("spore", "蘑菇孢子"),
            ("follow-me", "看我嘛"),
            ("fake-out", "击掌奇袭"),
            ("dark-void", "暗黑洞"),
            ("sketch", "写生"),
        ):
            session.add(MoveReference(name=move, zh=zh, type="normal", damage_class="status"))
            session.add(
                MoveLearner(
                    move_name=move,
                    dex_number=235 if move == "sketch" else 999,
                    version_groups_json="{}",
                    methods_key="scarlet-violet:level-up",
                )
            )
        session.add(
            DoublePokemonStat(
                format_key="sv",
                showdown_name="Smeargle",
                dex_number=235,
                rank=22,
                usage=10.6,
                raw_count=1,
                abilities_json=json.dumps([["own-tempo", 100.0]]),
                items_json="[]",
                moves_json=json.dumps(
                    [["follow-me", 93.0], ["spore", 92.0], ["dark-void", 1.0]]
                ),
                spreads_json="[]",
                teammates_json="[]",
                tera_types_json="[]",
            )
        )
        await session.commit()


async def test_smeargle_legal_moves_expand_to_sketchable(client: AsyncClient) -> None:
    await _seed()
    payload = (
        await client.get(f"{POKEMON_URL}/235/team-options", params={"format": "sv"})
    ).json()
    moves = {move["slug"] for move in payload["legal_moves"]}

    assert {"spore", "follow-me", "fake-out", "sketch"} <= moves
    # 不能写生的招式不在候选里
    assert "dark-void" not in moves


async def test_smeargle_validation_accepts_sketched_moves(client: AsyncClient) -> None:
    await _seed()
    response = (
        await client.post(
            f"{TEAMS_URL}/validate",
            json={
                "name": "图图犬",
                "format_key": "sv",
                "members": [
                    {
                        "dex_number": 235,
                        "showdown_name": "Smeargle",
                        "ability": "Own Tempo",
                        "nature": "timid",
                        "evs": [4, 0, 0, 0, 252, 252],
                        "moves": ["Spore", "Follow Me", "Fake Out", "Sketch"],
                        "level": 50,
                        "language": "CHS",
                    }
                ],
            },
        )
    ).json()
    assert response["ok"] is True, response["issues"]


async def test_smeargle_validation_rejects_non_sketchable(client: AsyncClient) -> None:
    await _seed()
    response = (
        await client.post(
            f"{TEAMS_URL}/validate",
            json={
                "name": "图图犬",
                "format_key": "sv",
                "members": [
                    {
                        "dex_number": 235,
                        "showdown_name": "Smeargle",
                        "ability": "Own Tempo",
                        "nature": "timid",
                        "evs": [4, 0, 0, 0, 252, 252],
                        "moves": ["Dark Void", "Spore", "Protect", "Follow Me"],
                        "level": 50,
                        "language": "CHS",
                    }
                ],
            },
        )
    ).json()
    assert response["ok"] is False
    assert any("Dark Void" in issue["message"] for issue in response["issues"])
