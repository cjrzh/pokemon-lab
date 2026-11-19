"""pokemon 表仓储：只做 SQL/ORM 读写，不含业务判断。

列表查询的三类条件（搜索 / 属性筛选 / 世代筛选）都以参数传入，由仓储拼装。
`types_json` 是 JSON 文本数组，属性筛选用 LIKE 匹配 `"fire"` 子串 —— 18 个属性名
都是不含引号与逗号的纯小写单词，LIKE '"fire"' 不会误命中（不存在子串嵌套）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Ability,
    AdminOpLog,
    ItemReference,
    MoveLearner,
    MoveReference,
    Pokemon,
    PokemonForm,
    PokemonFormMove,
    QuizMistake,
)
from app.domain.pokemon_parser import DAMAGE_CLASS_ZH


@dataclass(frozen=True)
class PokemonListQuery:
    """列表查询条件。全部可选，空条件 = 全量分页。"""

    search: str | None = None  # 中英文名子串（不区分大小写）
    type_filter: str | None = None  # 属性英文键，如 "fire"
    generation: int | None = None  # 登场世代
    sort: str = "dex"  # dex / dex_desc / total_stats / total_stats_asc
    page: int = 1  # 从 1 起
    page_size: int = 20
    #: True 时 `search` 按前缀匹配（`喷火` → 喷火龙），否则按子串匹配（`火龙` 也能命中）。
    #: 图鉴页保留子串（用户可能只记得名字中段）；建队选择器用前缀（输入更短、结果更准）。
    prefix: bool = False
    #: 对战分类筛选（normal / pseudo_legendary / restricted / sub_legendary /
    #: mythical / paradox）。分类由 `domain/battle_class.py` 按名字 + 传说/幻兽字段推导，
    #: 不是 pokemon 表里的列 —— 所以筛选在路由层过滤，见 `filter_by_battle_class`。
    battle_class: str | None = None


#: 排序字段白名单（路由用它校验，仓储按此分支）。
POKEMON_SORT_FIELDS = ("dex", "dex_desc", "total_stats", "total_stats_asc")

#: 与 `STAT_ORDER` 一致；stats_json 的键带连字符，json_extract 路径需要加引号。
_STAT_JSON_KEYS = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")


def _total_stats_expr():
    """六项种族值之和（SQL 表达式），用于列表排序。

    stats_json 按项目存为 JSON 文本，SQLite 可直接用 json_extract 求和；
    逐项 coalesce 0，缺失的项按 0 计（与展示层的 `total_stats` 一致）。
    空对象视为「没有数据」，返回 NULL，让它在升序 / 降序里都排到最后。
    """
    total = None
    for key in _STAT_JSON_KEYS:
        value = func.coalesce(func.json_extract(Pokemon.stats_json, f'$."{key}"'), 0)
        total = value if total is None else total + value
    return case((Pokemon.stats_json == "{}", None), else_=total)


@dataclass(frozen=True)
class PokemonPage:
    """分页结果。"""

    items: list[Pokemon]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


def _escape_like(raw: str) -> str:
    """转义 LIKE 通配符，避免用户输入的 `%` / `_` 被当成模式。"""
    return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(stmt: Select, query: PokemonListQuery) -> Select:
    if query.search:
        raw = query.search.strip()
        escaped = _escape_like(raw.lower())
        pattern = f"{escaped}%" if query.prefix else f"%{escaped}%"
        condition = func.lower(Pokemon.name_en).like(pattern, escape="\\") | func.ifnull(
            Pokemon.name_zh, ""
        ).like(pattern, escape="\\")
        # 纯数字输入按图鉴编号精确匹配（如「025」「25」）；同时保留名称匹配。
        if raw.isdigit():
            condition = condition | (Pokemon.dex_number == int(raw))
        stmt = stmt.where(condition)
    if query.type_filter:
        # types_json 形如 ["fire","flying"]，LIKE 匹配带引号的属性名
        stmt = stmt.where(Pokemon.types_json.like(f'%"{query.type_filter}"%'))
    if query.generation is not None:
        stmt = stmt.where(Pokemon.generation_introduced == query.generation)
    if query.battle_class:
        stmt = stmt.where(battle_class_condition(query.battle_class))
    return stmt


def battle_class_condition(battle_class: str):
    """把对战分类翻译成 SQL 条件（让筛选、分页、排序在同一语句里完成）。

    分类的判定顺序见 `domain/battle_class.py`：悖谬 > 幻兽 > 一级神 > 二级神 > 准神 > 普通。
    这里按「互斥」翻译 —— 每个分类都排除了优先级更高的分类，避免一只能在多档里重复出现。
    """
    from app.domain.battle_class import BATTLE_CLASS_KEYS, load_battle_classes

    if battle_class not in BATTLE_CLASS_KEYS:
        raise ValueError(f"未知对战分类：{battle_class}")

    table = load_battle_classes()
    paradox = list(table.paradox)
    restricted = list(table.restricted)
    pseudo = list(table.pseudo_legendary)

    is_paradox = func.lower(Pokemon.name_en).in_(paradox)
    is_mythical = Pokemon.is_mythical.is_(True)
    is_restricted = func.lower(Pokemon.name_en).in_(restricted)
    is_legendary = Pokemon.is_legendary.is_(True)
    is_pseudo = func.lower(Pokemon.name_en).in_(pseudo)

    if battle_class == "paradox":
        return is_paradox
    if battle_class == "mythical":
        return and_(is_mythical, ~is_paradox)
    if battle_class == "restricted":
        return and_(is_restricted, ~is_paradox, ~is_mythical)
    if battle_class == "sub_legendary":
        return and_(is_legendary, ~is_restricted, ~is_paradox, ~is_mythical)
    if battle_class == "pseudo_legendary":
        return and_(is_pseudo, ~is_legendary, ~is_mythical, ~is_paradox)
    # normal：排除以上全部
    return and_(~is_paradox, ~is_mythical, ~is_restricted, ~is_legendary, ~is_pseudo)


async def list_pokemon(session: AsyncSession, query: PokemonListQuery) -> PokemonPage:
    """分页列表。默认按图鉴编号升序，也可按编号降序或种族值合计排序。

    排序发生在筛选之后（同一 SQL 的 WHERE → ORDER BY），所以属性 / 世代 / 搜索
    的结果子集会被整体重新排序，再分页。
    """
    base = _apply_filters(select(Pokemon), query)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    page = max(1, query.page)
    page_size = max(1, min(200, query.page_size))

    if query.sort == "dex_desc":
        order = (Pokemon.dex_number.desc(),)
    elif query.sort in ("total_stats", "total_stats_asc"):
        expr = _total_stats_expr()
        # 没有种族值的记录排在最后；同分按图鉴编号，保证分页稳定
        order = (
            expr.is_(None),
            expr.desc() if query.sort == "total_stats" else expr.asc(),
            Pokemon.dex_number.asc(),
        )
    else:
        order = (Pokemon.dex_number.asc(),)

    stmt = base.order_by(*order).offset((page - 1) * page_size).limit(page_size)
    items = list((await session.execute(stmt)).scalars().all())

    return PokemonPage(items=items, total=total, page=page, page_size=page_size)


async def get_name_rows(session: AsyncSession) -> list[tuple[str, int]]:
    """全部 (name_en, dex_number)，供 Showdown 名称映射使用。"""
    rows = (await session.execute(select(Pokemon.name_en, Pokemon.dex_number))).all()
    return [(name, dex) for name, dex in rows]


async def battle_class_counts(session: AsyncSession) -> dict[str, int]:
    """各对战分类的数量（用于图鉴页筛选条上的计数）。

    分类规则是纯函数，这里一次取出 (name_en, 传说, 幻兽) 在内存里统计 ——
    1025 行、每行三个字段，比把整套判定翻译成 SQL 更容易保持一致。
    """
    from app.domain.battle_class import counts_for

    rows = (
        await session.execute(
            select(Pokemon.name_en, Pokemon.is_legendary, Pokemon.is_mythical)
        )
    ).all()
    return dict(counts_for([(name, legendary, mythical) for name, legendary, mythical in rows]))


async def get_zh_names(session: AsyncSession, dex_numbers: list[int]) -> dict[int, str | None]:
    """批量取中文名：dex_number → name_zh（未同步的编号不会出现在结果里）。"""
    if not dex_numbers:
        return {}
    stmt = select(Pokemon.dex_number, Pokemon.name_zh).where(
        Pokemon.dex_number.in_(set(dex_numbers))
    )
    rows = (await session.execute(stmt)).all()
    return {dex: zh for dex, zh in rows}


async def get_by_dex_number(session: AsyncSession, dex_number: int) -> Pokemon | None:
    return (
        await session.execute(select(Pokemon).where(Pokemon.dex_number == dex_number))
    ).scalar_one_or_none()


async def get_neighbors(
    session: AsyncSession, dex_number: int
) -> tuple[Pokemon | None, Pokemon | None]:
    """同图鉴中编号最接近的前后各一条（用于详情页的上一只 / 下一只）。"""
    prev_stmt = (
        select(Pokemon)
        .where(Pokemon.dex_number < dex_number)
        .order_by(Pokemon.dex_number.desc())
        .limit(1)
    )
    next_stmt = (
        select(Pokemon)
        .where(Pokemon.dex_number > dex_number)
        .order_by(Pokemon.dex_number.asc())
        .limit(1)
    )
    prev = (await session.execute(prev_stmt)).scalar_one_or_none()
    nxt = (await session.execute(next_stmt)).scalar_one_or_none()
    return prev, nxt


async def get_by_name(session: AsyncSession, name: str) -> Pokemon | None:
    """按英文名精确查找（同步脚本补数据时使用）。"""
    return (
        await session.execute(select(Pokemon).where(Pokemon.name_en == name))
    ).scalar_one_or_none()


async def upsert_pokemon(session: AsyncSession, record: dict) -> Pokemon:
    """按 dex_number 插入或更新。返回落库后的 ORM 对象。

    注意：`source=manual` 的记录由调用方（同步服务）决定是否跳过，仓储本身不判断 ——
    仓储不做业务判断是分层约定。
    """
    existing = await get_by_dex_number(session, record["dex_number"])
    if existing is None:
        record = {**record, "synced_at": datetime.now(UTC)}
        created = Pokemon(**record)
        session.add(created)
        await session.flush()
        return created

    for key, value in record.items():
        setattr(existing, key, value)
    existing.synced_at = datetime.now(UTC)
    await session.flush()
    return existing


async def update_pokemon_fields(session: AsyncSession, pokemon: Pokemon, fields: dict) -> Pokemon:
    """手动编辑：只更新给定字段，并把来源标记为 manual。"""
    allowed = {
        "name_en",
        "name_zh",
        "types_json",
        "stats_json",
        "abilities_json",
        "evolution_json",
        "moves_json",
        "genus_zh",
        "flavor_zh",
        "generation_introduced",
        "height_dm",
        "weight_hg",
        "is_demo",
    }
    for key, value in fields.items():
        if key in allowed:
            setattr(pokemon, key, value)
    pokemon.source = "manual"
    await session.flush()
    return pokemon


async def set_artwork_path(
    session: AsyncSession, pokemon: Pokemon, artwork_path: str | None
) -> Pokemon:
    """只更新立绘缓存路径。

    不走 `update_pokemon_fields`：补图片不属于人工编辑，不应把记录标记为 manual
    （否则后续同步会跳过这条，反而保护了过期数据）。
    """
    pokemon.artwork_path = artwork_path
    await session.flush()
    return pokemon


async def set_sprite_path(
    session: AsyncSession, pokemon: Pokemon, sprite_path: str | None
) -> Pokemon:
    """只更新小图标缓存路径（同 `set_artwork_path`，不标记 manual）。"""
    pokemon.sprite_path = sprite_path
    await session.flush()
    return pokemon


async def upsert_move_refs(session: AsyncSession, moves: list[dict]) -> int:
    """批量 upsert 招式参考数据（move_ref 表）。返回写入条数。

    招式详情是共享参考数据：同一招式的数值在 151 只宝可梦之间复用，单独建表
    避免在每只宝可梦的 moves_json 里重复存储。
    """
    if not moves:
        return 0
    names = [m["name"] for m in moves]
    existing = {
        row.name: row
        for row in (
            await session.execute(select(MoveReference).where(MoveReference.name.in_(names)))
        )
        .scalars()
        .all()
    }
    for move in moves:
        row = existing.get(move["name"])
        if row is None:
            session.add(MoveReference(**_move_ref_fields(move)))
        else:
            for key, value in _move_ref_fields(move).items():
                setattr(row, key, value)
    await session.flush()
    return len(moves)


def _move_ref_fields(move: dict) -> dict:
    return {
        "name": move["name"],
        "zh": move.get("zh"),
        "type": move.get("type"),
        "damage_class": move.get("damage_class"),
        "power": move.get("power"),
        "accuracy": move.get("accuracy"),
        "pp": move.get("pp"),
        "description_zh": move.get("description_zh"),
    }


async def get_move_ref_names(session: AsyncSession, names: list[str]) -> set[str]:
    """已存在于 move_ref 的招式名（回填脚本用来筛出缺失项）。"""
    if not names:
        return set()
    rows = (
        await session.execute(select(MoveReference.name).where(MoveReference.name.in_(set(names))))
    ).all()
    return {name for (name,) in rows}


async def get_move_refs(session: AsyncSession, names: list[str]) -> dict[str, dict]:
    """按名称取招式参考数据（详情接口用）。"""
    if not names:
        return {}
    rows = (
        (await session.execute(select(MoveReference).where(MoveReference.name.in_(set(names)))))
        .scalars()
        .all()
    )
    return {
        row.name: {
            "name": row.name,
            "zh": row.zh,
            "type": row.type,
            "damage_class": row.damage_class,
            "damage_class_zh": DAMAGE_CLASS_ZH.get(row.damage_class or ""),
            "power": row.power,
            "accuracy": row.accuracy,
            "pp": row.pp,
            "description_zh": row.description_zh,
        }
        for row in rows
    }


async def get_card_fields(session: AsyncSession, dex_numbers: list[int]) -> dict[int, dict]:
    """批量取列表卡片需要的字段：编号 → 名称 / 属性 / 立绘 / 传说标记。

    使用率排行榜等「只要一张卡」的场景使用；不加载 moves_json 等大字段。
    """
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(
                Pokemon.dex_number,
                Pokemon.name_en,
                Pokemon.name_zh,
                Pokemon.types_json,
                Pokemon.artwork_path,
                Pokemon.artwork_url,
                Pokemon.sprite_url,
                Pokemon.is_legendary,
                Pokemon.is_mythical,
            ).where(Pokemon.dex_number.in_(set(dex_numbers)))
        )
    ).all()
    result: dict[int, dict] = {}
    for (
        dex,
        name_en,
        name_zh,
        types_json,
        artwork_path,
        artwork_url,
        sprite_url,
        legendary,
        mythical,
    ) in rows:
        try:
            types = json.loads(types_json or "[]")
        except (json.JSONDecodeError, TypeError):
            types = []
        result[dex] = {
            "dex_number": dex,
            "name_en": name_en,
            "name_zh": name_zh,
            "types": types if isinstance(types, list) else [],
            "artwork_path": artwork_path,
            "artwork_url": artwork_url,
            "sprite_url": sprite_url,
            "is_legendary": legendary,
            "is_mythical": mythical,
        }
    return result


# ---------------------------------------------------------------------------
# 招式百科（move_ref + move_learner）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveListQuery:
    """招式列表筛选。`sort` 只接受白名单字段，避免拼 SQL 注入。"""

    search: str | None = None
    type_filter: str | None = None
    damage_class: str | None = None
    machine_only: bool = False
    sort: str = "name"
    page: int = 1
    page_size: int = 50


MOVE_SORT_COLUMNS = {
    "name": MoveReference.name,
    "power": MoveReference.power,
    "accuracy": MoveReference.accuracy,
    "pp": MoveReference.pp,
    "learners": MoveReference.learner_count,
}


async def list_moves(session: AsyncSession, query: MoveListQuery) -> tuple[list, int]:
    """招式列表：名称搜索、属性 / 分类 / 学习器筛选、排序与分页。

    默认按中文名排序（无中文时落到英文）；`learners` 按学习者数量降序。
    """
    stmt = select(MoveReference)
    if query.search:
        keyword = f"%{query.search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(MoveReference.name).like(keyword)
            | func.lower(MoveReference.name_en or "").like(keyword)
            | func.ifnull(MoveReference.zh, "").like(keyword)
            | func.ifnull(MoveReference.description_zh, "").like(keyword)
        )
    if query.type_filter:
        stmt = stmt.where(MoveReference.type == query.type_filter)
    if query.damage_class:
        stmt = stmt.where(MoveReference.damage_class == query.damage_class)
    if query.machine_only:
        stmt = stmt.where(MoveReference.is_machine.is_(True))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    page = max(1, query.page)
    page_size = max(1, min(200, query.page_size))

    column = MOVE_SORT_COLUMNS.get(query.sort, MoveReference.name)
    if query.sort == "learners":
        order = (column.desc(), MoveReference.name.asc())
    elif query.sort == "name":
        order = (func.ifnull(MoveReference.zh, MoveReference.name).asc(),)
    else:
        # 数值型字段：None（变化招式没有威力等）排在最后
        order = (column.is_(None), column.desc(), MoveReference.name.asc())

    stmt = stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size)
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


async def get_move(session: AsyncSession, name: str) -> MoveReference | None:
    return (
        await session.execute(select(MoveReference).where(MoveReference.name == name))
    ).scalar_one_or_none()


async def list_moves_for_version(
    session: AsyncSession, version_group: str
) -> set[str]:
    """某个版本组里**任意宝可梦**能学会的全部招式（按 `move_learner` 派生表）。

    用于图图犬的「写生」范围：写生可以复制本版本里任何宝可梦学会的招式，
    因此不需要逐个物种查招式表。
    """
    rows = (
        await session.execute(
            select(MoveLearner.move_name).where(
                MoveLearner.methods_key.like(f"%{version_group}:%")
            )
        )
    ).all()
    return {name for (name,) in rows}


async def get_move_learners(session: AsyncSession, name: str) -> list[MoveLearner]:
    stmt = (
        select(MoveLearner)
        .where(MoveLearner.move_name == name)
        .order_by(MoveLearner.dex_number.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_pokemon_briefs(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, tuple[str | None, str, str, bool, bool, str | None]]:
    """批量取学习者的展示信息：dex → (中文名, 英文名, types_json, 传说, 幻之, 小图标路径)。

    `sprite_path` 是本地缓存的相对路径（`media/` 下）；缺失时由调用方回落到
    远程代理地址，与图鉴列表同一约定。
    """
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(
                Pokemon.dex_number,
                Pokemon.name_zh,
                Pokemon.name_en,
                Pokemon.types_json,
                Pokemon.is_legendary,
                Pokemon.is_mythical,
                Pokemon.sprite_path,
            ).where(Pokemon.dex_number.in_(set(dex_numbers)))
        )
    ).all()
    return {
        dex: (name_zh, name_en, types_json, legendary, mythical, sprite_path)
        for dex, name_zh, name_en, types_json, legendary, mythical, sprite_path in rows
    }


async def get_moves_json_map(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, str]:
    """编号 → moves_json（队伍合法性校验用；只取需要的几条，不整表加载）。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(Pokemon.dex_number, Pokemon.moves_json).where(
                Pokemon.dex_number.in_(set(dex_numbers))
            )
        )
    ).all()
    return {dex: moves for dex, moves in rows}


