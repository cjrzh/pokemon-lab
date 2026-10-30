"""中文图鉴描述的兜底译文。

PokéAPI 对一部分条目（尤其第 9 世代）没有 `zh-hans` / `zh-hant` 的图鉴文本，
上游也没有日文可回落。这里读取仓库内 `data/flavor-zh/*.json` 的项目自译，
只为「上游缺中文」的记录提供兜底，并且**绝不覆盖上游已有的官方中文**。

来源标注：
  - `pokeapi`：上游官方中文文本；
  - `project`：本项目自译（`data/flavor-zh`），界面显示「项目自译」标记；
  - `None`：没有中文文本。

数据文件结构见 `data/flavor-zh/gen-02.json`：
    {"schema_version": 1, "generation": 2, "source": "project-translation",
     "source_label": "项目自译", "entries": {"152": "……"}}
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: data/ 下的译文目录名。
FLAVOR_DIR_NAME = "flavor-zh"
FLAVOR_INDEX_FILE = "genus-zh.json"

#: 来源常量：与数据库中 `flavor_zh_source` 的取值一致。
SOURCE_POKEAPI = "pokeapi"
SOURCE_PROJECT = "project"


class FlavorTranslationError(RuntimeError):
    """译文文件缺失或损坏。属于仓库数据问题，应在启动/测试时暴露。"""


@lru_cache(maxsize=1)
def load_translations() -> dict[int, str]:
    """加载全部代次的图鉴描述译文：dex_number → 中文文本。"""
    data_dir = get_settings().data_dir / FLAVOR_DIR_NAME
    if not data_dir.is_dir():
        logger.warning("译文目录不存在，跳过中文兜底：%s", data_dir)
        return {}

    entries: dict[int, str] = {}
    for path in sorted(data_dir.glob("gen-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw = payload["entries"]
            for dex, text in raw.items():
                if not isinstance(text, str) or not text.strip():
                    raise FlavorTranslationError(f"{path.name} 中 #{dex} 的译文为空")
                entries[int(dex)] = text.strip()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise FlavorTranslationError(f"译文文件损坏（{path}）：{exc}") from exc

    logger.info("已加载 %d 条图鉴描述译文", len(entries))
    return entries


@lru_cache(maxsize=1)
def load_genus_translations() -> dict[int, str]:
    """加载分类（genus）译文：dex_number → 中文分类。"""
    path = get_settings().data_dir / FLAVOR_DIR_NAME / FLAVOR_INDEX_FILE
    if not path.exists():
        logger.warning("分类译文文件不存在，跳过分类兜底：%s", path)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            int(dex): str(text).strip()
            for dex, text in payload["entries"].items()
            if str(text).strip()
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise FlavorTranslationError(f"分类译文文件损坏（{path}）：{exc}") from exc


def reset_translation_cache() -> None:
    """仅供测试：清空译文缓存，让下次读取重新加载（数据目录切换后使用）。"""
    load_translations.cache_clear()
    load_genus_translations.cache_clear()


def apply_flavor_fallback(record: dict) -> dict:
    """给解析出的记录补中文图鉴描述 / 分类，并记录来源。

    规则（对上游保持尊重，不覆盖已有中文）：
      - 记录里已有 `flavor_zh` → 来源标注 `pokeapi`，译文文件不参与；
      - 记录没有 `flavor_zh` 且译文文件有该编号 → 写入译文，标注 `project`；
      - 两者都没有 → 保持 None（前端回落英文原文并注明）。

    返回新 dict，不修改入参。
    """
    result = dict(record)
    dex_number = int(record["dex_number"])

    if result.get("flavor_zh"):
        result["flavor_zh_source"] = SOURCE_POKEAPI
    else:
        translated = load_translations().get(dex_number)
        if translated:
            result["flavor_zh"] = translated
            result["flavor_zh_source"] = SOURCE_PROJECT
        else:
            result["flavor_zh_source"] = None

    if result.get("genus_zh"):
        result["genus_zh_source"] = SOURCE_POKEAPI
    else:
        translated_genus = load_genus_translations().get(dex_number)
        if translated_genus:
            result["genus_zh"] = translated_genus
            result["genus_zh_source"] = SOURCE_PROJECT
        else:
            result["genus_zh_source"] = None

    return result


def translation_data_dir() -> Path:
    """译文目录路径（供脚本与测试检查文件是否存在）。"""
    return get_settings().data_dir / FLAVOR_DIR_NAME
