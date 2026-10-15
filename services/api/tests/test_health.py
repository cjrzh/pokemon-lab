"""健康检查接口与自检逻辑测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.engine import session_scope
from app.db.models import SCHEMA_VERSION
from app.services.selfcheck import check_datasets

HEALTH_URL = "/api/v1/health"


async def test_health_reports_database_ok_and_datasets_present(client: AsyncClient) -> None:
    response = await client.get(HEALTH_URL)

    assert response.status_code == 200
    payload = response.json()

    assert payload["service"] == "pokemon-lab-api"
    assert payload["version"] == "0.1.0"
    assert payload["generated_at"]

    checks = {item["name"]: item for item in payload["checks"]}
    assert set(checks) == {"database", "datasets"}
    assert checks["database"]["status"] == "ok"
    assert "SQLite" in checks["database"]["detail"]


async def test_health_overall_status_is_consistent_with_checks(client: AsyncClient) -> None:
    """整体状态必须由各项检查推导，不允许出现「有 error 却报 ok」的情况。"""
    payload = (await client.get(HEALTH_URL)).json()

    all_ok = all(item["status"] == "ok" for item in payload["checks"])
    assert payload["status"] == ("ok" if all_ok else "degraded")


async def test_health_maps_unfinished_module_to_degraded(client: AsyncClient) -> None:
    """P1 交付属性克制数据之前，datasets 必须如实报告为降级。"""
    payload = (await client.get(HEALTH_URL)).json()
    checks = {item["name"]: item for item in payload["checks"]}

    datasets = checks["datasets"]
    assert datasets["status"] in {"ok", "degraded"}
    if datasets["status"] == "degraded":
        assert payload["status"] == "degraded"


async def test_init_db_stamps_schema_version(client: AsyncClient) -> None:
    _ = client
    async with session_scope() as session:
        value = (
            await session.execute(
                text("select value from schema_meta where key = 'schema_version'")
            )
        ).scalar_one()

    assert value == SCHEMA_VERSION


async def test_database_file_is_created_inside_var_dir(client: AsyncClient, var_dir: Path) -> None:
    _ = client
    settings = get_settings()

    assert settings.database_path.parent == var_dir
    assert settings.database_path.exists()


async def test_cors_preflight_allows_owner_key_header(client: AsyncClient) -> None:
    """前端会用 X-Owner-Key 携带匿名身份，预检必须放行该头。"""
    response = await client.options(
        HEALTH_URL,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Owner-Key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-owner-key" in response.headers["access-control-allow-headers"].lower()


async def test_root_endpoint_points_to_docs_and_health(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["docs"] == "/docs"
    assert payload["health"] == HEALTH_URL


def test_check_datasets_reports_error_when_data_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POKEMON_LAB_DATA_DIR", str(tmp_path / "definitely-missing"))
    get_settings.cache_clear()
    try:
        result = check_datasets()
    finally:
        get_settings.cache_clear()

    assert result.name == "datasets"
    assert result.status == "error"
    assert "不存在" in result.detail


def test_check_datasets_reports_degraded_when_type_chart_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setenv("POKEMON_LAB_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    try:
        result = check_datasets()
    finally:
        get_settings.cache_clear()

    assert result.status == "degraded"
    assert "尚未生成" in result.detail


def test_check_datasets_reports_ok_when_type_chart_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "type-chart.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("POKEMON_LAB_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    try:
        result = check_datasets()
    finally:
        get_settings.cache_clear()

    assert result.status == "ok"
    assert "type-chart.json" in result.detail