async def get_abilities_map(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, str]:
    """编号 → abilities_json（队伍特性校验用）。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(Pokemon.dex_number, Pokemon.abilities_json).where(
                Pokemon.dex_number.in_(set(dex_numbers))
            )
        )
    ).all()
    return {dex: abilities for dex, abilities in rows}


async def get_evolution_json_map(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, str]:
    """编号 → evolution_json（队伍合法性校验用，找出进化链上的前代）。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(Pokemon.dex_number, Pokemon.evolution_json).where(
                Pokemon.dex_number.in_(set(dex_numbers))
            )
        )
    ).all()
    return {dex: evolution for dex, evolution in rows}


async def get_gender_rates(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, int | None]:
    """编号 → gender_rate（批量设性别时判断合法性）。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(Pokemon.dex_number, Pokemon.gender_rate).where(
                Pokemon.dex_number.in_(set(dex_numbers))
            )
        )
    ).all()
    return {dex: rate for dex, rate in rows}


@dataclass(frozen=True)
class ItemListQuery:
    """道具列表筛选。"""

    search: str | None = None
    category: str | None = None
    page: int = 1
    page_size: int = 50


async def list_items(
    session: AsyncSession, query: ItemListQuery
) -> tuple[list[ItemReference], int]:
    """道具列表：名称 / 说明搜索、分类筛选、分页。

    排序：有中文名的按中文名，缺失的落到英文名；同分类内保持稳定。
    """
    stmt = select(ItemReference)
    if query.search:
        keyword = f"%{query.search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(ItemReference.name).like(keyword)
            | func.lower(func.ifnull(ItemReference.name_en, "")).like(keyword)
            | func.ifnull(ItemReference.zh, "").like(f"%{query.search.strip()}%")
            | func.lower(func.ifnull(ItemReference.effect_en, "")).like(keyword)
        )
    if query.category:
        stmt = stmt.where(ItemReference.category == query.category)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    page = max(1, query.page)
    page_size = max(1, min(200, query.page_size))
    stmt = (
        stmt.order_by(
            func.ifnull(ItemReference.zh, ItemReference.name).asc(),
            ItemReference.name.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


async def get_item_categories(session: AsyncSession) -> list[tuple[str, int]]:
    """库里实际出现过的道具分类及数量（按数量降序）。"""
    rows = (
        await session.execute(
            select(ItemReference.category, func.count())
            .where(ItemReference.category.is_not(None))
            .group_by(ItemReference.category)
            .order_by(func.count().desc())
        )
    ).all()
    return [(category, count) for category, count in rows if category]


async def get_item(session: AsyncSession, name: str) -> ItemReference | None:
    return (
        await session.execute(select(ItemReference).where(ItemReference.name == name))
    ).scalar_one_or_none()


async def get_move_type_options(session: AsyncSession) -> list[str]:
    """库里实际出现过的招式属性（供筛选按钮）。"""
    rows = (
        await session.execute(
            select(MoveReference.type)
            .where(MoveReference.type.is_not(None))
            .group_by(MoveReference.type)
        )
    ).all()
    return sorted({value for (value,) in rows if value})


async def list_missing_artwork(session: AsyncSession, limit: int | None = None) -> list[Pokemon]:
    """列出没有本地立绘的记录（供补图脚本使用）。"""
    stmt = select(Pokemon).where(Pokemon.artwork_path.is_(None)).order_by(Pokemon.dex_number.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def list_missing_sprites(session: AsyncSession, limit: int | None = None) -> list[Pokemon]:
    """列出没有本地小图标的记录（供补图脚本使用）。"""
    stmt = select(Pokemon).where(Pokemon.sprite_path.is_(None)).order_by(Pokemon.dex_number.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def create_manual_pokemon(session: AsyncSession, record: dict) -> Pokemon:
    """手动新增：来源标记 manual。dex_number 冲突时抛 ValueError（调用方转 409）。"""
    if await get_by_dex_number(session, record["dex_number"]) is not None:
        raise ValueError(f"图鉴编号 {record['dex_number']} 已存在")
    record = {
        **record,
        "source": "manual",
        "is_demo": record.get("is_demo", False),
        "synced_at": datetime.now(UTC),
    }
    created = Pokemon(**record)
    session.add(created)
    await session.flush()
    return created


async def count_pokemon(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Pokemon))).scalar_one()


async def get_sync_overview(session: AsyncSession) -> dict:
    """同步总览：总数、来源分布、最近同步时间。供管理页与 selfcheck 使用。"""
    total = await count_pokemon(session)
    from_sync = (
        await session.execute(select(func.count()).where(Pokemon.source == "pokeapi"))
    ).scalar_one()
    from_manual = (
        await session.execute(select(func.count()).where(Pokemon.source == "manual"))
    ).scalar_one()
    demo_count = (
        await session.execute(select(func.count()).where(Pokemon.is_demo.is_(True)))
    ).scalar_one()
    last_synced = (await session.execute(select(func.max(Pokemon.synced_at)))).scalar_one()
    artwork_cached = (
        await session.execute(select(func.count()).where(Pokemon.artwork_path.is_not(None)))
    ).scalar_one()
    moves_covered = (
        await session.execute(select(func.count()).where(Pokemon.moves_json.not_in(("{}", ""))))
    ).scalar_one()

    # 按世代统计：generation_introduced 缺失的记录归入 None（不会出现在 map 键里）
    per_generation = dict(
        (
            await session.execute(
                select(Pokemon.generation_introduced, func.count())
                .where(Pokemon.generation_introduced.is_not(None))
                .group_by(Pokemon.generation_introduced)
                .order_by(Pokemon.generation_introduced.asc())
            )
        ).all()
    )

    return {
        "total": total,
        "from_pokeapi": from_sync,
        "from_manual": from_manual,
        "demo": demo_count,
        "last_synced_at": last_synced.isoformat() if last_synced else None,
        "artwork_cached": artwork_cached,
        "moves_covered": moves_covered,
        "per_generation": per_generation,
    }


async def log_admin_op(
    session: AsyncSession, action: str, target: str | None = None, detail: str | None = None
) -> None:
    """记录一次后台操作。失败不影响主流程（由调用方决定是否吞异常）。"""
    session.add(AdminOpLog(action=action, target=target, detail=detail))


async def list_admin_ops(session: AsyncSession, limit: int = 50) -> list[AdminOpLog]:
    stmt = select(AdminOpLog).order_by(AdminOpLog.id.desc()).limit(min(limit, 200))
    return list((await session.execute(stmt)).scalars().all())


def parse_json_fields(pokemon: Pokemon) -> dict:
    """把 ORM 对象转成带解析后 JSON 字段的字典（响应组装用）。"""

    def safe_loads(text: str, default):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return default

    stats = safe_loads(pokemon.stats_json, {})
    return {
        "id": pokemon.id,
        "dex_number": pokemon.dex_number,
        "name_en": pokemon.name_en,
        "name_zh": pokemon.name_zh,
        "name_ja": pokemon.name_ja,
        "types": safe_loads(pokemon.types_json, []),
        "stats": stats,
        "total_stats": sum(stats.values()) if stats else None,
        "abilities": safe_loads(pokemon.abilities_json, []),
        "evolution": safe_loads(pokemon.evolution_json, {}),
        "moves": safe_loads(pokemon.moves_json, {}),
        "generation_introduced": pokemon.generation_introduced,
        "height_dm": pokemon.height_dm,
        "weight_hg": pokemon.weight_hg,
        "genus_zh": pokemon.genus_zh,
        "genus_en": pokemon.genus_en,
        "flavor_zh": pokemon.flavor_zh,
        "flavor_en": pokemon.flavor_en,
        "flavor_zh_source": pokemon.flavor_zh_source,
        "genus_zh_source": pokemon.genus_zh_source,
        "artwork_path": pokemon.artwork_path,
        "artwork_url_remote": pokemon.artwork_url,
        "sprite_url": pokemon.sprite_url,
        "sprite_path": pokemon.sprite_path,
        "is_legendary": pokemon.is_legendary,
        "is_mythical": pokemon.is_mythical,
        "is_baby": pokemon.is_baby,
        "gender_rate": pokemon.gender_rate,
        "capture_rate": pokemon.capture_rate,
        "base_happiness": pokemon.base_happiness,
        "hatch_counter": pokemon.hatch_counter,
        "growth_rate": pokemon.growth_rate,
        "habitat": pokemon.habitat,
        "color": pokemon.color,
        "shape": pokemon.shape,
        "egg_groups": safe_loads(pokemon.egg_groups_json, []),
        "source": pokemon.source,
        "is_demo": pokemon.is_demo,
        "synced_at": pokemon.synced_at.isoformat() if pokemon.synced_at else None,
    }


# ---------------------------------------------------------------------------
# 特性（ability 参考表）
# ---------------------------------------------------------------------------


async def list_abilities(
    session: AsyncSession,
    *,
    search: str | None = None,
    tier: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Ability], int]:
    """特性列表：搜索（中/英文名、说明）、按 S 级筛选、分页。

    排序：S 级在前，其次按中文名；分页在排序之后执行。
    """
    stmt = select(Ability)
    if search:
        raw = search.strip()
        keyword = f"%{raw.lower()}%"
        stmt = stmt.where(
            func.lower(Ability.name).like(keyword)
            | func.ifnull(Ability.zh, "").like(keyword)
            | func.ifnull(Ability.effect_zh, "").like(keyword)
        )
    if tier in ("s", "normal"):
        stmt = stmt.where(Ability.tier == tier)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    page = max(1, page)
    page_size = max(1, min(200, page_size))
    stmt = (
        stmt.order_by(
            # 's' < 'normal' 按字符串排序不成立，用 case 显式置顶
            case((Ability.tier == "s", 0), else_=1),
            func.ifnull(Ability.zh, Ability.name).asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


async def get_ability(session: AsyncSession, name: str) -> Ability | None:
    return (await session.execute(select(Ability).where(Ability.name == name))).scalar_one_or_none()


async def get_ability_holders(session: AsyncSession, name: str) -> list[Pokemon]:
    """拥有某特性的宝可梦（按图鉴编号），通过 abilities_json 的设备名匹配。

    与列表筛选同样的约定：ability name 是纯小写 kebab-case，`"name"` 不会误命中子串。
    """
    stmt = (
        select(Pokemon)
        .where(Pokemon.abilities_json.like(f'%"{name}"%'))
        .order_by(Pokemon.dex_number.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_ability_tier_map(session: AsyncSession) -> dict[str, str]:
    """特性名 → 评级（'s' / 'normal'）。图鉴接口为特性附 S 级标记用。"""
    rows = (await session.execute(select(Ability.name, Ability.tier))).all()
    return {name: tier for name, tier in rows}


async def get_s_tier_names(session: AsyncSession) -> list[str]:
    """当前全部 S 级特性名（供图鉴页做高亮）。"""
    stmt = select(Ability.name).where(Ability.tier == "s").order_by(Ability.name)
    rows = (await session.execute(stmt)).all()
    return [name for (name,) in rows]


async def update_ability_rating(
    session: AsyncSession, ability: Ability, *, tier: str, note: str | None
) -> Ability:
    """人工修改评级：置为 manual，之后的自动评级不再覆盖。"""
    ability.tier = tier
    ability.rating_note = note
    ability.rating_source = "manual"
    await session.flush()
    return ability


# ---------------------------------------------------------------------------
# 出卷：候选题目（只读图鉴的编号 + 名称 + 图片）
# ---------------------------------------------------------------------------


async def quiz_candidates(
    session: AsyncSession,
    *,
    generation: int | None = None,
    dex_from: int | None = None,
    dex_to: int | None = None,
) -> list[tuple[int, str, str | None, str | None, str | None, str | None]]:
    """出卷候选：dex → (dex, name_en, name_zh, artwork_path, artwork_url, sprite_path)。

    只取有名称的记录（名称是答案，缺了就无法判分）；图片缺失仍然可以出题，
    页面会显示「暂无图片」而不是跳过 —— 跳过会让「全量」名不副实。
    """
    stmt = select(
        Pokemon.dex_number,
        Pokemon.name_en,
        Pokemon.name_zh,
        Pokemon.artwork_path,
        Pokemon.artwork_url,
        Pokemon.sprite_path,
    ).where(Pokemon.name_en.is_not(None))
    if generation is not None:
        stmt = stmt.where(Pokemon.generation_introduced == generation)
    if dex_from is not None:
        stmt = stmt.where(Pokemon.dex_number >= dex_from)
    if dex_to is not None:
        stmt = stmt.where(Pokemon.dex_number <= dex_to)
    stmt = stmt.order_by(Pokemon.dex_number.asc())
    rows = (await session.execute(stmt)).all()
    return [(dex, en, zh, art, art_url, sprite) for dex, en, zh, art, art_url, sprite in rows]


async def get_quiz_rows_by_dex(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, tuple[str, str | None, str | None, str | None, str | None]]:
    """批量取判分 / 展示所需字段。

    dex → (name_en, name_zh, artwork_path, artwork_url, sprite_path)。
    """
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(
                Pokemon.dex_number,
                Pokemon.name_en,
                Pokemon.name_zh,
                Pokemon.artwork_path,
                Pokemon.artwork_url,
                Pokemon.sprite_path,
            ).where(Pokemon.dex_number.in_(set(dex_numbers)))
        )
    ).all()
    return {dex: (en, zh, art, art_url, sprite) for dex, en, zh, art, art_url, sprite in rows}


async def quiz_mistake_rows(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, QuizMistake]:
    """按编号取错题记录。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(QuizMistake).where(QuizMistake.dex_number.in_(set(dex_numbers)))
        )
    ).scalars().all()
    return {row.dex_number: row for row in rows}


