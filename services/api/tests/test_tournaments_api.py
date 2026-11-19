"""官方赛事：解析器、名称映射与查询接口测试。

不发真实网络：解析器用从 Limitless 页面截取的 HTML 片段；同步逻辑用直接构造的
数据验证（赛事行 → 落库 → 查询）。真实同步由手动验证（见 docs/DATA_SOURCES.md）。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.domain import tournament_catalog
from app.domain import tournament_parser as parser
from app.domain.tournament_showdown import (
    ShowdownDex,
    build_showdown_member,
    choose_ability,
    format_meta,
    normalize_nature,
    normalize_tera,
    render_tournament_showdown,
    split_gigantamax,
)

USAGE_URL = "/api/v1/tournaments"

# 从 https://limitlessvgc.com/tournaments?time=all&show=100&page=1 截取的一行
EVENT_ROW = """
<tr data-date="2026-10-31" data-country="PL"
    data-name="Regional Gdańsk" data-format="m-c"
    data-players="758" data-winner="ES-Javier Varela">
    <td>31 Oct 26</td>
    <td><img class="flag" src="x" alt="PL"></td>
    <td><a href="/tournaments/448">Regional Gdańsk</a></td>
    <td class="landscape-only">758</td>
    <td class="landscape-only"><span class="winner">
        <img class="flag" src="x" alt="ES"><a class="inline" href="/players/5213">Javier Varela</a>
    </span></td>
</tr>
"""

EVENT_PAGE = """
<div class="infobox">
    <div class="infobox-heading">
        Regional Gdańsk
        <img class="flag" src="x" alt="PL" data-tooltip="Poland"> </div>
    <div class="infobox-line">
        31st October 2026 • 758 Players •
        <a href="/pokemon/?time=all&amp;format=m-c">Regulation Set M-C</a>
        <div class="rk9gg"><a href="https://rk9.gg/pairings/x">Pairings</a></div>
    </div>
</div>
<div class="secondary-menu"></div>
<table class="data-table striped">
    <tr data-rank="1" data-name="Javier Varela" data-country="ES">
        <td>1</td><td><a href="/players/5213">Javier Varela</a></td>
        <td><img class="flag" src="x" alt="ES"></td>
        <td><div class="vgc-team">
            <a href="/pokemon/gholdengo" data-tooltip="Gholdengo"><img></a>
            <a href="/pokemon/garchomp" data-tooltip="Garchomp"><img></a>
        </div></td>
        <td><a href="/teams/7472"><i></i></a></td>
    </tr>
</table>
"""

TEAMS_PAGE = """
<section class="tournament-teamlists">
    <div class="tournament-decklist">
        <div class="teamlist-toggle" data-toggle data-target="team-1">1st Javier Varela</div>
        <div class="hidden" data-name="team-1">
            <div class="teamlist"><div class="teamlist-pokemon">
                <div class="pkmn" data-id="charizard">
                    <div class="name"><a href="/pokemon/charizard">Charizard</a></div>
                    <div class="main"><div class="details">
                        <div class="item">Charizardite Y</div>
                        <div class="ability">Ability: Blaze</div>
                        <div class="nature">Modest Nature</div>
                    </div><ul class="moves">
                        <li>Heat Wave</li><li>Weather Ball</li><li>Solar Beam</li><li>Protect</li>
                    </ul></div>
                </div>
                <div class="pkmn" data-id="garchomp">
                    <div class="name"><a href="/pokemon/garchomp">Garchomp</a></div>
                    <div class="main"><div class="details">
                        <div class="item">Rocky Helmet</div>
                        <div class="ability">Ability: Rough Skin</div>
                        <div class="nature">Jolly Nature</div>
                    </div><ul class="moves">
                        <li>Earthquake</li><li>Rock Slide</li><li>Dragon Claw</li><li>Protect</li>
                    </ul></div>
                </div>
                <div class="pkmn" data-id="kingambit">
                    <div class="name"><a href="/pokemon/kingambit">Kingambit</a></div>
                    <div class="details"><div class="ability">Ability: Defiant</div></div>
                    <ul class="moves"><li>Sucker Punch</li></ul>
                </div>
                <div class="pkmn" data-id="rillaboom">
                    <div class="name"><a href="/pokemon/rillaboom">Rillaboom</a></div>
                    <ul class="moves"><li>Wood Hammer</li></ul>
                </div>
                <div class="pkmn" data-id="sneasler">
                    <div class="name"><a href="/pokemon/sneasler">Sneasler</a></div>
                </div>
                <div class="pkmn" data-id="incineroar">
                    <div class="name"><a href="/pokemon/incineroar">Incineroar</a></div>
                </div>
            </div><div class="teamlist-options"><button class="export"></button></div>
        </div>
    </div>
