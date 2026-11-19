"""官方赛事页面的解析（纯函数：HTML 文本 → 结构化数据，不访问网络 / 数据库）。

解析对象（limitlessvgc.com）：
  - **赛事列表页**：`/tournaments?time=all&show=100&type=…&page=…`
    `<tr data-date data-format data-players ...>` 一行一场赛事；
  - **成绩页**：`/tournaments/{id}` —— 名次 / 选手 / 国家 / 队伍预览 / 队表链接；
  - **队表页**：`/tournaments/{id}/teams` —— 每位选手 6 只的完整配置
    （物种 / 道具 / 特性 / 性格 / 太晶 / 招式；**没有 EV 与 IV**，Limitless 未公开）；
  - **统计页**：`/tournaments/{id}/statistics` —— 「Most successful Pokémon」
    只覆盖 Top Cut，使用率以成绩页的**全体队表**为准（见 `usage_from_teams`）。

为什么用正则而不是 HTML 解析库：
  页面结构稳定、片段规则简单（固定的 class 与 data-* 属性），正则足够且零依赖；
  解析器只做「从文本里取值」，任何一处结构变化都会在测试里立刻暴露。

容错原则：认不出的整块跳过（记入 warnings），不造半截数据；统计值缺字段时用
`None` 表示，由上层决定展示方式，而不是填一个看起来合理的默认值。
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from app.domain.tournament_catalog import infer_event_type

# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


def clean_text(raw: str) -> str:
    """去标签、反转义、压缩空白。"""
    return _SPACES.sub(" ", html.unescape(_TAG.sub(" ", raw or ""))).strip()


def _text_of(fragment: str | None) -> str | None:
    if fragment is None:
        return None
    text = clean_text(fragment)
    return text or None


# ---------------------------------------------------------------------------
# 赛事列表
# ---------------------------------------------------------------------------

_TR_ROW = re.compile(r"<tr\s[^>]*data-date=\"([^\"]+)\"[^>]*>(.*?)</tr>", re.S)
_ATTR = re.compile(r'data-([a-z]+)="([^"]*)"')
_TOURNAMENT_LINK = re.compile(r'href="/tournaments/(\d+)"')
_PLAYER_WINNER = re.compile(r'data-winner="([A-Za-z]{0,4}-)?([^"]*)"')


@dataclass(frozen=True)
class EventRow:
    """列表页的一行。`winner_country` / `winner_name` 已从 `XX-姓名` 拆开。"""

    tournament_id: int
    date: str  # YYYY-MM-DD
    name: str
    ruleset: str
    players: int
    country: str | None = None
    winner: str | None = None
    winner_country: str | None = None
    #: 列表页的类型筛选值（regional / worlds …），由 `parse_event_list` 的调用方补
    event_type: str | None = None


def parse_event_list(page_html: str, *, event_type: str | None = None) -> list[EventRow]:
    """解析赛事列表页；没有行时返回空列表。

    `event_type` 是本次请求的类型筛选值（列表页自身不带这个字段），
    由调用方传入后写进每一行。
    """
    rows: list[EventRow] = []
    for match in _TR_ROW.finditer(page_html):
        date, body = match.group(1), match.group(2)
        attrs = dict(_ATTR.findall(match.group(0)))
        link = _TOURNAMENT_LINK.search(body)
        if link is None:
            continue
        winner = _text_of(attrs.get("winner")) or None
        winner_country = None
        if winner and "-" in winner:
            prefix, _, rest = winner.partition("-")
            # `US-Joseph Ugarte` / `GB-Barry Anderson`：前缀是两位国家代码
            if 2 <= len(prefix) <= 3 and prefix.isalpha() and rest:
                winner_country, winner = prefix.upper(), rest.strip()
        try:
            players = int(attrs.get("players") or 0)
        except ValueError:
            players = 0
        rows.append(
            EventRow(
                tournament_id=int(link.group(1)),
                date=date,
                name=_text_of(attrs.get("name")) or "",
                ruleset=(attrs.get("format") or "").strip(),
                players=players,
                country=(attrs.get("country") or "").strip() or None,
                winner=winner,
                winner_country=winner_country,
                event_type=event_type,
            )
        )
    return rows


@dataclass(frozen=True)
class EventHeader:
    """赛事详情页头部的元信息。"""

    name: str
    date: str | None = None
    players: int | None = None
    ruleset: str | None = None
    country: str | None = None
    event_type: str | None = None


_INFOBOX = re.compile(r'<div class="infobox">(.*?)<div class="secondary-menu">', re.S)
_INFOBOX_HEADING = re.compile(r'<div class="infobox-heading">(.*?)</div>', re.S)
_INFOBOX_LINE = re.compile(r'<div class="infobox-line">(.*?)</div>', re.S)
_DATE = re.compile(r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})")
_PLAYERS = re.compile(r"(\d+)\s*Players")
_COUNTRY = re.compile(r'class="flag"[^>]*alt="([A-Z]{2,3})"')
_ALERT = re.compile(r'class="alert[^"]*"[^>]*>(.*?)</a>', re.S)


def parse_event_header(page_html: str) -> EventHeader:
    """从成绩页解析名称 / 日期 / 人数 / 规则 / 国家 / 类型。"""
    head = _INFOBOX.search(page_html)
    heading_block = _INFOBOX_HEADING.search(head.group(1)) if head else None
    name = _text_of(heading_block.group(1)) if heading_block else ""
    # 头部标题里混着国家徽章的 alt（如 `US`），去掉标题最后的国旗文字
    country = None
    if heading_block is not None:
        flag = _COUNTRY.search(heading_block.group(1))
        if flag:
            country = flag.group(1)
            name = _SPACES.sub(" ", name.removesuffix(country)).strip()

    line_html = ""
    if head is not None:
        line = _INFOBOX_LINE.search(head.group(1))
        line_html = line.group(1) if line else ""

    date_match = _DATE.search(clean_text(line_html))
    players_match = _PLAYERS.search(clean_text(line_html))
    ruleset = None
    # 规则链接形如 `/pokemon/?time=all&format=m-c`，文字是规则展示名
    ruleset_link = re.search(
        r'href="/pokemon/\?[^"]*format=([^"&]+)"[^>]*>(.*?)</a>', line_html, re.S
    )
    if ruleset_link:
        ruleset = ruleset_link.group(1).strip()

    title = re.search(r"<title>(.*?)</title>", page_html, re.S)
    if not name and title:
        name = clean_text(title.group(1)).split(" – ")[0]

    alert = _ALERT.search(page_html)
    event_type = infer_event_type(name)
    if event_type is None and alert is not None:
        event_type = infer_event_type(clean_text(alert.group(1)))

    return EventHeader(
        name=name,
        date=date_match.group(1) if date_match else None,
        players=int(players_match.group(1)) if players_match else None,
        ruleset=ruleset,
        country=country,
        event_type=event_type,
    )


# ---------------------------------------------------------------------------
# 成绩页（名次 / 选手 / 队伍预览）
# ---------------------------------------------------------------------------

_STANDING_ROW = re.compile(
    r'<tr data-rank="(\d+)"[^>]*data-name="([^"]*)"[^>]*data-country="([^"]*)"[^>]*>(.*?)</tr>',
    re.S,
)
_MEMBER_PREVIEW = re.compile(r'href="/pokemon/[^"]+" data-tooltip="([^"]+)"')
_TEAM_LINK = re.compile(r'href="/teams/(\d+)"')


@dataclass(frozen=True)
class StandingRow:
    """成绩页的一行：名次 + 选手 + 队伍预览 + 队表链接。"""

    rank: int
    player: str
    country: str | None
    species: list[str] = field(default_factory=list)
    team_id: int | None = None


def parse_standings(page_html: str) -> list[StandingRow]:
    """解析成绩页的名次表。队伍预览可能缺失（早期赛事），此时 `species` 为空。"""
    rows: list[StandingRow] = []
    for match in _STANDING_ROW.finditer(page_html):
        rank, player, country, body = match.groups()
        species = [html.unescape(name) for name in _MEMBER_PREVIEW.findall(body)]
        link = _TEAM_LINK.search(body)
        rows.append(
            StandingRow(
                rank=int(rank),
                player=html.unescape(_text_of(player) or ""),
                country=country.strip() or None,
                species=species,
                team_id=int(link.group(1)) if link else None,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# 队表页（完整配置）
# ---------------------------------------------------------------------------

_DECKLIST_CHUNK = re.compile(
    r'<div class="tournament-decklist">(.*?)(?=<div class="tournament-decklist">|</section>|\Z)',
    re.S,
)
_TOGGLE = re.compile(r'<div class="teamlist-toggle"[^>]*>(.*?)</div>', re.S)
_PKMN_BLOCK = re.compile(
    r'<div class="pkmn" data-id="([^"]+)">(.*?)'
    r'(?=<div class="pkmn" data-id="|</div>\s*</div>\s*<div class="teamlist-options">)',
    re.S,
)
_DETAIL_ITEM = re.compile(r'<div class="item">(.*?)</div>', re.S)
_DETAIL_ABILITY = re.compile(r'<div class="ability">\s*Ability:\s*(.*?)</div>', re.S)
_DETAIL_NATURE = re.compile(r'<div class="nature">(.*?)\s*Nature\s*</div>', re.S)
_DETAIL_TERA = re.compile(r'<div class="tera">\s*Tera Type:\s*(.*?)</div>', re.S)
_MOVES_LIST = re.compile(r'<ul class="moves">(.*?)</ul>', re.S)
_MOVE_ITEM = re.compile(r"<li>(.*?)</li>", re.S)
_NO_TEAMS = re.compile(r"there are no available teams", re.I)


@dataclass(frozen=True)
class TeamMemberRow:
    """一只宝可梦在队表里的配置。

    `species_slug` 是 Limitless 的物种 slug（如 `urshifu-rapid-strike`），
    **不是** Showdown 显示名；映射到 Showdown 名与图鉴编号由服务层负责。
    """

    species_slug: str
    species_label: str
    item: str | None = None
    ability: str | None = None
    nature: str | None = None
    tera_type: str | None = None
    moves: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TeamRow:
    """一位选手的队表。`label` 是「1st Joseph Ugarte」这样的原始标题。"""

    rank: int | None
    player: str
    members: list[TeamMemberRow] = field(default_factory=list)


_TOGGLE_RANK = re.compile(r"^\s*(\d+)(?:st|nd|rd|th)\s+(.*)$", re.I)


def parse_teamlists(page_html: str) -> list[TeamRow]:
    """解析 `/tournaments/{id}/teams` 的队表；页面没有队表时返回空列表。"""
    if _NO_TEAMS.search(page_html):
        return []

    teams: list[TeamRow] = []
    for chunk in _DECKLIST_CHUNK.findall(page_html):
        toggle = _TOGGLE.search(chunk)
        label = _text_of(toggle.group(1)) if toggle else ""
        rank: int | None = None
        player = label or "未知选手"
        rank_match = _TOGGLE_RANK.match(player)
        if rank_match:
            rank = int(rank_match.group(1))
            player = rank_match.group(2).strip()

        members: list[TeamMemberRow] = []
        for slug, body in _PKMN_BLOCK.findall(chunk):
            name_block = re.search(r'<div class="name">(.*?)</div>', body, re.S)
            moves_block = _MOVES_LIST.search(body)
            moves = (
                [_text_of(move) or "" for move in _MOVE_ITEM.findall(moves_block.group(1))]
                if moves_block
                else []
            )
            members.append(
                TeamMemberRow(
                    species_slug=slug.strip(),
                    species_label=(
                        _text_of(name_block.group(1)) if name_block else None
                    )
                    or slug,
                    item=_text_of(_DETAIL_ITEM.search(body).group(1))
                    if _DETAIL_ITEM.search(body)
                    else None,
                    ability=_text_of(_DETAIL_ABILITY.search(body).group(1))
                    if _DETAIL_ABILITY.search(body)
                    else None,
                    nature=_text_of(_DETAIL_NATURE.search(body).group(1))
                    if _DETAIL_NATURE.search(body)
                    else None,
                    tera_type=_text_of(_DETAIL_TERA.search(body).group(1))
                    if _DETAIL_TERA.search(body)
                    else None,
                    moves=[move for move in moves if move],
                )
            )
        # 不足 6 只的块（页面被截断 / 非完整队表）不收录，避免「3 只的假队伍」
        if len(members) >= 6:
            teams.append(TeamRow(rank=rank, player=player, members=members[:6]))
    return teams


# ---------------------------------------------------------------------------
# 统计页（Top Cut 使用率）
# ---------------------------------------------------------------------------

_STAT_ROW = re.compile(r'<tr data-count="(\d+)"[^>]*data-points="(\d+)"[^>]*>(.*?)</tr>', re.S)
_STAT_NAME = re.compile(r'href="/pokemon/([a-z0-9-]+)">([^<]+)</a>')


@dataclass(frozen=True)
class StatRow:
    rank: int
    species_slug: str
    species_label: str
    count: int
    share: float
    points: int


def parse_statistics(page_html: str) -> list[StatRow]:
    """解析统计页的「Most successful Pokémon」。

    页面上只有 Top Cut 的数据；本项目的「赛事使用率」用成绩页的全员队伍重算，
    这里的数值作为对照（`source: top_cut`）。
    """
    rows: list[StatRow] = []
    for match in _STAT_ROW.finditer(page_html):
        count, points, body = match.groups()
        name = _STAT_NAME.search(body)
        if name is None:
            continue
        rank_match = re.search(r"<td>(\d+)</td>", body)
        share_match = re.search(r"([\d.]+)%", clean_text(body))
        rows.append(
            StatRow(
                rank=int(rank_match.group(1)) if rank_match else len(rows) + 1,
                species_slug=name.group(1),
                species_label=html.unescape(name.group(2)).strip(),
                count=int(count),
                share=float(share_match.group(1)) if share_match else 0.0,
                points=int(points),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# 赛事使用率（从全体队表计算）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageRow:
    species_slug: str
    species_label: str
    count: int
    share: float


def usage_from_teams(teams: list[TeamRow]) -> list[UsageRow]:
    """按「出场队伍数」统计物种使用率（一只 / 队 计 1 次）。

    分母是**队数**（6 只满编的队伍数），所以使用率之和约为 600% —— 与 Smogon
    的「使用率」口径一致（每队 6 只，单只上限 100%）。
    """
    teams = [team for team in teams if team.members]
    if not teams:
        return []
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for team in teams:
        seen: set[str] = set()
        for member in team.members:
            if member.species_slug in seen:
                continue
            seen.add(member.species_slug)
            counts[member.species_slug] = counts.get(member.species_slug, 0) + 1
            labels.setdefault(member.species_slug, member.species_label)
    total = len(teams)
    rows = [
        UsageRow(
            species_slug=slug,
            species_label=labels[slug],
            count=count,
            share=round(count / total * 100, 2),
        )
        for slug, count in counts.items()
    ]
    rows.sort(key=lambda row: (-row.count, row.species_label or row.species_slug))
    return rows
