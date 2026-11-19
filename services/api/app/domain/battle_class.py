"""对战分类（普通 / 准神 / 一级神 / 二级神 / 幻兽 / 悖谬）。

为什么需要独立的规范数据，而不是只靠种族值或 `is_legendary` 推导：

  - **准神**是社区约定（三段进化最终形态、种族值 600），进化链与形态数据不足以
    可靠判定，且超级进化会让形态种族值超过 600；
  - **一级神 / 二级神**的界限是官方规则「限制传说的宝可梦」的定义，不是数值 ——
    超梦（680）是二级神，无极汰那（690）、太乐巴戈斯（600）是一级神；
  - **悖谬**按物种名固定，PokéAPI 没有单独字段。

所以名字清单放在仓库 `data/battle-classes.json`（与属性克制表同一约定：跨端共享、
可审阅、不由模型生成）。本模块只做「查表 + 优先级」的纯函数，不做 IO 之外的判断。

优先级（一只宝可梦只归一类）：
  悖谬 > 幻兽 > 一级神 > 二级神 > 准神 > 普通
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

#: 分类键（与前端展示顺序一致）。
BATTLE_CLASS_KEYS = (
    "normal",
    "pseudo_legendary",
    "restricted",
    "sub_legendary",
    "mythical",
    "paradox",
)

#: 中文名（接口与页面共用这一份）。
BATTLE_CLASS_ZH: dict[str, str] = {
    "normal": "普通",
    "pseudo_legendary": "准神",
    "restricted": "一级神",
    "sub_legendary": "二级神",
    "mythical": "幻兽",
    "paradox": "悖谬",
}


class BattleClassDataUnavailable(RuntimeError):
    """规范数据缺失或损坏。接口应降级为「全部普通」而不是 500。"""


@dataclass(frozen=True)
class BattleClassTable:
    """解析后的分类清单。所有集合都是小写英文名（PokéAPI 的 name_en）。"""

    pseudo_legendary: frozenset[str]
    restricted: frozenset[str]
    paradox: frozenset[str]
    label: str

    def classify(self, name_en: str, *, is_legendary: bool, is_mythical: bool) -> str:
        """单只的分类。未知名称按普通处理（不猜）。"""
        key = name_en.strip().lower()
        if key in self.paradox:
            return "paradox"
        if is_mythical:
            return "mythical"
        if key in self.restricted:
            return "restricted"
        if is_legendary:
            return "sub_legendary"
        if key in self.pseudo_legendary:
            return "pseudo_legendary"
        return "normal"

    def names_for(self, battle_class: str) -> frozenset[str]:
        """某个分类的显式名单（普通 / 二级神 / 幻兽由字段推导，返回空集）。"""
        return {
            "pseudo_legendary": self.pseudo_legendary,
            "restricted": self.restricted,
            "paradox": self.paradox,
        }.get(battle_class, frozenset())


_lock = threading.Lock()
_cache: BattleClassTable | None = None
_cache_path: Path | None = None


def data_path() -> Path:
    return get_settings().data_dir / "battle-classes.json"


def load_battle_classes() -> BattleClassTable:
    """加载并校验分类清单；进程内缓存（测试可 `reset_battle_class_cache`）。"""
    global _cache, _cache_path
    path = data_path()
    with _lock:
        if _cache is not None and _cache_path == path:
            return _cache

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BattleClassDataUnavailable(f"缺少规范数据 {path}") from exc
        except json.JSONDecodeError as exc:
            raise BattleClassDataUnavailable(f"{path} 不是合法 JSON：{exc}") from exc

        def _names(field: str) -> frozenset[str]:
            values = raw.get(field)
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise BattleClassDataUnavailable(f"{path} 的 `{field}` 应为字符串数组")
            return frozenset(value.strip().lower() for value in values if value.strip())

        table = BattleClassTable(
            pseudo_legendary=_names("pseudo_legendary"),
            restricted=_names("restricted"),
            paradox=_names("paradox"),
            label=str(raw.get("source_label") or "项目整理"),
        )
        _cache = table
        _cache_path = path
        return table


def reset_battle_class_cache() -> None:
    """测试用：清空缓存，让下一次读取重新加载。"""
    global _cache, _cache_path
    with _lock:
        _cache = None
        _cache_path = None


def classify(
    name_en: str, *, is_legendary: bool, is_mythical: bool
) -> str:
    """便捷入口：数据缺失时返回 `normal`（不阻断图鉴浏览）。"""
    try:
        table = load_battle_classes()
    except BattleClassDataUnavailable:
        return "normal"
    return table.classify(name_en, is_legendary=is_legendary, is_mythical=is_mythical)


def class_zh(battle_class: str) -> str:
    return BATTLE_CLASS_ZH.get(battle_class, battle_class)


def counts_for(rows: list[tuple[str, bool, bool]]) -> Mapping[str, int]:
    """给定 (name_en, is_legendary, is_mythical) 列表，统计各分类数量。"""
    counts = {key: 0 for key in BATTLE_CLASS_KEYS}
    for name_en, is_legendary, is_mythical in rows:
        counts[classify(name_en, is_legendary=is_legendary, is_mythical=is_mythical)] += 1
    return counts
