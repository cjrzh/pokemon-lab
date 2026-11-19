"""生成本地形态 → Pokémon Showdown 显示名 的映射（`data/forms/showdown.json`）。

为什么需要：
  本地图鉴的形态名来自 PokéAPI（`rotom-wash` / `ogerpon-wellspring-mask` /
  `indeedee-female`），而队伍导出、Smogon 统计、交换机器人都用 Showdown 口径
  （`Rotom-Wash` / `Ogerpon-Wellspring` / `Indeedee-F`）。建队时选了形态，
  必须能换算出 Showdown 名，导出的代码与使用率推荐才会对得上。

来源：`https://play.pokemonshowdown.com/data/pokedex.json`（公开数据文件）。
匹配规则（按优先级）：
  1. 归一化后完全一致（`rotom-wash` ↔ `Rotom-Wash`）；
  2. 同一图鉴编号下，按「形态后缀词袋重合度」打分取唯一最高
     （`ogerpon-wellspring-mask` ↔ `Ogerpon-Wellspring`，
       `tauros-paldea-aqua-breed` ↔ `Tauros-Paldea-Aqua`）；
  3. 少量人工别名（如本地 `maushold-family-of-three` 对应 Showdown 的默认
     条目 `Maushold`）—— 都是「两个名字对不上但语义明确」的情况，写在
     `CURATED` 里并注明原因。

同一个来源还生成**超极巨化清单**（`gigantamax`）：Showdown 用
`canGigantamax`（G 招式名）标记哪些物种 / 形态能超极巨化。建队页据此显示
「超极巨化」开关，保存校验据此拒绝没有 G 形态的配置。

用法（在 services/api 目录下）：
    uv run python scripts/gen_form_showdown.py            # 生成（联网）
    uv run python scripts/gen_form_showdown.py --offline  # 用 api_cache 里的副本

生成的 JSON 入库（`data/` 是项目规范数据目录），运行时由
`app/services/form_service.py:load_form_showdown_map()` 读取。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.engine import init_db, session_scope  # noqa: E402
from app.db.models import Pokemon, PokemonForm  # noqa: E402
from app.domain.smogon_stats import showdown_slug  # noqa: E402

POKEDEX_URL = "https://play.pokemonshowdown.com/data/pokedex.json"
OUTPUT = Path("forms") / "showdown.json"

#: 形态词的同义词（本地 PokéAPI 写法 → Showdown 写法）。
_TOKEN_SYNONYMS = {
    "female": "f",
    "male": "m",
    "hisuian": "hisui",
    "alolan": "alola",
    "galarian": "galar",
    "paldean": "paldea",
    "standard": "",
    "breed": "",
    "mask": "",
    "forme": "",
    "form": "",
}

#: 人工别名：两边名字对不上、但语义明确的少数形态。
CURATED: dict[str, tuple[str, str]] = {
    "urshifu-single-strike": ("Urshifu", "Showdown 的一击流即默认 Urshifu，连击流另有条目"),
    "tatsugiri-curly": ("Tatsugiri", "Showdown 的默认米立龙是卷卷形态"),
    "tatsugiri-droopy": ("Tatsugiri-Droopy", "下垂形态"),
    "tatsugiri-stretchy": ("Tatsugiri-Stretchy", "伸展形态"),
    "minior-red-meteor": ("Minior-Meteor", "默认的流星形态"),
    "maushold-family-of-three": ("Maushold", "Showdown 的默认条目就是一家三口"),
    "maushold-family-of-four": ("Maushold-Four", "Showdown 用 -Four 后缀表示一家四口"),
    "indeedee-male": ("Indeedee", "Showdown 的默认条目是雄性爱管侍"),
    "indeedee-female": ("Indeedee-F", "雌性用 -F 后缀"),
    "basculegion-male": ("Basculegion", "Showdown 默认条目为雄性"),
    "basculegion-female": ("Basculegion-F", "雌性用 -F 后缀"),
    "meowstic-male": ("Meowstic", "Showdown 默认条目为雄性"),
    "pyroar-male": ("Pyroar", "Showdown 默认条目为雄性"),
    "oinkologne-male": ("Oinkologne", "Showdown 默认条目为雄性"),
    "rockruff-own-tempo": ("Rockruff-Dusk", "我行我素岩狗狗对应 Showdown 的 Dusk 条目"),
    "necrozma-dawn": ("Necrozma-Dawn-Wings", "拂晓之翼"),
    "necrozma-dusk": ("Necrozma-Dusk-Mane", "黄昏之鬃"),
    "zygarde-50-power-construct": ("Zygarde", "50% 形态（群聚变形）即 Showdown 的默认 Zygarde"),
    "zygarde-10-power-construct": ("Zygarde-10%", "10% 形态（群聚变形）"),
    "ogerpon-wellspring-mask": ("Ogerpon-Wellspring", "面具后缀在 Showdown 里省略 Mask"),
    "ogerpon-hearthflame-mask": ("Ogerpon-Hearthflame", "面具后缀在 Showdown 里省略 Mask"),
    "ogerpon-cornerstone-mask": ("Ogerpon-Cornerstone", "面具后缀在 Showdown 里省略 Mask"),
    # 小陨星（Minior）的核心颜色在 Showdown 里不影响对战（核心形态才会变身），
    # 全部归一到同一个条目，避免建队时导出不存在的名字。
    "minior-red": ("Minior", "核心颜色只是外观差异"),
    "minior-orange": ("Minior", "核心颜色只是外观差异"),
    "minior-yellow": ("Minior", "核心颜色只是外观差异"),
    "minior-green": ("Minior", "核心颜色只是外观差异"),
    "minior-blue": ("Minior", "核心颜色只是外观差异"),
    "minior-indigo": ("Minior", "核心颜色只是外观差异"),
    "minior-violet": ("Minior", "核心颜色只是外观差异"),
}


def _tokens(value: str) -> list[str]:
    return [part for part in re.split(r"[-_\s]+", value.lower()) if part]


def _normalized_tokens(value: str) -> list[str]:
    out: list[str] = []
    for token in _tokens(value):
        mapped = _TOKEN_SYNONYMS.get(token)
        if mapped is None:
            out.append(token)
        elif mapped:
            out.append(mapped)
    return out


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _score(local: str, showdown_name: str) -> float:
    """本地形态名与 Showdown 名的相似度（只看形态后缀词袋）。"""
    local_tokens = _normalized_tokens(local)
    sd_tokens = _normalized_tokens(showdown_name)
    if not local_tokens or not sd_tokens:
        return 0.0
    local_suffix = local_tokens[1:]
    sd_suffix = sd_tokens[1:]
    if not local_suffix or not sd_suffix:
        return 0.0
    common = set(local_suffix) & set(sd_suffix)
    return len(common) / max(len(local_suffix), len(sd_suffix))


def build_mapping(
    forms: list[tuple[str, int]],
    bases: dict[int, str],
    pokedex: dict[str, dict],
) -> tuple[dict[str, str], list[dict]]:
    """返回（形态 → Showdown 名, 未能匹配的清单）。"""
    by_dex: dict[int, list[str]] = {}
    seen: set[str] = set()
    for entry in pokedex.values():
        name = str(entry.get("name") or "")
        num = entry.get("num")
        if not isinstance(num, int) or not name or name in seen:
            continue
        seen.add(name)
        by_dex.setdefault(num, []).append(name)

    mapping: dict[str, str] = {}
    unmatched: list[dict] = []
    for form_name, dex_number in forms:
        if form_name in CURATED:
            mapping[form_name] = CURATED[form_name][0]
            continue
        candidates = by_dex.get(dex_number, [])
        exact = next((name for name in candidates if _key(name) == _key(form_name)), None)
        if exact:
            mapping[form_name] = exact
            continue
        scored = sorted(
            ((score, name) for name in candidates if (score := _score(form_name, name)) > 0),
            reverse=True,
        )
        if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            mapping[form_name] = scored[0][1]
            continue
        # 默认形态：本地带「默认后缀」（`-normal` / `-standard` / `-incarnate` …），
        # Showdown 直接用不带后缀的名字。取「候选名是本地名的词前缀」的那一个。
        if bases.get(dex_number) == form_name:
            local_prefix = _normalized_tokens(form_name)
            prefix_matches = [
                name
                for name in candidates
                if _normalized_tokens(name) == local_prefix[: len(_normalized_tokens(name))]
            ]
            if len(prefix_matches) == 1:
                mapping[form_name] = prefix_matches[0]
                continue
        unmatched.append(
            {
                "form": form_name,
                "dex": dex_number,
                "base": bases.get(dex_number),
                "candidates": candidates,
                "scores": [(round(score, 2), name) for score, name in scored[:4]],
            }
        )
    return mapping, unmatched


def build_gigantamax_mapping(
    dex_numbers: set[int], pokedex: dict[str, dict]
) -> dict[str, dict]:
    """Showdown 名（slug）→ 超极巨化信息，只保留本地图鉴里有的物种。

    Showdown 的 `pokedex.json` 在能超极巨化的条目上带 `canGigantamax`（G 招式名），
    例如 `Charizard` → `G-Max Wildfire`、`Urshifu-Rapid-Strike` → `G-Max Rapid Flow`。
    **键用 Showdown 自己的名字**而不是本地 slug：本地默认名常带形态后缀
    （`urshifu-single-strike`、`toxtricity-amped`），与 Showdown 的 `Urshifu` /
    `Toxtricity` 对不上，直接用本地名会漏掉这两个物种。

    返回结构：`{slug: {showdown_name, gmax_name, gmax_move}}`。没有 G 形态的
    物种不会出现在结果里 —— 建队页据此只对有 G 形态的宝可梦显示开关。
    """
    mapping: dict[str, dict] = {}
    for entry in pokedex.values():
        num = entry.get("num")
        name = entry.get("name")
        move = entry.get("canGigantamax")
        if not isinstance(num, int) or num not in dex_numbers:
            continue
        if not isinstance(name, str) or not isinstance(move, str):
            continue
        mapping[showdown_slug(name)] = {
            "showdown_name": name,
            "gmax_name": f"{name}-Gmax",
            "gmax_move": move,
        }
    return mapping


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="用 api_cache 里的副本")
    args = parser.parse_args()

    await init_db()
    async with session_scope() as session:
        pokemon_rows = (await session.execute(select(Pokemon))).scalars().all()
        bases = {row.dex_number: row.name_en for row in pokemon_rows}
        # 默认形态也要映射：`maushold-family-of-four` → `Maushold-Four`、
        # `indeedee-male` → `Indeedee` 这类本地默认名与 Showdown 名并不相同。
        forms = [(row.name_en, row.dex_number) for row in pokemon_rows]
        forms += [
            (row.name, row.dex_number)
            for row in (await session.execute(select(PokemonForm))).scalars().all()
        ]

    pokedex: dict[str, dict] | None = None
    if args.offline:
        from app.db.engine import get_session_factory
        from app.repositories import api_cache_repo

        async with get_session_factory()() as session:
            cached = await api_cache_repo.get_cache_entry(session, "showdown:pokedex", now=0)
        if cached is not None:
            pokedex = json.loads(cached.payload)
    if pokedex is None:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True, trust_env=False) as client:
            response = await client.get(POKEDEX_URL)
            response.raise_for_status()
            pokedex = response.json()

    mapping, unmatched = build_mapping(forms, bases, pokedex)
    # 超极巨化清单按「本地图鉴里存在的物种」过滤；键用 Showdown 自己的名字
    gigantamax = build_gigantamax_mapping(set(bases), pokedex)

    path = get_settings().data_dir / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "本地形态名（PokéAPI 口径）→ Pokémon Showdown 显示名。"
            "由 scripts/gen_form_showdown.py 生成，不要手工改；新形态同步后重跑即可。"
            "`gigantamax` 是能超极巨化的物种 / 形态清单（键为 showdown_slug）。"
        ),
        "source": POKEDEX_URL,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "forms": dict(sorted(mapping.items())),
        "gigantamax": dict(sorted(gigantamax.items())),
        "curated": {
            name: {"showdown": value, "reason": reason}
            for name, (value, reason) in sorted(CURATED.items())
        },
        "unmatched": unmatched,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"已写入 {path}：{len(mapping)} 个形态，{len(gigantamax)} 个可超极巨化，"
        f"未匹配 {len(unmatched)} 个"
    )
    for item in unmatched:
        print(f"  未匹配 {item['form']}（#{item['dex']}）候选：{item['candidates']}")
    return 0 if not unmatched else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