async def get_ability_details_map(session: AsyncSession) -> dict[str, dict]:
    """特性名 → 参考表里的中文名与说明（形态特性补全用）。

    形态（`pokemon_form.abilities_json`）只存 slug，中文名与说明在图鉴同步时
    没有写进去；`ability` 参考表才是这些字段的唯一来源。
    """
    rows = (
        await session.execute(
            select(Ability.name, Ability.zh, Ability.effect_zh, Ability.effect_en)
        )
    ).all()
    return {
        name: {"zh": zh, "effect_zh": effect_zh, "effect_en": effect_en}
        for name, zh, effect_zh, effect_en in rows
    }


async def get_form_moves_map(
    session: AsyncSession, dex_numbers: list[int], version_group: str
) -> dict[int, list[tuple[str, str]]]:
    """编号 → [(形态名, 该形态在指定版本组的招式明细 JSON), …]。

    形态专属招式只出现在形态的 `/pokemon/{name}` 响应里（如连击流武道熊师的
    「水流连打」）；这里按编号与版本组取回，由服务层与主招式表合并。
    """
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(
                PokemonFormMove.dex_number,
                PokemonFormMove.form_name,
                PokemonFormMove.methods_json,
            ).where(
                PokemonFormMove.dex_number.in_(set(dex_numbers)),
                PokemonFormMove.version_group == version_group,
            )
        )
    ).all()
    result: dict[int, list[tuple[str, str]]] = {}
    for dex, form_name, methods in rows:
        result.setdefault(dex, []).append((form_name, methods))
    return result