</section>
"""


def _dex() -> ShowdownDex:
    """构造一个最小的 Showdown 索引（只含测试用到的条目）。"""
    pokedex = {
        "charizard": {
            "name": "Charizard",
            "num": 6,
            "abilities": {"0": "Blaze", "H": "Solar Power"},
        },
        "charizardmegay": {
            "name": "Charizard-Mega-Y",
            "num": 6,
            "abilities": {"0": "Drought"},
        },
        "charizardgmax": {
            "name": "Charizard-Gmax",
            "num": 6,
            "baseSpecies": "Charizard",
            "abilities": {"0": "Blaze", "H": "Solar Power"},
        },
        "garchomp": {
            "name": "Garchomp",
            "num": 445,
            "abilities": {"0": "Sand Veil", "H": "Rough Skin"},
        },
        "calyrexice": {
            "name": "Calyrex-Ice",
            "num": 898,
            "abilities": {"0": "As One (Glastrier)"},
        },
    }
    learnsets = {
        "charizard": {"learnset": {"heatwave": ["9M"], "protect": ["9M"]}},
        "garchomp": {"learnset": {"earthquake": ["9M"], "rockslide": ["9M"]}},
    }
    items = {
        "charizardite y": {
            "name": "Charizardite Y",
            "megaStone": {"Charizard": "Charizard-Mega-Y"},
        }
    }
    moves = {
        "heatwave": {"name": "Heat Wave"},
        "protect": {"name": "Protect"},
        "earthquake": {"name": "Earthquake"},
        "rockslide": {"name": "Rock Slide"},
    }
    return ShowdownDex(pokedex=pokedex, items=items, learnsets=learnsets, moves=moves)


# ---------------------------------------------------------------------------
# 解析器
# ---------------------------------------------------------------------------


def test_parse_event_list_splits_winner_country() -> None:
    rows = parser.parse_event_list(EVENT_ROW, event_type="regional")
    assert len(rows) == 1
    row = rows[0]
    assert row.tournament_id == 448
    assert row.date == "2026-10-31"
    assert row.name == "Regional Gdańsk"
    assert row.ruleset == "m-c"
    assert row.players == 758
    assert row.country == "PL"
    assert (row.winner, row.winner_country) == ("Javier Varela", "ES")
    assert row.event_type == "regional"


def test_parse_event_list_handles_empty_page() -> None:
    assert parser.parse_event_list("<html><body>没有赛事</body></html>") == []


def test_parse_event_header() -> None:
    header = parser.parse_event_header(EVENT_PAGE)
    assert header.name == "Regional Gdańsk"
    assert header.date == "31st October 2026"
    assert header.players == 758
    assert header.ruleset == "m-c"
    assert header.country == "PL"
    assert header.event_type == "regional"


def test_parse_standings_with_preview_and_team_link() -> None:
    rows = parser.parse_standings(EVENT_PAGE)
    assert len(rows) == 1
    row = rows[0]
    assert row.rank == 1
    assert row.player == "Javier Varela"
    assert row.country == "ES"
    assert row.species == ["Gholdengo", "Garchomp"]
    assert row.team_id == 7472


def test_parse_teamlists() -> None:
    teams = parser.parse_teamlists(TEAMS_PAGE)
    assert len(teams) == 1
    team = teams[0]
    assert (team.rank, team.player) == (1, "Javier Varela")
    assert len(team.members) == 6
    charizard = team.members[0]
    assert charizard.species_slug == "charizard"
    assert charizard.item == "Charizardite Y"
    assert charizard.ability == "Blaze"
    assert charizard.nature == "Modest"
    assert charizard.moves == ["Heat Wave", "Weather Ball", "Solar Beam", "Protect"]


def test_parse_teamlists_ignores_incomplete_and_missing_pages() -> None:
    assert parser.parse_teamlists("<html>no decklists</html>") == []
    assert parser.parse_teamlists(
        '<section class="tournament-teamlists">There are no available teams</section>'
    ) == []


def test_usage_from_teams_counts_once_per_team() -> None:
    teams = parser.parse_teamlists(TEAMS_PAGE)
    # 同一队里的重复物种只计一次（这里每只不同，验证分母为队数）
    usage = parser.usage_from_teams(teams)
    by_slug = {row.species_slug: row for row in usage}
    assert by_slug["charizard"].count == 1
    assert by_slug["charizard"].share == 100.0
    assert len(usage) == 6

    dup = parser.TeamRow(
        rank=2,
        player="B",
        members=[teams[0].members[0], teams[0].members[0]],
    )
    merged = parser.usage_from_teams([teams[0], dup])
    charizard = next(row for row in merged if row.species_slug == "charizard")
    assert charizard.count == 2
    assert charizard.share == 100.0


# ---------------------------------------------------------------------------
# 名称映射 / Showdown 文本
# ---------------------------------------------------------------------------


def test_species_alias_and_mega_form() -> None:
    dex = _dex()
    species = dex.species("charizard")
    assert species is not None
    mega = dex.mega_form(species, "Charizardite Y")
    assert mega == "Charizard-Mega-Y"
    assert dex.species(mega).dex_number == 6


def test_split_gigantamax() -> None:
    # 后缀（Showdown 物种别名）与前缀（Limitless 显示名）都要认
    assert split_gigantamax("Charizard-Gmax") == ("Charizard", True)
    assert split_gigantamax("Urshifu-Rapid-Strike-Gmax") == ("Urshifu-Rapid-Strike", True)
    assert split_gigantamax("Gigantamax Charizard") == ("Charizard", True)
    assert split_gigantamax("超极巨化 喷火龙") == ("喷火龙", True)
    assert split_gigantamax("Charizard") == ("Charizard", False)
    assert split_gigantamax(None) == (None, False)


def test_build_showdown_member_normalizes_gigantamax() -> None:
    """`-Gmax` 别名收成「基础形态 + 标记」，供 `Gigantamax: Yes` 输出。"""
    member = build_showdown_member(
        _dex(),
        member_slug="charizard-gmax",
        member_label="Charizard-Gmax",
        item=None,
        ability="Blaze",
        nature="Timid",
        tera_type=None,
        moves=["Heat Wave"],
        format_key="swsh",
    )
    assert member["showdown_name"] == "Charizard"
    assert member["dex_number"] == 6
    assert member["gigantamax"] is True
    assert member["dynamax_level"] == 10
    assert member["level"] == 100
    assert member["shiny"] is True

    # Limitless 的显示名是 `Gigantamax Charizard`（前缀），不是 `-Gmax` 后缀
    prefixed = build_showdown_member(
        _dex(),
        member_slug="charizard",
        member_label="Gigantamax Charizard",
        item=None,
        ability="Blaze",
        nature="Timid",
        tera_type=None,
        moves=["Heat Wave"],
        format_key="swsh",
    )
    assert prefixed["showdown_name"] == "Charizard"
    assert prefixed["gigantamax"] is True


def test_choice_ability_parenthesized_suffix() -> None:
    dex = _dex()
    species = dex.species("calyrex-ice")
    assert species is not None
    assert choose_ability(dex, species, "As One (Glastrier)") == "As One (Glastrier)"
    # 未知特性保留原值（不猜）
    assert choose_ability(dex, species, "Rough Skin") == "Rough Skin"


def test_normalize_nature_and_tera() -> None:
    assert normalize_nature("Modest") == "modest"
    assert normalize_nature("Nonsense") is None
    assert normalize_tera("Fairy") == "Fairy"
    assert normalize_tera("Nonsense") is None


def test_format_meta() -> None:
    champions = format_meta("champions")
    assert champions["default_level"] == 50
    assert champions["include_tera"] is False
    sv = format_meta("sv")
    assert sv["include_tera"] is True
    assert format_meta(None)["default_level"] == 50


def test_render_tournament_showdown_omits_evs() -> None:
    text = render_tournament_showdown(
        [
            {
                "showdown_name": "Garchomp",
                "item": "Rocky Helmet",
                "ability": "Rough Skin",
                "nature": "jolly",
                "tera_type": "Steel",
                "moves": ["Earthquake", "Rock Slide"],
                "level": 50,
                "language": "CHS",
            }
        ],
        format_key="sv",
    )
    assert "Garchomp @ Rocky Helmet" in text
    assert "Ability: Rough Skin" in text
    assert "Jolly Nature" in text
    assert "Tera Type: Steel" in text
    assert "EVs:" not in text
    assert "IVs:" not in text
    assert text.endswith("- Rock Slide  ")


def test_render_tournament_showdown_defaults_level_shiny_and_gmax() -> None:
    """官方赛事代码默认 100 级 / 闪光；剑盾带极巨化等级与 `Gigantamax: Yes`。"""
    text = render_tournament_showdown(
        [
            {
                "showdown_name": "Charizard",
                "item": "Heavy-Duty Boots",
                "ability": "Blaze",
                "nature": "timid",
                "moves": ["Heat Wave"],
                "level": 100,
                "shiny": True,
                "dynamax_level": 10,
                "gigantamax": True,
            }
        ],
        format_key="swsh",
    )
    lines = [line.rstrip() for line in text.splitlines()]
    assert lines[0] == "Charizard @ Heavy-Duty Boots"
    assert lines[1] == "Ability: Blaze"
    assert lines[2] == "Level: 100"
    assert lines[3] == "Dynamax Level: 10"
    assert lines[4] == "Gigantamax: Yes"
    assert lines[5] == "Shiny: Yes"
    # 剑盾的复制代码不带语言标记
    assert "Language:" not in text
    assert "Gmax" not in text


def test_render_tournament_showdown_fills_defaults() -> None:
    """成员 dict 缺省时：等级 100、闪光、语言 CHS 仍要写出来。"""
    text = render_tournament_showdown(
        [{"showdown_name": "Garchomp", "moves": []}], format_key="sv"
    )
    assert "Level: 100" in text
    assert "Shiny: Yes" in text
    assert "Language: CHS" in text
    # 朱紫以外的格式没有极巨化行
    assert "Dynamax Level" not in text
    assert "Gigantamax" not in text


def test_render_tournament_showdown_skips_tera_for_other_formats() -> None:
    text = render_tournament_showdown(
        [
            {
                "showdown_name": "Garchomp",
                "ability": "Rough Skin",
                "tera_type": "Steel",
                "moves": [],
                "level": 50,
            }
        ],
        format_key="champions",
    )
    assert "Tera Type" not in text


# ---------------------------------------------------------------------------
# 目录
# ---------------------------------------------------------------------------


def test_catalog_ruleset_mapping() -> None:
    assert tournament_catalog.format_key_for("m-c") == "champions"
    assert tournament_catalog.format_key_for("svf") == "sv"
    assert tournament_catalog.format_key_for("vgc22") == "swsh"
    assert tournament_catalog.format_key_for("vgc17") is None
    assert tournament_catalog.ruleset_label("svf") == "朱紫 Reg F"
    assert tournament_catalog.event_type_label("regional") == "地区赛"
    assert tournament_catalog.infer_event_type("Regional Nice") == "regional"
    assert tournament_catalog.infer_event_type("World Championships 2026") == "worlds"
    assert tournament_catalog.infer_event_type("Something Else") is None


def test_catalog_urls() -> None:
    assert (
        tournament_catalog.tournament_url(448, "teams")
        == "https://limitlessvgc.com/tournaments/448/teams"
    )
    assert "type=worlds" in tournament_catalog.list_url("worlds", 2)


# ---------------------------------------------------------------------------
# 接口（直接构造数据，不联网）
# ---------------------------------------------------------------------------


async def _seed_tournament(client: AsyncClient) -> int:
    from app.db.engine import get_session_factory
    from app.db.models import (
        Tournament,
        TournamentStanding,
        TournamentTeam,
        TournamentTeamMember,
        TournamentUsage,
    )

    factory = get_session_factory()
    async with factory() as session:
        tournament = Tournament(
            source_id=448,
            name="Regional Gdańsk",
            date="2026-10-31",
            ruleset="m-c",
            event_type="regional",
            country="PL",
            players=758,
            winner="Javier Varela",
            winner_country="ES",
            format_key="champions",
            standings_count=1,
            team_count=1,
            has_teamlists=True,
            source_url="https://limitlessvgc.com/tournaments/448",
        )
        session.add(tournament)
        await session.flush()
        session.add(
            TournamentStanding(
                tournament_id=tournament.id,
                rank=1,
                player="Javier Varela",
                country="ES",
                species_json=json.dumps(["Gholdengo", "Garchomp"]),
                source_team_id=7472,
            )
        )
        team = TournamentTeam(
            tournament_id=tournament.id,
            rank=1,
            player="Javier Varela",
            country="ES",
            source_team_id=7472,
            showdown_text="Garchomp @ Rocky Helmet  \nAbility: Rough Skin  ",
            problems_json="[]",
        )
        session.add(team)
        await session.flush()
        session.add(
            TournamentTeamMember(
                team_id=team.id,
                position=0,
                dex_number=445,
                species_slug="garchomp",
                showdown_name="Garchomp",
                item="Rocky Helmet",
                ability="Rough Skin",
                nature="jolly",
                tera_type=None,
                moves_json=json.dumps(["Earthquake", "Rock Slide", "Dragon Claw", "Protect"]),
            )
        )
        session.add(
            TournamentUsage(
                tournament_id=tournament.id,
                species_slug="garchomp",
                dex_number=445,
                showdown_name="Garchomp",
                rank=1,
                count=1,
                share=100.0,
            )
        )
        await session.commit()
        return tournament.id


async def test_list_tournaments(client: AsyncClient) -> None:
    await _seed_tournament(client)
    payload = (await client.get(USAGE_URL)).json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["name"] == "Regional Gdańsk"
    assert item["ruleset_label"] == "宝可梦冠军 Reg M-C（官方赛事）"
    assert item["event_type_label"] == "地区赛"
    assert item["format_key"] == "champions"
    assert payload["years"] == [2026]
    assert payload["rulesets"][0]["identifier"] == "m-c"


async def test_list_tournaments_filters(client: AsyncClient) -> None:
    await _seed_tournament(client)
    assert (await client.get(USAGE_URL, params={"ruleset": "m-c"})).json()["total"] == 1
    assert (await client.get(USAGE_URL, params={"ruleset": "svf"})).json()["total"] == 0
    assert (await client.get(USAGE_URL, params={"event_type": "worlds"})).json()["total"] == 0
    assert (await client.get(USAGE_URL, params={"year": 2025})).json()["total"] == 0
    assert (await client.get(USAGE_URL, params={"q": "Gdańsk"})).json()["total"] == 1
    # 未知规则 / 类型 → 422（而不是静默返回空）
    assert (await client.get(USAGE_URL, params={"ruleset": "nope"})).status_code == 422
    assert (
        await client.get(USAGE_URL, params={"event_type": "nope"})
    ).status_code == 422


async def test_tournament_detail(client: AsyncClient) -> None:
    tournament_id = await _seed_tournament(client)
    payload = (await client.get(f"{USAGE_URL}/{tournament_id}")).json()
    assert payload["tournament"]["name"] == "Regional Gdańsk"
    assert payload["standings"][0]["species"] == ["Gholdengo", "Garchomp"]
    team = payload["teams"][0]
    assert team["members"][0]["showdown_name"] == "Garchomp"
    assert team["members"][0]["gigantamax"] is False
    assert team["members"][0]["dynamax_level"] is None
    # 读取时按当前规则重算文本：默认满级 / 闪光
    assert "Level: 100" in team["showdown_text"]
    assert "Shiny: Yes" in team["showdown_text"]
    assert payload["usage"][0]["share"] == 100.0
    assert (await client.get(f"{USAGE_URL}/9999")).status_code == 404


async def test_tournament_detail_normalizes_legacy_gigantamax_prefix(
    client: AsyncClient,
) -> None:
    """旧库把 `Gigantamax Charizard` 直接存成显示名：读取时按新规则重写。"""
    from app.db.engine import get_session_factory
    from app.db.models import Tournament, TournamentTeam, TournamentTeamMember

    factory = get_session_factory()
    async with factory() as session:
        tournament = Tournament(
            source_id=990001,
            name="Legacy SwSh",
            date="2020-01-18",
            ruleset="swsh2",
            event_type="regional",
            format_key="swsh",
            standings_count=1,
            team_count=1,
            has_teamlists=True,
        )
        session.add(tournament)
        await session.flush()
        team = TournamentTeam(
            tournament_id=tournament.id,
            rank=1,
            player="Legacy",
            showdown_text="Gigantamax Charizard @ Charti Berry  ",
        )
        session.add(team)
        await session.flush()
        session.add(
            TournamentTeamMember(
                team_id=team.id,
                position=0,
                dex_number=6,
                species_slug="charizard-gmax",
                showdown_name="Gigantamax Charizard",
                item="Charti Berry",
                ability="Blaze",
                nature="timid",
                tera_type=None,
                moves_json=json.dumps(["Protect"]),
            )
        )
        await session.flush()
        tournament_id, team_id = tournament.id, team.id
        await session.commit()

    payload = (await client.get(f"{USAGE_URL}/{tournament_id}")).json()
    team = payload["teams"][0]
    member = team["members"][0]
    assert member["showdown_name"] == "Charizard"
    assert member["gigantamax"] is True
    assert member["dynamax_level"] == 10
    assert "Gigantamax Charizard" not in team["showdown_text"]
    assert team["showdown_text"].startswith("Charizard @ Charti Berry")
    assert "Gigantamax: Yes" in team["showdown_text"]
    assert "Level: 100" in team["showdown_text"]
    assert "Shiny: Yes" in team["showdown_text"]

    draft = (await client.get(f"{USAGE_URL}/{tournament_id}/teams/{team_id}")).json()
    assert draft["default_level"] == 100
    imported = draft["members"][0]
    assert imported["showdown_name"] == "Charizard"
    assert imported["gigantamax"] is True
    assert imported["level"] == 100
    assert imported["shiny"] is True


async def test_team_import_draft(client: AsyncClient) -> None:
    tournament_id = await _seed_tournament(client)
    payload = (await client.get(f"{USAGE_URL}/{tournament_id}/teams/1")).json()
    assert payload["format_key"] == "champions"
    assert payload["default_level"] == 100
    assert payload["points_kind"] == "stat_points"
    member = payload["members"][0]
    assert member["dex_number"] == 445
    assert member["evs"] == [0, 0, 0, 0, 0, 0]
    assert member["level"] == 100
    assert member["shiny"] is True
    assert member["gigantamax"] is False
    # 冠军没有极巨化：不把默认 10 写进非剑盾队伍
    assert member["dynamax_level"] is None
    assert payload["validation"]["ok"] is True
    assert (await client.get(f"{USAGE_URL}/{tournament_id}/teams/999")).status_code == 404


async def test_sync_rejects_concurrent_run(client: AsyncClient) -> None:
    from app.db.engine import get_session_factory
    from app.db.models import TournamentSyncRun

    factory = get_session_factory()
    async with factory() as session:
        session.add(TournamentSyncRun(status="running", scope_json="{}"))
        await session.commit()
    response = await client.post(f"{USAGE_URL}/sync", json={})
    assert response.status_code == 409


def test_schema_version_bumped() -> None:
    from app.db.models import SCHEMA_VERSION

    assert SCHEMA_VERSION >= "0021"


async def test_mark_interrupted_runs_recovers_tournament_sync(
    client: AsyncClient, monkeypatch
) -> None:
    """服务重启后残留的 running 赛事同步要收尾，不然后续同步永远 409。"""
    from app.db.engine import get_session_factory, session_scope
    from app.db.models import TournamentSyncRun
    from app.services import tournament_service

    factory = get_session_factory()
    async with factory() as session:
        stale = TournamentSyncRun(status="running", total=20, done=7)
        session.add(stale)
        await session.commit()
        stale_id = stale.id

    async with session_scope() as session:
        recovered = await tournament_service.mark_interrupted_runs(session)
    assert recovered == 1

    async with factory() as session:
        stale = await session.get(TournamentSyncRun, stale_id)
    assert stale.status == "error"
    assert "中断" in (stale.message or "")
    assert stale.finished_at is not None

    # 新同步不再被旧的 running 记录挡住。替换后台任务，避免测试真的联网。
    async def noop(_scope, _run_id) -> None:
        return None

    monkeypatch.setattr(tournament_service, "run_sync", noop)
    response = await client.post(f"{USAGE_URL}/sync", json={})
    assert response.status_code == 202


def test_parse_items_js() -> None:
    from app.services.tournament_service import parse_items_js

    text = (
        'exports.BattleItems = {charizarditey:{name:"Charizardite Y",spritenum:586,'
        'megaStone:{Charizard:"Charizard-Mega-Y"},itemUser:["Charizard"]},'
        'leftovers:{name:"Leftovers",num:234,gen:2}}'
    )
    items = parse_items_js(text)
    assert items["charizardite y"]["megaStone"] == {"Charizard": "Charizard-Mega-Y"}
    assert "leftovers" not in items
