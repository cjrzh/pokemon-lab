"""中文图鉴描述译文服务测试：兜底规则、来源标注、数据完整性。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.flavor_translation_service import (
    SOURCE_POKEAPI,
    SOURCE_PROJECT,
    apply_flavor_fallback,
    load_genus_translations,
    load_translations,
    reset_translation_cache,
)


@pytest.fixture
def translation_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """把 data_dir 指到含译文文件的临时目录，并清空缓存。"""
    data = tmp_path / "data"
    flavor = data / "flavor-zh"
    flavor.mkdir(parents=True)
    (flavor / "gen-02.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generation": 2,
                "source": "project-translation",
                "entries": {"152": "项目自译的描述。"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (flavor / "genus-zh.json").write_text(
        json.dumps({"entries": {"152": "叶子宝可梦"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    from app.core.config import get_settings

    monkeypatch.setenv("POKEMON_LAB_DATA_DIR", str(data))
    get_settings.cache_clear()
    reset_translation_cache()
    yield flavor
    reset_translation_cache()
    get_settings.cache_clear()


def test_load_translations_and_genus(translation_dir: Path) -> None:
    assert load_translations() == {152: "项目自译的描述。"}
    assert load_genus_translations() == {152: "叶子宝可梦"}


def test_fallback_uses_translation_when_upstream_has_no_zh(translation_dir: Path) -> None:
    record = {"dex_number": 152, "flavor_zh": None, "genus_zh": None}
    result = apply_flavor_fallback(record)

    assert result["flavor_zh"] == "项目自译的描述。"
    assert result["flavor_zh_source"] == SOURCE_PROJECT
    assert result["genus_zh"] == "叶子宝可梦"
    assert result["genus_zh_source"] == SOURCE_PROJECT
    # 入参不被修改
    assert record["flavor_zh"] is None


def test_official_chinese_is_never_overwritten(translation_dir: Path) -> None:
    record = {
        "dex_number": 152,
        "flavor_zh": "上游官方中文。",
        "genus_zh": "官方分类",
    }
    result = apply_flavor_fallback(record)

    assert result["flavor_zh"] == "上游官方中文。"
    assert result["flavor_zh_source"] == SOURCE_POKEAPI
    assert result["genus_zh"] == "官方分类"
    assert result["genus_zh_source"] == SOURCE_POKEAPI


def test_no_translation_leaves_none(translation_dir: Path) -> None:
    result = apply_flavor_fallback({"dex_number": 999, "flavor_zh": None, "genus_zh": None})
    assert result["flavor_zh"] is None
    assert result["flavor_zh_source"] is None
    assert result["genus_zh"] is None


def test_corrupt_translation_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    flavor = data / "flavor-zh"
    flavor.mkdir(parents=True)
    (flavor / "gen-02.json").write_text("{ not json", encoding="utf-8")

    from app.core.config import get_settings

    monkeypatch.setenv("POKEMON_LAB_DATA_DIR", str(data))
    get_settings.cache_clear()
    reset_translation_cache()

    from app.services.flavor_translation_service import FlavorTranslationError

    with pytest.raises(FlavorTranslationError):
        load_translations()

    reset_translation_cache()
    get_settings.cache_clear()


def test_repository_translations_cover_all_generations() -> None:
    """仓库内的译文文件必须覆盖 303 条缺失条目，且没有空值。"""
    repo_data = Path(__file__).resolve().parents[3] / "data" / "flavor-zh"
    files = sorted(repo_data.glob("gen-*.json"))
    assert files, "缺少 data/flavor-zh/gen-XX.json"

    entries: dict[int, str] = {}
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["source"] == "project-translation"
        for dex, text in payload["entries"].items():
            assert text.strip(), f"{path.name} #{dex} 译文为空"
            assert int(dex) not in entries, f"#{dex} 在多个文件中重复"
            entries[int(dex)] = text

    assert len(entries) == 303

    genus = json.loads((repo_data / "genus-zh.json").read_text(encoding="utf-8"))
    assert len(genus["entries"]) == 15