async def get_form_abilities_map(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[int, list[str]]:
    """编号 → [该编号下每个形态的 abilities_json]（验证「形态专属特性」用）。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(PokemonForm.dex_number, PokemonForm.abilities_json).where(
                PokemonForm.dex_number.in_(set(dex_numbers))
            )
        )
    ).all()
    result: dict[int, list[str]] = {}
    for dex, abilities in rows:
        result.setdefault(dex, []).append(abilities)
    return result


async def get_form_name_rows(session: AsyncSession) -> list[tuple[str, int]]:
    """全部 (形态名, 编号)，供 Showdown 名称映射使用（形态名即 slug）。"""
    rows = (
        await session.execute(select(PokemonForm.name, PokemonForm.dex_number))
    ).all()
    return [(name, dex) for name, dex in rows]


async def get_form_showdown_names(
    session: AsyncSession, dex_numbers: list[int]
) -> dict[tuple[int, str], str]:
    """(图鉴编号, Showdown 名小写) → 本地**非默认**形态 slug。

    已保存队伍只存 Showdown 名；要还原用户当初选的形态，必须用数据库里的
    `pokemon_form` 判断 —— 映射文件同时包含默认形态，直接反查会把 `Garchomp`
    还原成 `garchomp`，而后者并不是一个可选的形态（`team-options?form=` 会 422）。
    """
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(PokemonForm.dex_number, PokemonForm.name).where(
                PokemonForm.dex_number.in_(set(dex_numbers))
            )
        )
    ).all()
    from app.services.form_service import load_form_showdown_map

    mapping = load_form_showdown_map()
    result: dict[tuple[int, str], str] = {}
    for dex, name in rows:
        showdown = mapping.get(name)
        if showdown:
            result[(dex, showdown.lower())] = name
    return result


async def get_base_names(session: AsyncSession, dex_numbers: list[int]) -> dict[int, str]:
    """编号 → 默认形态的英文名（`pokemon.name_en`），用于识别「默认形态」。"""
    if not dex_numbers:
        return {}
    rows = (
        await session.execute(
            select(Pokemon.dex_number, Pokemon.name_en).where(
                Pokemon.dex_number.in_(set(dex_numbers))
            )
        )
    ).all()
    return {dex: name for dex, name in rows}
