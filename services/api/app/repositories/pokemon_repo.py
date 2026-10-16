"""pokemon 表仓储：只做 SQL/ORM 读写，不含业务判断。

列表查询的三类条件（搜索 / 属性筛选 / 世代筛选）都以参数传入，由仓储拼装。
`types_json` 是 JSON 文本数组，属性筛选用 LIKE 匹配 `"fire"` 子串 —— 18 个属性名
都是不含引号与逗号的纯小写单词，LIKE '"fire"' 不会误命中（不存在子串嵌套）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminOpLog, Pokemon


@dataclass(frozen=True)
class PokemonListQuery:
    """列表查询条件。全部可选，空条件 = 全量分页。"""

    search: str | None = None  # 中英文名子串（不区分大小写）
    type_filter: str | None = None  # 属性英文键，如 "fire"
    generation: int | None = None  # 登场世代
    page: int = 1  # 从 1 起
    page_size: int = 20


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


def _apply_filters(stmt: Select, query: PokemonListQuery) -> Select:
    if query.search:
        keyword = f"%{query.search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(Pokemon.name_en).like(keyword)
            | func.ifnull(Pokemon.name_zh, "").like(keyword)
        )
    if query.type_filter:
        # types_json 形如 ["fire","flying"]，LIKE 匹配带引号的属性名
        stmt = stmt.where(Pokemon.types_json.like(f'%"{query.type_filter}"%'))
    if query.generation is not None:
        stmt = stmt.where(Pokemon.generation_introduced == query.generation)
    return stmt


async def list_pokemon(session: AsyncSession, query: PokemonListQuery) -> PokemonPage:
    """分页列表，按图鉴编号升序。"""
    base = _apply_filters(select(Pokemon), query)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    page = max(1, query.page)
    page_size = max(1, min(100, query.page_size))
    stmt = base.order_by(Pokemon.dex_number.asc()).offset((page - 1) * page_size).limit(page_size)
    items = list((await session.execute(stmt)).scalars().all())

    return PokemonPage(items=items, total=total, page=page, page_size=page_size)


async def get_by_dex_number(session: AsyncSession, dex_number: int) -> Pokemon | None:
    return (
        await session.execute(select(Pokemon).where(Pokemon.dex_number == dex_number))
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

    return {
        "total": total,
        "from_pokeapi": from_sync,
        "from_manual": from_manual,
        "demo": demo_count,
        "last_synced_at": last_synced.isoformat() if last_synced else None,
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

    return {
        "id": pokemon.id,
        "dex_number": pokemon.dex_number,
        "name_en": pokemon.name_en,
        "name_zh": pokemon.name_zh,
        "types": safe_loads(pokemon.types_json, []),
        "stats": safe_loads(pokemon.stats_json, {}),
        "abilities": safe_loads(pokemon.abilities_json, []),
        "evolution": safe_loads(pokemon.evolution_json, {}),
        "generation_introduced": pokemon.generation_introduced,
        "height_dm": pokemon.height_dm,
        "weight_hg": pokemon.weight_hg,
        "source": pokemon.source,
        "is_demo": pokemon.is_demo,
        "synced_at": pokemon.synced_at.isoformat() if pokemon.synced_at else None,
    }
