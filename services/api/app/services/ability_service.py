"""特性（Ability）数据服务。

特性与宝可梦是多对多关系：同一特性被多只宝可梦共享（如「威吓」35 只），
因此单独建 `ability` 参考表，`pokemon.abilities_json` 仍然保存「谁拥有哪个特性」。

数据来源与优先级：
  1. 特性中文名 / 说明：从已同步的 `pokemon.abilities_json` 汇总；
     上游缺中文说明时，用 `data/flavor-zh/abilities-zh.json` 的项目自译兜底。
  2. S 级评级：`data/abilities/s-tier.json` 的 LLM 预评（`rating_source=llm`）。
     人工在页面上改过的评级会标记 `manual`，后续自动预评**不会覆盖**人工结论。

`sync_abilities()` 是幂等的：每次同步/回填都可以调用，只更新缺失或变化的字段。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Ability, Pokemon, PokemonForm

logger = logging.getLogger(__name__)

TIER_S = "s"
TIER_NORMAL = "normal"
TIERS = (TIER_S, TIER_NORMAL)

SOURCE_LLM = "llm"
SOURCE_MANUAL = "manual"

RATING_FILE = Path("abilities") / "s-tier.json"
EFFECT_TRANSLATION_FILE = Path("flavor-zh") / "abilities-zh.json"


class AbilityRatingError(RuntimeError):
    """评级 / 译文文件损坏。属于仓库数据问题，应在同步或测试时暴露。"""


@dataclass(frozen=True)
class RatingEntry:
    tier: str
    note: str | None


def _data_dir() -> Path:
    return get_settings().data_dir


def load_ratings() -> dict[str, RatingEntry]:
    """读取 LLM 预评文件：ability name → 评级与理由。"""
    path = _data_dir() / RATING_FILE
    if not path.exists():
        logger.warning("S 级评级文件不存在，跳过自动评级：%s", path)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        tiers = payload["tiers"]
        ratings: dict[str, RatingEntry] = {}
        for name, entry in tiers.items():
            tier = str(entry["tier"])
            if tier not in TIERS:
                raise AbilityRatingError(f"非法评级 {tier!r}（特性 {name}）")
            ratings[name] = RatingEntry(tier=tier, note=entry.get("note"))
        return ratings
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AbilityRatingError(f"评级文件损坏（{path}）：{exc}") from exc


def load_name_translations() -> dict[str, str]:
    """读取特性中文名兜底：ability name → 中文名。

    形态独有特性（如蕾冠王的「人马一体」）在 `pokemon.abilities_json` 里不存在，
    `ability.zh` 因此为空；这里从译文文件的 `names` 字段补上。
    """
    path = _data_dir() / EFFECT_TRANSLATION_FILE
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        names = payload.get("names") or {}
        return {str(name): str(text).strip() for name, text in names.items() if str(text).strip()}
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise AbilityRatingError(f"特性译文文件损坏（{path}）：{exc}") from exc


def load_effect_translations() -> dict[str, str]:
    """读取特性中文说明兜底译文：ability name → 中文说明。"""
    path = _data_dir() / EFFECT_TRANSLATION_FILE
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(name): str(text).strip()
            for name, text in payload["entries"].items()
            if str(text).strip()
        }
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AbilityRatingError(f"特性译文文件损坏（{path}）：{exc}") from exc


def collect_ability_records(
    pokemon_rows: list[Pokemon],
    form_rows: list[PokemonForm] | None = None,
) -> dict[str, dict]:
    """从宝可梦记录汇总特性：name → {zh, effect_zh, effect_en, users}。

    `form_rows` 是形态记录：形态可能带**独有特性**（蕾冠王的「人马一体」、
    阿罗拉形态的特性等），只扫 `pokemon` 表会让这些特性永远进不了参考表，
    界面就只剩一个 slug。形态条目通常只有 `name`，中文靠译文文件兜底。
    """
    merged: dict[str, dict] = {}

    def fold(abilities_json: str | None, dex_number: int) -> None:
        try:
            abilities = json.loads(abilities_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(abilities, list):
            return
        for ability in abilities:
            if not isinstance(ability, dict):
                continue
            name = ability.get("name")
            if not name:
                continue
            entry = merged.setdefault(
                name,
                {
                    "zh": None,
                    "effect_zh": None,
                    "effect_en": None,
                    "users": [],
                },
            )
            if not entry["zh"] and ability.get("zh"):
                entry["zh"] = ability["zh"]
            if not entry["effect_zh"] and ability.get("effect_zh"):
                entry["effect_zh"] = ability["effect_zh"]
            if not entry["effect_en"] and ability.get("effect_en"):
                entry["effect_en"] = ability["effect_en"]
            if dex_number not in entry["users"]:
                entry["users"].append(dex_number)

    for pokemon in pokemon_rows:
        fold(pokemon.abilities_json, pokemon.dex_number)
    for form in form_rows or []:
        fold(form.abilities_json, form.dex_number)
    return merged


async def sync_abilities(session: AsyncSession) -> dict:
    """把宝可梦记录里的特性汇总进 `ability` 表，并应用自动评级。

    返回统计：{"abilities": 总数, "s_tier": S 级数, "new": 新增数}。
    """
    rows = list((await session.execute(select(Pokemon))).scalars().all())
    forms = list((await session.execute(select(PokemonForm))).scalars().all())
    aggregated = collect_ability_records(rows, forms)
    translations = load_effect_translations()
    name_translations = load_name_translations()
    ratings = load_ratings()

    existing = {
        ability.name: ability
        for ability in (await session.execute(select(Ability))).scalars().all()
    }

    new_count = 0
    for name, data in aggregated.items():
        effect_zh = data["effect_zh"] or translations.get(name)
        zh = data["zh"] or name_translations.get(name)
        ability = existing.get(name)
        if ability is None:
            ability = Ability(
                name=name,
                zh=zh,
                effect_zh=effect_zh,
                effect_en=data["effect_en"],
            )
            session.add(ability)
            existing[name] = ability
            new_count += 1
        else:
            # 只补缺失字段，不覆盖已有中文（上游优先，其次是已落库的译文）
            if not ability.zh and zh:
                ability.zh = zh
            if not ability.effect_zh and effect_zh:
                ability.effect_zh = effect_zh
            if not ability.effect_en and data["effect_en"]:
                ability.effect_en = data["effect_en"]

        # 自动评级只在人工没有覆盖时应用
        rating = ratings.get(name)
        if rating is not None and ability.rating_source != SOURCE_MANUAL:
            ability.tier = rating.tier
            ability.rating_note = rating.note
            ability.rating_source = SOURCE_LLM

    await session.flush()

    s_tier_count = sum(1 for a in existing.values() if a.tier == TIER_S)
    return {
        "abilities": len(aggregated),
        "s_tier": s_tier_count,
        "new": new_count,
    }
