"""建队校验上下文测试：进化链上前代招式的继承。

规则背景：一只宝可梦保留进化前形态学过的招式，所以合法性 = 自己的招式表 ∪
进化链上前代的招式表。Showdown 官方校验器用的是同一思路（`getFullLearnset`）。
真实案例：雷丘的 Fake Out 来自皮丘（蛋招式），只看雷丘自己的表会误判为非法。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.domain.team_rules import validate_team
from app.repositories import pokemon_repo
from app.services import team_service

POKEMON_URL = "/api/v1/pokemon"
TEAMS_URL = "/api/v1/teams"

CHAIN = {
    "chain_id": "10",
    "chain": {
        "name": "pichu",
        "dex": 172,
        "detail": None,
        "evolves_to": [
            {
                "name": "pikachu",
                "dex": 25,
                "detail": "亲密度 ≥ 220",
                "evolves_to": [
                    {"name": "raichu", "dex": 26, "detail": "使用雷之石", "evolves_to": []}
                ],
            }
        ],
    },
}


def _pokemon(dex: int, name_en: str, moves: dict[str, dict[str, list[tuple[str, int]]]]):
    version_groups = {
        vg: {"methods": {method: [{"name": n, "level": lv} for n, lv in entries]}}
        for vg, methods in moves.items()
        for method, entries in methods.items()
    }
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_en,
        types_json=json.dumps(["electric"]),
        stats_json=json.dumps({"hp": 60}),
        abilities_json=json.dumps([{"name": "static", "is_hidden": False}]),
        evolution_json=json.dumps(CHAIN),
        moves_json=json.dumps({"version_groups": version_groups}),
        source="pokeapi",
    )


async def _seed(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                # 皮丘：Fake Out / Encore 是蛋招式
                _pokemon(
                    172,
                    "pichu",
                    {"scarlet-violet": {"egg": [("fake-out", 0), ("encore", 0)]}},
                ),
                # 雷丘：自己的表里只有 encore，没有 fake-out
                _pokemon(
                    26,
                    "raichu",
                    {"scarlet-violet": {"machine": [("encore", 0), ("protect", 0)]}},
                ),
            ]
        )
        await session.commit()


def test_ancestor_dex_numbers_walks_evolution_chain() -> None:
    """进化链上的前代按「最早 → 直接前身」顺序返回，不含自己。"""
    payload = json.dumps(CHAIN)
    assert team_service.ancestor_dex_numbers(payload, 26) == [172, 25]
    assert team_service.ancestor_dex_numbers(payload, 25) == [172]
    assert team_service.ancestor_dex_numbers(payload, 172) == []


def test_ancestor_dex_numbers_handles_missing_data() -> None:
    assert team_service.ancestor_dex_numbers("{}", 26) == []
    assert team_service.ancestor_dex_numbers("not json", 26) == []
    # 编号不在链上（如另一条进化链）时返回空，不误伤
    assert team_service.ancestor_dex_numbers(json.dumps(CHAIN), 999) == []


async def test_validation_context_inherits_pre_evolution_moves(client: AsyncClient) -> None:
    """雷丘的 Fake Out 来自皮丘，合法范围应包含前代招式。"""
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        context = await team_service.build_validation_context(session, "sv", [26])

    legal = context.legal_moves[26]
    assert "fake-out" in legal  # 来自皮丘的蛋招式
    assert "encore" in legal  # 自己就会
    assert "protect" in legal


async def test_validation_accepts_inherited_move(client: AsyncClient) -> None:
    """端到端：含 Fake Out 的雷丘能通过校验并保存。"""
    await _seed(client)
    payload = {
        "name": "雷丘队",
        "format_key": "sv",
        "members": [
            {
                "dex_number": 26,
                "showdown_name": "Raichu",
                "ability": "Static",
                "nature": "timid",
                "evs": [0, 0, 0, 252, 4, 252],
                "moves": ["Fake Out", "Encore", "Protect"],
            }
        ],
    }
    response = await client.post(
        TEAMS_URL, json=payload
    )
    assert response.status_code == 200, response.text


async def test_validation_still_rejects_unknown_move(client: AsyncClient) -> None:
    """继承前代招式不等于放宽一切：链上没人会的招仍被拒绝。"""
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        context = await team_service.build_validation_context(session, "sv", [26])

    result = validate_team(
        [
            {
                "dex_number": 26,
                "showdown_name": "Raichu",
                "moves": ["hydro-pump"],
                "evs": [0] * 6,
            }
        ],
        points_kind="ev",
        legal_moves=context.legal_moves,
        legal_abilities=context.legal_abilities,
    )
    assert not result.ok
    assert any("hydro-pump" in issue.message for issue in result.issues)


async def test_validation_does_not_inherit_from_descendants(client: AsyncClient) -> None:
    """只向进化链上游继承：皮丘不该获得雷丘独有的招式。"""
    await _seed(client)
    factory = get_session_factory()
    async with factory() as session:
        context = await team_service.build_validation_context(session, "sv", [172])

    # protect 只在雷丘自己的表里；皮丘不能「反向继承」
    assert "fake-out" in context.legal_moves[172]
    assert "protect" not in context.legal_moves[172]
