"""道具参考数据与图标的解析 / 缓存测试（不访问网络）。"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.services import item_service

_SITRUS_PAYLOAD = {
    "id": 135,
    "name": "sitrus-berry",
    "cost": 20,
    "category": {"name": "medicine"},
    "names": [
        {"name": "オボンのみ", "language": {"name": "ja-hrkt"}},
        {"name": "文柚果", "language": {"name": "zh-hant"}},
        {"name": "Sitrus Berry", "language": {"name": "en"}},
    ],
    "effect_entries": [
        {
            "short_effect": "Consumed at 1/2 max HP\nto recover 1/4 max HP.",
            "language": {"name": "en"},
        }
    ],
    "sprites": {
        "default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/"
        "sitrus-berry.png"
    },
}


def test_parse_item_prefers_zh_hans_then_zh_hant() -> None:
    payload = {
        **_SITRUS_PAYLOAD,
        "names": [
            {"name": "文柚果", "language": {"name": "zh-hant"}},
            {"name": "文柚果", "language": {"name": "zh-hans"}},
            {"name": "Sitrus Berry", "language": {"name": "en"}},
        ],
    }
    item = item_service.parse_item("sitrus-berry", payload)

    assert item.name == "sitrus-berry"  # 始终用统计里的 slug
    assert item.zh == "文柚果"
    assert item.name_en == "Sitrus Berry"
    assert item.category == "medicine"
    assert item.cost == 20
    assert "sprites/items/sitrus-berry.png" in (item.icon_url or "")


def test_parse_item_normalizes_effect_whitespace() -> None:
    item = item_service.parse_item("sitrus-berry", _SITRUS_PAYLOAD)

    assert item.effect_en == "Consumed at 1/2 max HP to recover 1/4 max HP."


def test_parse_item_handles_missing_fields() -> None:
    item = item_service.parse_item("mystery", {})

    assert item.zh is None
    assert item.name_en is None
    assert item.category is None
    assert item.icon_url is None
    assert item.cost is None


def test_icon_media_url_prefers_local() -> None:
    assert item_service.icon_media_url("sitrus-berry", "items/sitrus-berry.png") == (
        "/media/items/sitrus-berry.png"
    )
    remote = item_service.icon_media_url("sitrus-berry", None)
    assert remote is not None and "sprites/items/sitrus-berry.png" in remote
    # 上游没有单独条目的道具不拼远程地址
    assert item_service.icon_media_url("pretty-feather", None) is None


async def test_ensure_item_icon_reuses_cached_file(var_dir: Path) -> None:
    target = get_settings().item_icon_dir / "sitrus-berry.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"png")

    assert await item_service.ensure_item_icon("sitrus-berry") == "items/sitrus-berry.png"


async def test_ensure_item_icon_returns_none_on_failure(
    var_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args, **_kwargs):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(httpx.AsyncClient, "get", fail)

    assert await item_service.ensure_item_icon("leftovers") is None


async def test_sync_items_writes_and_updates_rows(var_dir: Path, monkeypatch) -> None:
    from app.db.engine import get_session_factory, init_db
    from app.db.models import ItemReference

    await init_db()

    async def fake_fetch(_client, slug: str):
        if slug == "leek":
            return _SITRUS_PAYLOAD
        return None

    async def fake_icon(slug: str, **_kwargs):
        return f"items/{slug}.png"

    monkeypatch.setattr(item_service, "fetch_item", fake_fetch)
    monkeypatch.setattr(item_service, "ensure_item_icon", fake_icon)

    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        result = await item_service.sync_items(session, ["leek", "missing-item"])
        await session.commit()

        assert result.synced == ["leek"]
        assert result.icons == 1
        assert "missing-item" in result.failed

        row = (
            await session.execute(select(ItemReference).where(ItemReference.name == "leek"))
        ).scalar_one()
        assert row.zh == "文柚果"  # 测试数据复用
        assert row.icon_path == "items/leek.png"
        assert row.category == "medicine"


async def test_sync_items_uses_local_only_entries(var_dir: Path, monkeypatch) -> None:
    from app.db.engine import get_session_factory, init_db
    from app.db.models import ItemReference

    await init_db()

    async def fake_fetch(_client, _slug: str):
        raise AssertionError("本地专属道具不应打上游")

    monkeypatch.setattr(item_service, "fetch_item", fake_fetch)

    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        result = await item_service.sync_items(session, ["pretty-feather"])
        await session.commit()

        assert result.synced == ["pretty-feather"]
        row = (
            await session.execute(
                select(ItemReference).where(ItemReference.name == "pretty-feather")
            )
        ).scalar_one()
        assert row.zh == "美丽之羽"
        assert row.icon_path is None
        assert row.icon_url is None
