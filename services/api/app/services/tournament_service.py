"""官方赛事同步：发现赛事 → 抓成绩 / 队表 → 名称映射 → 落库。

数据源页面（全部公开、robots.txt 允许抓取）：
  - 列表：`/tournaments?time=all&show=100&type=...&page=N`（每个类型独立翻页）
  - 成绩：`/tournaments/{id}`（名次 / 选手 / 队伍预览 / 队表链接）
  - 队表：`/tournaments/{id}/teams?show=1000&page=1`（一次可取回全部队表）
  - （可选）统计：`/tournaments/{id}/statistics`（Top Cut 使用率，作对照）

增量策略：
  - 已完整抓过（有身高 / 队表已落库）的赛事直接跳过；
  - 只抓「有队表」的赛事时，`has_teamlists` 为 False 的赛事会补抓一次；
  - 官方赛事的历史不会变，跳过是安全的；重抓由 `refresh=true` 显式触发。

名称映射（`domain/tournament_showdown.py`）依赖 Showdown 官方数据：
  - 首次同步时下载 `pokedex.json` / `items.js` / `learnsets.json` / `moves.json`，
    写入 `api_cache`（TTL 30 天），之后的同步直接用缓存，不再重复下载。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import session_scope
from app.db.models import (
    Tournament,
    TournamentStanding,
    TournamentSyncRun,
    TournamentTeam,
    TournamentTeamMember,
    TournamentUsage,
)
from app.domain import tournament_catalog, tournament_parser
from app.domain.tournament_showdown import (
    TOURNAMENT_DEFAULT_LEVEL,
    ShowdownDex,
    build_showdown_member,
    format_meta,
    render_tournament_showdown,
    split_gigantamax,
)
from app.repositories import api_cache_repo, pokemon_repo
from app.services import team_service

logger = logging.getLogger(__name__)

#: 对 Limitless 的并发请求数（对方是普通站点，保持克制）。
MAX_CONCURRENCY = 3

#: 队表页一次取回的条数。实测 `show=1000` 会在服务端渲染全量队表（大会约 1.2 MB），
#: 对 100–1500 人的赛事都能一次取回；超过这个数量的赛事（世锦赛）分页取。
TEAMLIST_PAGE_SIZE = 1000

#: Showdown 官方数据的缓存 TTL（秒）：30 天。
SHOWDOWN_CACHE_TTL = 30 * 24 * 3600

SHOWDOWN_URLS = {
    "pokedex": "https://play.pokemonshowdown.com/data/pokedex.json",
    "items": "https://play.pokemonshowdown.com/data/items.js",
    "learnsets": "https://play.pokemonshowdown.com/data/learnsets.json",
    "moves": "https://play.pokemonshowdown.com/data/moves.json",
}


@dataclass(frozen=True)
class SyncScope:
    """一次赛事同步的范围。`None` 表示「全部」。"""

    #: 赛事类型（默认抓全部类型；地区赛数量最多）
    types: tuple[str, ...] | None = None
    #: 只抓这个日期之后的赛事（YYYY-MM-DD）
    date_from: str | None = None
    #: 只抓这个日期之前的赛事（YYYY-MM-DD）
    date_to: str | None = None
    #: 只抓这些规则（Limitless 标识，如 `m-c` / `svf`）
    rulesets: tuple[str, ...] | None = None
    #: 只抓有队表的赛事（没有队表的历史赛事仍然会记录名次与使用率）
    with_teams_only: bool = True
    #: 强制重抓（忽略增量跳过）
    refresh: bool = False

    def to_json(self) -> dict:
        return {
            "types": list(self.types) if self.types else None,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "rulesets": list(self.rulesets) if self.rulesets else None,
            "with_teams_only": self.with_teams_only,
            "refresh": self.refresh,
        }


# ---------------------------------------------------------------------------
# 网络
# ---------------------------------------------------------------------------


def _client() -> httpx.AsyncClient:
    """赛事抓取用客户端：显式忽略环境代理（与 Smogon 同步同一考虑）。"""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        headers={"User-Agent": tournament_catalog.USER_AGENT},
        follow_redirects=True,
        trust_env=False,
    )


async def _get(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.text


async def _get_optional(client: httpx.AsyncClient, url: str) -> str | None:
    """抓取一个可选页面；404 返回 None（该赛事没有这一页）。"""
    response = await client.get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# Showdown 官方数据（名称映射用）
# ---------------------------------------------------------------------------


_ITEMS_JS_ENTRY = re.compile(r'\{name:"([^"]+)"[^{}]*?megaStone:\{([^}]*)\}')


def parse_items_js(text: str) -> dict[str, dict]:
    """从 `items.js`（Showdown 的 JS 数据文件）里提取进化石 → 形态映射。

    只解析需要的一小部分：`name` 与 `megaStone`。返回结构与 `items.json`
    相同（`{name_lower: {"name": …, "megaStone": {…}}}`），供 `ShowdownDex` 使用。
    """
    items: dict[str, dict] = {}
    for match in _ITEMS_JS_ENTRY.finditer(text):
        name, inner = match.groups()
        pairs = re.findall(r'"?([A-Za-z0-9\-\'\. ]+)"?:"([^"]+)"', inner)
        items[name.strip().lower()] = {
            "name": name.strip(),
            "megaStone": {key.strip(): value.strip() for key, value in pairs},
        }
    return items


async def load_showdown_dex(session: AsyncSession) -> ShowdownDex:
    """读取（必要时下载）Showdown 官方数据，构造只读索引。

    缓存放在 `api_cache`（与 PokéAPI 缓存共用），键前缀 `showdown:`。
    下载失败时用已有缓存（即使过期）；完全没有任何数据时抛 RuntimeError ——
    没有名称映射就无法把队表转成可建队的配置，宁可明确失败。
    """
    now = time.time()
    payloads: dict[str, object] = {}

    async with _client() as client:
        for key, url in SHOWDOWN_URLS.items():
            cache_key = f"showdown:{key}"
            cached = await api_cache_repo.get_cache_entry(session, cache_key, now=now)
            if cached is not None and cached.fresh:
                payloads[key] = json.loads(cached.payload)
                continue
            try:
                response = await client.get(url)
                text = response.text
                if key == "items":
                    parsed: object = parse_items_js(text)
                elif key in ("learnsets", "pokedex", "moves"):
                    parsed = json.loads(text)
                else:  # pragma: no cover - 目录只有上面几种
                    continue
                payloads[key] = parsed
                await api_cache_repo.upsert_cache_entry(
                    session,
                    cache_key,
                    url,
                    json.dumps(parsed, ensure_ascii=False),
                    now + SHOWDOWN_CACHE_TTL,
                )
                await session.flush()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                if cached is not None:
                    logger.warning("Showdown 数据下载失败，使用旧缓存（%s）：%s", key, exc)
                    payloads[key] = json.loads(cached.payload)
                    continue
                raise RuntimeError(f"无法获取 Showdown 官方数据（{key}）：{exc}") from exc

    return ShowdownDex(
        pokedex=payloads.get("pokedex") or {},
        items=payloads.get("items") or {},
        learnsets=payloads.get("learnsets") or {},
        moves=payloads.get("moves") or {},
    )


# ---------------------------------------------------------------------------
# 列表发现
# ---------------------------------------------------------------------------


async def discover_events(
    client: httpx.AsyncClient,
    scope: SyncScope,
) -> list[tournament_parser.EventRow]:
    """按类型翻页抓列表，合并去重（同一赛事可能出现在多个类型里）。"""
    types = scope.types or tournament_catalog.SYNC_TYPES
    found: dict[int, tournament_parser.EventRow] = {}
    for event_type in types:
        for page in range(1, 20):
            url = tournament_catalog.list_url(event_type, page)
            text = await _get(client, url)
            rows = tournament_parser.parse_event_list(text, event_type=event_type)
            if not rows:
                break
            for row in rows:
                found.setdefault(row.tournament_id, row)
            if len(rows) < 100:
                break
    events = list(found.values())
    if scope.date_from:
        events = [row for row in events if row.date >= scope.date_from]
    if scope.date_to:
        events = [row for row in events if row.date <= scope.date_to]
    if scope.rulesets:
        wanted = set(scope.rulesets)
        events = [row for row in events if row.ruleset in wanted]
    events.sort(key=lambda row: row.date)
    return events


# ---------------------------------------------------------------------------
# 同步编排
# ---------------------------------------------------------------------------


async def start_sync(session: AsyncSession, scope: SyncScope) -> TournamentSyncRun:
    """创建同步记录并**立即提交**（后台任务用独立会话读取）。"""
    run = TournamentSyncRun(
        status="running",
        scope_json=json.dumps(scope.to_json(), ensure_ascii=False),
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)
    await session.commit()
    return run


async def run_sync(scope: SyncScope, run_id: int) -> None:
    """后台执行同步；异常写进 run，不向外抛。"""
    try:
        await _run_sync_inner(scope, run_id)
    except Exception as exc:  # noqa: BLE001 - 后台任务要把失败写进记录
        logger.exception("官方赛事同步失败")
        async with session_scope() as session:
            run = await session.get(TournamentSyncRun, run_id)
            if run is not None:
                run.status = "error"
                run.message = f"{type(exc).__name__}: {exc}"
                run.finished_at = _now()


def _now() -> datetime:
    return datetime.now(UTC)


async def _update_run(run_id: int, **fields) -> None:
    async with session_scope() as session:
        run = await session.get(TournamentSyncRun, run_id)
        if run is None:
            return
        for key, value in fields.items():
            setattr(run, key, value)


async def _run_sync_inner(scope: SyncScope, run_id: int) -> None:
    async with session_scope() as session:
        showdown = await load_showdown_dex(session)

    async with _client() as client:
        events = await discover_events(client, scope)

        # 增量：已抓过且有队表的赛事跳过（除非 refresh）
        async with session_scope() as session:
            existing: dict[int, Tournament] = {
                row.source_id: row
                for row in (await session.execute(select(Tournament))).scalars().all()
            }

        targets: list[tournament_parser.EventRow] = []
        skipped = 0
        for row in events:
            known = existing.get(row.tournament_id)
            if known is None or scope.refresh:
                targets.append(row)
                continue
            if known.has_teamlists:
                # 已完整抓过：官方赛事的历史不会变，跳过是安全的
                skipped += 1
                continue
            # 之前抓到过但没有队表：站方可能后来补了队表，但不必每次同步都重试
            # （早期赛事常年没有队表），30 天内抓过就跳过。
            if _fresh_enough(known.fetched_at, days=30):
                skipped += 1
                continue
            targets.append(row)

        await _update_run(run_id, total=len(targets), skipped=skipped)

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        created = failed = 0
        for index, row in enumerate(targets, start=1):
            await _update_run(run_id, current=_label(row))
            try:
                async with semaphore:
                    await _sync_one(client, showdown, row)
            except Exception as exc:  # noqa: BLE001 - 单场失败不影响其它赛事
                logger.warning("赛事 %s 同步失败：%s", row.tournament_id, exc)
                failed += 1
                await _update_run(run_id, done=index, failed=failed)
                continue
            created += 1
            await _update_run(run_id, done=index, created=created)

    async with session_scope() as session:
        run = await session.get(TournamentSyncRun, run_id)
        if run is not None:
            run.status = "done"
            run.current = None
            run.finished_at = _now()
            if run.failed:
                run.message = f"{run.failed} 场赛事抓取失败，其余已入库"


def _fresh_enough(fetched_at: datetime | None, *, days: int) -> bool:
    """`fetched_at` 是否在最近 `days` 天内（用于无队表赛事的重试节流）。"""
    if fetched_at is None:
        return False
    value = fetched_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return (datetime.now(UTC) - value).days < days


def _label(row: tournament_parser.EventRow) -> str:
    return f"{row.name}（{row.tournament_id}）"


async def _sync_one(
    client: httpx.AsyncClient,
    showdown: ShowdownDex,
    row: tournament_parser.EventRow,
) -> bool:
    """同步一场赛事。返回 True 表示写入了队表，False 表示只有成绩 / 无数据。"""
    result_url = tournament_catalog.tournament_url(row.tournament_id)
    result_html = await _get(client, result_url)
    header = tournament_parser.parse_event_header(result_html)
    standings = tournament_parser.parse_standings(result_html)

    teams_html = await _get_optional(
        client,
        f"{result_url}/teams?show={TEAMLIST_PAGE_SIZE}&page=1",
    )
    teams = tournament_parser.parse_teamlists(teams_html or "")

    format_key = tournament_catalog.format_key_for(row.ruleset)
    usage = tournament_parser.usage_from_teams(teams)

    async with session_scope() as session:
        tournament = (
            await session.execute(
                select(Tournament).where(Tournament.source_id == row.tournament_id)
            )
        ).scalar_one_or_none()
        if tournament is None:
            tournament = Tournament(source_id=row.tournament_id)
            session.add(tournament)

        tournament.name = header.name or row.name
        tournament.date = row.date
        tournament.ruleset = row.ruleset
        tournament.event_type = (
            row.event_type
            or tournament_catalog.infer_event_type(header.name)
            or "special"
        )
        tournament.country = header.country or row.country
        tournament.players = header.players or row.players
        tournament.winner = row.winner
        tournament.winner_country = row.winner_country
        tournament.format_key = format_key
        tournament.standings_count = len(standings)
        tournament.team_count = len(teams)
        tournament.has_teamlists = bool(teams)
        tournament.source_url = result_url
        await session.flush()

        # 名次（整体替换，幂等）
        await session.execute(
            delete(TournamentStanding).where(
                TournamentStanding.tournament_id == tournament.id
            )
        )
        for standing in standings:
            session.add(
                TournamentStanding(
                    tournament_id=tournament.id,
                    rank=standing.rank,
                    player=standing.player,
                    country=standing.country,
                    species_json=json.dumps(standing.species, ensure_ascii=False),
                    source_team_id=standing.team_id,
                )
            )

        # 队伍与队表：先删队员再删队伍（team_id 是自增 id，SQLite 会复用，
        # 残留的队员行会与新队伍撞唯一键）
        old_team_ids = select(TournamentTeam.id).where(
            TournamentTeam.tournament_id == tournament.id
        )
        await session.execute(
            delete(TournamentTeamMember).where(
                TournamentTeamMember.team_id.in_(old_team_ids)
            )
        )
        await session.execute(
            delete(TournamentTeam).where(TournamentTeam.tournament_id == tournament.id)
        )
        for team in teams:
            members = [
                build_showdown_member(
                    showdown,
                    member_slug=member.species_slug,
                    member_label=member.species_label,
                    item=member.item,
                    ability=member.ability,
                    nature=member.nature,
                    tera_type=member.tera_type,
                    moves=member.moves,
                    format_key=format_key,
                )
                for member in team.members
            ]
            showdown_text = render_tournament_showdown(members, format_key=format_key)
            problems = [
                f"{member['showdown_name']} 未能映射到图鉴"
                for member in members
                if member.get("dex_number") is None
            ]
            validation = await _validate(
                session,
                format_key,
                [
                    {
                        "dex_number": member["dex_number"],
                        "showdown_name": member["showdown_name"],
                        "ability": member.get("ability"),
                        "moves": member.get("moves") or [],
                        "item": member.get("item"),
                        "evs": [0] * 6,
                        "level": member.get("level"),
                    }
                    for member in members
                    if member.get("dex_number") is not None
                ],
            )
            record = TournamentTeam(
                tournament_id=tournament.id,
                rank=team.rank or 0,
                player=team.player,
                country=None,
                source_team_id=_team_id_of(standings, team.rank, team.player),
                showdown_text=showdown_text,
                problems_json=json.dumps(problems, ensure_ascii=False),
                validation_json=json.dumps(validation, ensure_ascii=False),
            )
            session.add(record)
            await session.flush()
            for position, member in enumerate(members):
                session.add(
                    TournamentTeamMember(
                        team_id=record.id,
                        position=position,
                        dex_number=member.get("dex_number"),
                        species_slug=member.get("species_slug") or "",
                        showdown_name=member.get("showdown_name") or "",
                        item=member.get("item"),
                        ability=member.get("ability"),
                        nature=member.get("nature"),
                        tera_type=member.get("tera_type"),
                        # 超极巨化统一折算成「基础形态 + 标记」，与导出的
                        # `Gigantamax: Yes` 一一对应；极巨化等级赛事未公开，记默认 10。
                        gigantamax=bool(member.get("gigantamax")),
                        dynamax_level=member.get("dynamax_level") or 10,
                        moves_json=json.dumps(member.get("moves") or [], ensure_ascii=False),
                    )
                )

        # 使用率（整体替换）
        await session.execute(
            delete(TournamentUsage).where(TournamentUsage.tournament_id == tournament.id)
        )
        for rank, usage_row in enumerate(usage, start=1):
            species = showdown.species(usage_row.species_slug)
            session.add(
                TournamentUsage(
                    tournament_id=tournament.id,
                    species_slug=usage_row.species_slug,
                    dex_number=species.dex_number if species else None,
                    showdown_name=species.name if species else usage_row.species_label,
                    rank=rank,
                    count=usage_row.count,
                    share=usage_row.share,
                )
            )

    return bool(teams)


def _team_id_of(
    standings: list[tournament_parser.StandingRow],
    rank: int | None,
    player: str,
) -> int | None:
    """该名次对应的 Limitless 队表 id。

    成绩页偶尔出现**同一个队表 id 指向多名选手**（站方录入问题，如 2026 世锦赛
    第 23 与 33 名共用 6827）。重复的 id 不能作为身份标识，一律记为 None。
    """
    ids = [row.team_id for row in standings if row.team_id is not None]
    duplicated = {team_id for team_id in ids if ids.count(team_id) > 1}
    for standing in standings:
        if standing.rank == rank or (
            standing.player.lower() == player.lower() and standing.team_id
        ):
            if standing.team_id in duplicated:
                return None
            return standing.team_id
    return None


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------


async def list_tournaments(
    session: AsyncSession,
    *,
    ruleset: str | None,
    event_type: str | None,
    format_key: str | None,
    year: int | None,
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(Tournament)
    if ruleset:
        stmt = stmt.where(Tournament.ruleset == ruleset)
    if event_type:
        stmt = stmt.where(Tournament.event_type == event_type)
    if format_key:
        stmt = stmt.where(Tournament.format_key == format_key)
    if year:
        stmt = stmt.where(Tournament.date.like(f"{year:04d}-%"))
    if search:
        needle = f"%{search.strip()}%"
        stmt = stmt.where(
            Tournament.name.like(needle) | Tournament.winner.like(needle)
        )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = list(
        (
            await session.execute(
                stmt.order_by(Tournament.date.desc(), Tournament.source_id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [_summary(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "years": await available_years(session),
        "rulesets": _ruleset_options(await stored_rulesets(session)),
    }


def _summary(row: Tournament) -> dict:
    return {
        "id": row.id,
        "source_id": row.source_id,
        "name": row.name,
        "date": row.date,
        "ruleset": row.ruleset,
        "ruleset_label": tournament_catalog.ruleset_label(row.ruleset),
        "event_type": row.event_type,
        "event_type_label": tournament_catalog.event_type_label(row.event_type),
        "country": row.country,
        "players": row.players,
        "winner": row.winner,
        "winner_country": row.winner_country,
        "format_key": row.format_key,
        "standings_count": row.standings_count,
        "team_count": row.team_count,
        "has_teamlists": row.has_teamlists,
        "source_url": row.source_url,
    }


async def stored_rulesets(session: AsyncSession) -> list[str]:
    rows = (
        await session.execute(select(Tournament.ruleset).distinct())
    ).all()
    found = {value for (value,) in rows if value}
    ordered = [item.identifier for item in tournament_catalog.RULESETS if item.identifier in found]
    return ordered + sorted(found - set(ordered))


def _ruleset_options(identifiers: list[str]) -> list[dict]:
    options = []
    for identifier in identifiers:
        item = tournament_catalog.RULESET_BY_ID.get(identifier)
        options.append(
            {
                "identifier": identifier,
                "label": item.label if item else identifier,
                "game": item.game if item else "",
                "format_key": item.format_key if item else None,
            }
        )
    return options


async def available_years(session: AsyncSession) -> list[int]:
    rows = (await session.execute(select(Tournament.date))).all()
    return sorted({int(date[:4]) for (date,) in rows if date}, reverse=True)


def _tournament_member_payload(
    member: TournamentTeamMember, format_key: str | None = None
) -> dict:
    """赛事成员行 → 渲染 / 建队共用的字段（超极巨化统一成「基础形态 + 标记」）。

    旧数据把 G 形态写进 `showdown_name`（`Charizard-Gmax`），这里拆掉后缀并补上
    标记；新数据已经存成基础形态 + `gigantamax`。两种写法得到同一份导出代码。

    极巨化等级只对剑盾有意义（其它格式给 None，避免把 10 写进朱紫 / 冠军队伍）。
    """
    name, suffix_gmax = split_gigantamax(member.showdown_name)
    return {
        "showdown_name": name or member.showdown_name,
        "species_slug": member.species_slug,
        "item": member.item,
        "ability": member.ability,
        "nature": member.nature,
        "tera_type": member.tera_type,
        "moves": json.loads(member.moves_json or "[]"),
        "level": TOURNAMENT_DEFAULT_LEVEL,
        "language": "CHS",
        "shiny": True,
        "dynamax_level": (
            (member.dynamax_level if member.dynamax_level is not None else 10)
            if format_key == "swsh"
            else None
        ),
        "gigantamax": bool(member.gigantamax) or suffix_gmax,
    }


async def get_tournament(session: AsyncSession, tournament_id: int) -> dict | None:
    row = await session.get(Tournament, tournament_id)
    if row is None:
        return None

    standings = list(
        (
            await session.execute(
                select(TournamentStanding)
                .where(TournamentStanding.tournament_id == tournament_id)
                .order_by(TournamentStanding.rank.asc())
            )
        )
        .scalars()
        .all()
    )
    teams = list(
        (
            await session.execute(
                select(TournamentTeam)
                .where(TournamentTeam.tournament_id == tournament_id)
                .order_by(TournamentTeam.rank.asc(), TournamentTeam.id.asc())
            )
        )
        .scalars()
        .all()
    )
    member_rows = list(
        (
            await session.execute(
                select(TournamentTeamMember).where(
                    TournamentTeamMember.team_id.in_([team.id for team in teams])
                )
            )
        )
        .scalars()
        .all()
    ) if teams else []
    members_by_team: dict[int, list[TournamentTeamMember]] = {}
    for member in member_rows:
        members_by_team.setdefault(member.team_id, []).append(member)

    usage = list(
        (
            await session.execute(
                select(TournamentUsage)
                .where(TournamentUsage.tournament_id == tournament_id)
                .order_by(TournamentUsage.rank.asc())
            )
        )
        .scalars()
        .all()
    )
    teams_payload = []
    for team in teams:
        ordered = sorted(
            members_by_team.get(team.id, []), key=lambda item: item.position
        )
        payload_members = [
            _tournament_member_payload(member, row.format_key) for member in ordered
        ]
        teams_payload.append(
            {
                "id": team.id,
                "rank": team.rank,
                "player": team.player,
                "country": team.country,
                # 按当前规则重算文本：旧库里的代码可能是旧格式（`Level: 50`、
                # `Charizard-Gmax`、缺 `Shiny` / `Gigantamax`），读取时统一升级，
                # 用户不必为了复制正确格式而重抓赛事。
                "showdown_text": render_tournament_showdown(
                    payload_members, format_key=row.format_key
                ),
                "problems": json.loads(team.problems_json or "[]"),
                "validation": json.loads(team.validation_json or "{}"),
                "members": [
                    {
                        "position": member.position,
                        "dex_number": member.dex_number,
                        "showdown_name": payload["showdown_name"],
                        "species_slug": member.species_slug,
                        "item": member.item,
                        "ability": member.ability,
                        "nature": member.nature,
                        "tera_type": member.tera_type,
                        "moves": payload["moves"],
                        "gigantamax": payload["gigantamax"],
                        "dynamax_level": payload["dynamax_level"],
                    }
                    for member, payload in zip(ordered, payload_members, strict=True)
                ],
            }
        )

    return {
        "tournament": _summary(row),
        "standings": [
            {
                "rank": standing.rank,
                "player": standing.player,
                "country": standing.country,
                "species": json.loads(standing.species_json or "[]"),
                "team_id": standing.source_team_id,
            }
            for standing in standings
        ],
        "teams": teams_payload,
        "usage": [
            {
                "rank": entry.rank,
                "species_slug": entry.species_slug,
                "showdown_name": entry.showdown_name,
                "dex_number": entry.dex_number,
                "count": entry.count,
                "share": entry.share,
            }
            for entry in usage
        ],
    }


async def usable_team(
    session: AsyncSession, tournament_id: int, team_id: int
) -> dict | None:
    """取一支队伍，转成建队页需要的成员字段（**已清除 EV**，避免误导）。

    只返回能映射到图鉴的成员；`format_key` 为空（本地无法建队）时调用方应拒绝。
    """
    row = await session.get(Tournament, tournament_id)
    if row is None or not row.format_key:
        return None
    team = await session.get(TournamentTeam, team_id)
    if team is None or team.tournament_id != tournament_id:
        return None
    members = list(
        (
            await session.execute(
                select(TournamentTeamMember)
                .where(TournamentTeamMember.team_id == team.id)
                .order_by(TournamentTeamMember.position.asc())
            )
        )
        .scalars()
        .all()
    )
    meta = format_meta(row.format_key)
    # 形态（`Urshifu-Rapid-Strike` / `Toxtricity-Low-Key`）要还原成建队页的形态
    # 选择器，否则一键建队会把队表里的形态换成使用率更高的另一个形态。
    form_by_showdown = await pokemon_repo.get_form_showdown_names(
        session, [member.dex_number for member in members if member.dex_number]
    )
    payload = []
    for member in members:
        if member.dex_number is None:
            continue
        fields = _tournament_member_payload(member, row.format_key)
        form = form_by_showdown.get(
            (member.dex_number, fields["showdown_name"].lower())
        )
        payload.append(
            {
                "dex_number": member.dex_number,
                "showdown_name": fields["showdown_name"],
                # 本地非默认形态 slug；默认形态为 None
                "form": form,
                "item": fields["item"],
                "ability": fields["ability"],
                "nature": fields["nature"],
                "evs": [0, 0, 0, 0, 0, 0],
                "moves": fields["moves"],
                "tera_type": fields["tera_type"],
                # 赛事页面代码的默认值：满级 / 闪光 / 极巨化等级 10。
                "level": TOURNAMENT_DEFAULT_LEVEL,
                "language": "CHS",
                "shiny": True,
                "dynamax_level": fields["dynamax_level"],
                "gigantamax": fields["gigantamax"],
                "gender": None,
            }
        )
    return {
        "tournament": _summary(row),
        "team": {
            "id": team.id,
            "rank": team.rank,
            "player": team.player,
            "showdown_text": render_tournament_showdown(payload, format_key=row.format_key),
            "validation": json.loads(team.validation_json or "{}"),
        },
        "format_key": row.format_key,
        "default_level": TOURNAMENT_DEFAULT_LEVEL,
        "trade_prefix": meta["trade_prefix"],
        "points_kind": meta["points_kind"],
        "members": payload,
        "validation": await _validate(session, row.format_key, payload),
    }


async def _validate(
    session: AsyncSession, format_key: str, members: list[dict]
) -> dict:
    """按本地规则校验这支队伍；返回 issues / ok（源站笔误也如实列出）。"""
    validation = await team_service.validate_members(session, format_key, members)
    return {
        "ok": validation.ok,
        "issues": [issue.message for issue in validation.issues],
    }


# ---------------------------------------------------------------------------
# 同步记录
# ---------------------------------------------------------------------------


async def latest_run(session: AsyncSession) -> TournamentSyncRun | None:
    return (
        await session.execute(
            select(TournamentSyncRun).order_by(TournamentSyncRun.id.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def mark_interrupted_runs(session: AsyncSession) -> int:
    """服务启动时把残留的 running 任务标为 error（后台任务随进程消失）。

    与 Smogon 历史使用率同步同样的道理：不清理会让前端一直转圈，并让新的
    同步永远撞上「已有任务在运行」。已抓完的赛事都已落库，下次增量会跳过。
    """
    rows = list(
        (
            await session.execute(
                select(TournamentSyncRun).where(TournamentSyncRun.status == "running")
            )
        )
        .scalars()
        .all()
    )
    for run in rows:
        run.status = "error"
        run.current = None
        run.finished_at = _now()
        prefix = f"{run.message}；" if run.message else ""
        run.message = f"{prefix}服务重启，同步任务被中断（已完成 {run.done}/{run.total}）"
    return len(rows)


async def purge_all(session: AsyncSession) -> int:
    """清空赛事数据（测试 / 修正用）。返回删除的赛事数。"""
    ids = [row for (row,) in (await session.execute(select(Tournament.id))).all()]
    if not ids:
        return 0
    await session.execute(
        delete(TournamentTeamMember).where(
            TournamentTeamMember.team_id.in_(select(TournamentTeam.id))
        )
    )
    for model in (TournamentStanding, TournamentTeam, TournamentUsage):
        await session.execute(delete(model).where(model.tournament_id.in_(ids)))
    await session.execute(delete(Tournament).where(Tournament.id.in_(ids)))
    return len(ids)
