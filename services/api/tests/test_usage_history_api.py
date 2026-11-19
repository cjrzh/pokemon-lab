"""Smogon 历史使用率：目录、增量计划与查询接口测试。

不发真实网络：`plan_targets` 只做本地计算；同步落库用直接构造的快照验证。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import UsageSnapshot, UsageSnapshotEntry
from app.domain import smogon_catalog
from app.repositories import pokemon_repo
from app.services.usage_sync_service import SyncScope, plan_targets

USAGE_URL = "/api/v1/usage"


def test_catalog_has_no_duplicates_and_expected_range() -> None:
    ids = [fmt.format_id for fmt in smogon_catalog.FORMAT_CATALOG]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 50
    # 随机格式不收录
    assert not (smogon_catalog.EXCLUDED & set(ids))
    # 三档等级线
    assert smogon_catalog.CUTOFFS == (1500, 1630, 1760)


def test_usage_url_shape() -> None:
    assert (
        smogon_catalog.usage_url("gen9doublesuu", "2026-10", 1630)
        == "https://www.smogon.com/stats/2026-10/gen9doublesuu-1630.txt"
    )


async def _seed_snapshot(
    *,
    format_id: str = "gen9doublesuu",
    month: str = "2026-10",
    cutoff: int = 1630,
    battles: int = 1200,
) -> None:
    factory = get_session_factory()
    async with factory() as session:
        # 多个用例共用一个 client，宝可梦只插一次
        from sqlalchemy import select

        exists = (
            await session.execute(
                select(pokemon_repo.Pokemon).where(pokemon_repo.Pokemon.dex_number == 1013)
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                pokemon_repo.Pokemon(
                    dex_number=1013,
                    name_en="sinistcha",
                    name_zh="来悲茶",
                    types_json=json.dumps(["grass", "ghost"]),
                    stats_json="{}",
                    abilities_json="[]",
                    evolution_json="{}",
                    moves_json="{}",
                    source="pokeapi",
                    sprite_path="sprites/1013.png",
                )
            )
        snapshot = UsageSnapshot(
            format_id=format_id, month=month, cutoff=cutoff, battles=battles
        )
        session.add(snapshot)
        await session.flush()
        session.add_all(
            [
                UsageSnapshotEntry(
                    snapshot_id=snapshot.id,
                    showdown_name="Sinistcha",
                    dex_number=1013,
                    rank=1,
                    usage=31.5,
                    raw_count=900,
                ),
                UsageSnapshotEntry(
                    snapshot_id=snapshot.id,
                    showdown_name="Unknown-Mon",
                    dex_number=None,
                    rank=2,
                    usage=12.25,
                    raw_count=400,
                ),
            ]
        )
        await session.commit()


async def test_query_returns_entries_with_dex_info(client: AsyncClient) -> None:
    await _seed_snapshot()
    payload = (
        await client.get(
            USAGE_URL,
            params={"format": "gen9doublesuu", "month": "2026-10", "cutoff": 1630},
        )
    ).json()

    assert payload["battles"] == 1200
    assert payload["total"] == 2
    first = payload["items"][0]
    assert first["showdown_name"] == "Sinistcha"
    assert first["name_zh"] == "来悲茶"
    assert first["types"] == ["grass", "ghost"]
    assert first["sprite_url"] == "/media/sprites/1013.png"
    # 未映射的条目仍展示，只是没有图鉴信息
    assert payload["items"][1]["dex_number"] is None
    assert payload["months"] == ["2026-10"]


async def test_query_defaults_to_latest_month(client: AsyncClient) -> None:
    await _seed_snapshot(month="2026-09")
    await _seed_snapshot(month="2026-10")

    payload = (await client.get(USAGE_URL, params={"format": "gen9doublesuu"})).json()
    assert payload["month"] == "2026-10"
    assert payload["months"] == ["2026-09", "2026-10"]


async def test_query_search_by_name_and_dex(client: AsyncClient) -> None:
    await _seed_snapshot()

    by_name = (
        await client.get(USAGE_URL, params={"format": "gen9doublesuu", "q": "sinist"})
    ).json()
    assert by_name["total"] == 1

    by_dex = (
        await client.get(USAGE_URL, params={"format": "gen9doublesuu", "q": "1013"})
    ).json()
    assert by_dex["total"] == 1


async def test_query_reports_missing_snapshot(client: AsyncClient) -> None:
    """选到还没同步的快照：has_snapshot=False，而不是「同步了但榜单为空」。"""
    await _seed_snapshot(month="2026-10", cutoff=1630)

    existing = (
        await client.get(
            USAGE_URL,
            params={"format": "gen9doublesuu", "month": "2026-10", "cutoff": 1630},
        )
    ).json()
    assert existing["has_snapshot"] is True
    assert existing["total"] == 2

    missing = (
        await client.get(
            USAGE_URL,
            params={"format": "gen9doublesuu", "month": "2026-09", "cutoff": 1500},
        )
    ).json()
    assert missing["has_snapshot"] is False
    assert missing["battles"] == 0
    assert missing["total"] == 0


async def test_sync_single_format_scope(client: AsyncClient) -> None:
    """单条目同步：只传一个 format_ids，计划里只有该规则。"""
    await _seed_snapshot(month="2026-10", cutoff=1630)

    factory = get_session_factory()
    async with factory() as session:
        scope = SyncScope(
            format_ids=["gen9doublesuu"],
            cutoffs=(1500, 1630),
        )
        targets, warnings = await plan_targets(session, scope, ["2026-09", "2026-10"])

    # 该规则两个月 × 两档，去掉已有的 (2026-10, 1630)
    assert targets == [
        ("gen9doublesuu", "2026-09", 1500),
        ("gen9doublesuu", "2026-09", 1630),
        ("gen9doublesuu", "2026-10", 1500),
    ]
    assert warnings == []

    # 再收窄到单个快照
    async with factory() as session:
        single = SyncScope(
            format_ids=["gen9doublesuu"], months=["2026-09"], cutoffs=(1760,)
        )
        targets, _ = await plan_targets(session, single, ["2026-09", "2026-10"])
    assert targets == [("gen9doublesuu", "2026-09", 1760)]


async def test_sync_request_validates_scope(client: AsyncClient) -> None:
    """单条目同步的参数要校验：未知格式 / 未知等级线 / 空列表都拒绝（422）。"""
    assert (
        await client.post(f"{USAGE_URL}/sync", json={"format_ids": ["not-a-format"]})
    ).status_code == 422
    assert (
        await client.post(f"{USAGE_URL}/sync", json={"format_ids": [], "months": ["2026-10"]})
    ).status_code == 422
    assert (
        await client.post(
            f"{USAGE_URL}/sync",
            json={"format_ids": ["gen9doublesuu"], "cutoffs": [9999]},
        )
    ).status_code == 422
    assert (
        await client.post(
            f"{USAGE_URL}/sync",
            json={"format_ids": ["gen9doublesuu"], "months": ["2026/10"]},
        )
    ).status_code == 422


async def test_query_rejects_unknown_format_and_cutoff(client: AsyncClient) -> None:
    assert (await client.get(USAGE_URL, params={"format": "nope"})).status_code == 422
    assert (await client.get(USAGE_URL, params={"cutoff": 9999})).status_code == 422


async def test_plan_targets_is_incremental(client: AsyncClient) -> None:
    """已存在的 (格式, 月份, 等级线) 不重复抓取。"""
    await _seed_snapshot(month="2026-10", cutoff=1630)

    factory = get_session_factory()
    async with factory() as session:
        scope = SyncScope(
            months=["2026-10"],
            format_ids=["gen9doublesuu"],
            cutoffs=(1500, 1630),
        )
        targets, warnings = await plan_targets(session, scope, ["2026-09", "2026-10"])

    # 1630 已有 → 只差 1500
    assert targets == [("gen9doublesuu", "2026-10", 1500)]
    assert warnings == []


async def test_plan_targets_warns_unknown_format(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        scope = SyncScope(months=["2026-10"], format_ids=["not-a-format"], cutoffs=(1630,))
        targets, warnings = await plan_targets(session, scope, ["2026-10"])

    assert targets == []
    assert any("not-a-format" in warning for warning in warnings)


async def test_sync_rejects_concurrent_run(client: AsyncClient) -> None:
    """已有 running 任务时不允许再启动（避免重复抓取）。"""
    from app.db.models import UsageSyncRun

    factory = get_session_factory()
    async with factory() as session:
        session.add(UsageSyncRun(status="running", scope_json="{}"))
        await session.commit()

    response = await client.post(f"{USAGE_URL}/sync", json={"months": ["2026-10"]})
    assert response.status_code == 409


def test_schema_version_bumped() -> None:
    from app.db.models import SCHEMA_VERSION

    assert SCHEMA_VERSION >= "0019"


async def test_lifespan_recovers_interrupted_runs(client: AsyncClient) -> None:
    """启动时（lifespan）自动收尾残留的 running 记录。"""
    from app.db.engine import get_session_factory
    from app.db.models import UsageSyncRun
    from app.main import lifespan

    factory = get_session_factory()
    async with factory() as session:
        stale = UsageSyncRun(status="running", total=10, done=3)
        session.add(stale)
        await session.commit()
        stale_id = stale.id

    # 用真实应用跑一次 lifespan（只到 startup 部分）
    from app.main import create_app

    app = create_app()
    async with lifespan(app):
        pass

    async with factory() as session:
        stale = await session.get(UsageSyncRun, stale_id)
    assert stale.status == "error"
    assert "中断" in (stale.message or "")


# ---------------------------------------------------------------------------
# 同步收尾（回归：最后一个条目 404 时任务永远停在 running）
# ---------------------------------------------------------------------------

#: 供落库测试用的一份最小 usage 文本（格式与 Smogon 一致）。
USAGE_TEXT = """
Total battles: 120
+ ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
| Rank | Pokemon            | Usage %   | Raw    | %       | Real   | %       |
+ ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
| 1    | Incineroar         | 83.49422% | 100    | 42.666% | 0      | 0.000%  |
+ ---- + ------------------ + --------- + ------ + ------- + ------ + ------- +
"""


async def _start_empty_run() -> int:
    from app.db.engine import session_scope
    from app.services import usage_sync_service

    async with session_scope() as session:
        run = await usage_sync_service.start_sync(
            session,
            SyncScope(format_ids=["gen9doublesuu"], months=["2026-10"], cutoffs=(1630,)),
        )
        return run.id


async def _run_with_download(monkeypatch, run_id: int, text: str | None) -> None:
    """直接执行 run_sync，跳过真实网络（只替换下载与月份发现）。"""
    from app.services import usage_sync_service

    async def fake_discover(_client) -> list[str]:
        return ["2026-10"]

    async def fake_download(_client, _semaphore, format_id, month, cutoff):
        return format_id, month, cutoff, text

    monkeypatch.setattr(smogon_catalog, "discover_months_async", fake_discover)
    monkeypatch.setattr(usage_sync_service, "_download", fake_download)

    scope = SyncScope(format_ids=["gen9doublesuu"], months=["2026-10"], cutoffs=(1630,))
    await usage_sync_service.run_sync(scope, run_id)


async def _get_run(run_id: int):
    from app.db.engine import get_session_factory
    from app.db.models import UsageSyncRun

    async with get_session_factory()() as session:
        return await session.get(UsageSyncRun, run_id)


async def test_run_sync_finishes_when_last_item_is_missing(
    client: AsyncClient, monkeypatch
) -> None:
    """最后一个候选 404（skipped）时任务也必须标 done，否则前端一直转圈。"""
    await _seed_snapshot(month="2026-09")  # 让 2026-10 成为唯一目标
    run_id = await _start_empty_run()
    await _run_with_download(monkeypatch, run_id, None)

    run = await _get_run(run_id)
    assert run.status == "done"
    assert run.done == 1
    assert run.skipped == 1
    assert run.current is None
    assert run.finished_at is not None


async def test_run_sync_finishes_when_last_item_is_parse_error(
    client: AsyncClient, monkeypatch
) -> None:
    """解析失败同样要推进进度并收尾（以前只在成功分支判断 done >= total）。"""
    await _seed_snapshot(month="2026-09")
    run_id = await _start_empty_run()
    await _run_with_download(monkeypatch, run_id, "not a usage table")

    run = await _get_run(run_id)
    assert run.status == "done"
    assert run.failed == 1
    assert run.done == 1


async def test_run_sync_persists_snapshot(client: AsyncClient, monkeypatch) -> None:
    await _seed_snapshot(month="2026-09")
    run_id = await _start_empty_run()
    await _run_with_download(monkeypatch, run_id, USAGE_TEXT)

    run = await _get_run(run_id)
    assert run.status == "done"
    assert run.created == 1

    payload = (
        await client.get(
            USAGE_URL,
            params={"format": "gen9doublesuu", "month": "2026-10", "cutoff": 1630},
        )
    ).json()
    assert payload["has_snapshot"] is True
    assert payload["items"][0]["showdown_name"] == "Incineroar"


async def test_persist_one_skips_duplicate_instead_of_failing(
    client: AsyncClient,
) -> None:
    """并发/残留导致的重复快照按「已存在」跳过，不让整批任务报错。"""
    from app.db.engine import session_scope
    from app.services import usage_sync_service
    from app.services.doubles_service import build_name_index

    await _seed_snapshot(month="2026-10", cutoff=1630)
    run_id = await _start_empty_run()
    # 手工把 run 的总数设为 1（模拟计划里漏掉了这个已有快照）
    async with session_scope() as session:
        from app.db.models import UsageSyncRun

        run = await session.get(UsageSyncRun, run_id)
        run.total = 1

    await usage_sync_service._persist_one(
        run_id, "gen9doublesuu", "2026-10", 1630, USAGE_TEXT, build_name_index([])
    )

    run = await _get_run(run_id)
    assert run.status == "done"
    assert run.skipped == 1
    assert run.done == 1
    # 原快照没有被重复写入：仍然只有一个
    from sqlalchemy import func, select

    from app.db.engine import get_session_factory
    from app.db.models import UsageSnapshot

    async with get_session_factory()() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(UsageSnapshot)
                .where(UsageSnapshot.format_id == "gen9doublesuu")
            )
        ).scalar_one()
    assert count == 1  # 只有 seed 的那一个；重复写入被跳过


async def test_mark_interrupted_runs_recovers_stale_status(
    client: AsyncClient,
) -> None:
    """服务重启后：走完的标 done，没走完的标 error（与「完成」区分开）。"""
    from app.db.engine import get_session_factory, session_scope
    from app.db.models import UsageSyncRun
    from app.services import usage_sync_service

    factory = get_session_factory()
    async with factory() as session:
        done_run = UsageSyncRun(status="running", total=10, done=10)
        broken_run = UsageSyncRun(status="running", total=10, done=4)
        session.add_all([done_run, broken_run])
        await session.commit()
        done_id, broken_id = done_run.id, broken_run.id

    async with session_scope() as session:
        recovered = await usage_sync_service.mark_interrupted_runs(session)

    assert recovered == 2
    async with factory() as session:
        done_run = await session.get(UsageSyncRun, done_id)
        broken_run = await session.get(UsageSyncRun, broken_id)
    assert done_run.status == "done"
    assert broken_run.status == "error"
    assert "中断" in (broken_run.message or "")
    assert broken_run.finished_at is not None


def test_data_dir_has_no_stale_usage_files() -> None:
    """历史使用率不落仓库文件（与旧的双打 JSON 不同），避免仓库膨胀。"""
    data_dir = get_settings().data_dir
    assert list(data_dir.glob("usage*")) == []
