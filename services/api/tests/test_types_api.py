"""属性克制接口测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import _REPO_DATA_DIR

TYPES_URL = "/api/v1/types"
EVALUATE_URL = "/api/v1/types/evaluate"
REVERSE_URL = "/api/v1/types/reverse"


def _load_repo_chart() -> dict[str, dict[str, float]]:
    """读取仓库根克制表（conftest 的 data_dir 夹具复制的就是这份文件）。"""
    payload = json.loads((_REPO_DATA_DIR / "type-chart.json").read_text(encoding="utf-8"))
    return payload["chart"]


async def test_get_type_chart_returns_18_types_and_meta(client: AsyncClient) -> None:
    response = await client.get(TYPES_URL)

    assert response.status_code == 200
    payload = response.json()

    assert len(payload["types"]) == 18
    names = {t["name"] for t in payload["types"]}
    assert "fairy" in names and "steel" in names
    assert payload["chart"]["fire"]["grass"] == 2
    assert payload["meta"]["generation_min"] == 6


async def test_get_type_chart_matches_shared_test_chart(client: AsyncClient) -> None:
    """/types 返回的克制表必须与仓库根规范文件完全一致（两端唯一真相）。"""
    payload = (await client.get(TYPES_URL)).json()

    assert payload["chart"] == _load_repo_chart()


async def test_evaluate_single_and_dual(client: AsyncClient) -> None:
    # 单属性 2 倍
    response = await client.post(EVALUATE_URL, json={"attack": "fire", "defense": ["grass"]})
    assert response.status_code == 200
    assert response.json() == {
        "attack": "fire",
        "defense": ["grass"],
        "multiplier": 2.0,
        "label": "2×",
    }

    # 双属性 4 倍
    response = await client.post(EVALUATE_URL, json={"attack": "fire", "defense": ["grass", "ice"]})
    assert response.status_code == 200
    assert response.json()["multiplier"] == 4.0
    assert response.json()["label"] == "4×"


async def test_evaluate_immune_and_fraction(client: AsyncClient) -> None:
    response = await client.post(EVALUATE_URL, json={"attack": "ground", "defense": ["flying"]})
    assert response.json()["multiplier"] == 0.0
    assert response.json()["label"] == "无效（免疫）"

    response = await client.post(
        EVALUATE_URL, json={"attack": "fire", "defense": ["water", "dragon"]}
    )
    assert response.json()["multiplier"] == 0.25
    assert response.json()["label"] == "1/4×"


async def test_evaluate_rejects_unknown_type_with_422(client: AsyncClient) -> None:
    response = await client.post(EVALUATE_URL, json={"attack": "shadow", "defense": ["normal"]})
    assert response.status_code == 422
    assert "不存在" in response.json()["detail"]


async def test_evaluate_rejects_three_defenses(client: AsyncClient) -> None:
    """世代规则允许的双属性上限是 2，三个防守属性是非法输入。"""
    response = await client.post(
        EVALUATE_URL, json={"attack": "fire", "defense": ["water", "grass", "ice"]}
    )
    assert response.status_code == 422


async def test_reverse_returns_only_non_neutral_sorted(client: AsyncClient) -> None:
    response = await client.post(REVERSE_URL, json={"defense": ["water", "ground"]})

    assert response.status_code == 200
    payload = response.json()

    entries = payload["entries"]
    multipliers = [e["multiplier"] for e in entries]
    assert multipliers == sorted(multipliers, reverse=True)

    by_attack = {e["attack"]: e["multiplier"] for e in entries}
    assert by_attack["grass"] == 4.0
    assert by_attack["electric"] == 0.0
    assert "normal" not in by_attack  # 中性项被排除

    # 中文名同步返回
    zh = {e["attack"]: e["zh"] for e in entries}
    assert zh["grass"] == "草"


async def test_reverse_rejects_unknown_type(client: AsyncClient) -> None:
    response = await client.post(REVERSE_URL, json={"defense": ["water", "shadow"]})
    assert response.status_code == 422


async def test_types_endpoints_503_when_chart_missing(
    var_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """克制表未生成时接口如实报 503，并提示生成命令。"""
    from app.core.config import get_settings
    from app.db.engine import dispose_engine, init_db
    from app.main import create_app
    from app.services.type_chart_service import reset_type_chart_cache

    empty_dir = var_dir.parent / "empty-data"
    empty_dir.mkdir()
    monkeypatch.setenv("POKEMON_LAB_DATA_DIR", str(empty_dir))
    get_settings.cache_clear()
    reset_type_chart_cache()
    await dispose_engine()

    app = create_app()
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        # GET /types
        assert (await c.get(TYPES_URL)).status_code == 503
        # POST /types/evaluate
        resp = await c.post(EVALUATE_URL, json={"attack": "fire", "defense": ["grass"]})
        assert resp.status_code == 503
        assert "gen_type_chart" in resp.json()["detail"]
        # POST /types/reverse
        assert (await c.post(REVERSE_URL, json={"defense": ["grass"]})).status_code == 503

    reset_type_chart_cache()
    get_settings.cache_clear()
