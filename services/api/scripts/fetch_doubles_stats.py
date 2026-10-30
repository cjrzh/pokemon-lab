"""抓取 Smogon 双打统计数据，生成 `data/doubles/*.json`。

用法（在 services/api 目录下）：
    uv run python scripts/fetch_doubles_stats.py              # 抓取全部 4 个格式
    uv run python scripts/fetch_doubles_stats.py --format sv  # 只抓一个
    uv run python scripts/fetch_doubles_stats.py --labels     # 只补中文标签（PokéAPI）

输出（仓库根 data/doubles/）：
    champions.json / sv.json / swsh.json / bdsp.json
    labels.json   # 道具、性格、少量招式的官方中文名（PokéAPI zh-hans）

产物是**原始统计**：不包含图鉴编号，导入数据库时再按名称映射。
抓取是低频手动操作（每月一次即可），不做定时任务；页面始终标注统计月份。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.doubles_formats import (  # noqa: E402
    FORMAT_BY_KEY,
    FORMATS,
    DoublesFormat,
    dataset_meta,
    moveset_url,
    update_dataset_meta,
    usage_url,
)
from app.domain.smogon_stats import (  # noqa: E402
    load_nature_zh,
    parse_moveset_text,
    parse_usage_table,
    showdown_slug,
)

API_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = API_DIR.parents[1] / "data" / "doubles"

#: Showdown 与 PokéAPI 命名不一致的道具（人工核对过的官方中文名）。
LABEL_OVERRIDES: dict[str, dict[str, str]] = {
    "items": {"leek": "大葱", "pretty-feather": "美丽之羽"},
    "abilities": {
        "as-one-(glastrier)": "人马一体",
        "as-one-(spectrier)": "人马一体",
    },
    "moves": {},
}
#: Showdown 的占位名，不是真实道具 / 招式。
PLACEHOLDER_LABELS = {"items": {"nothing"}, "moves": {"nothing"}, "abilities": set()}


def _fetch(url: str, client: httpx.Client) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def build_dataset(fmt: DoublesFormat, usage_text: str, moveset_text: str) -> dict:
    usage = parse_usage_table(usage_text)
    blocks = parse_moveset_text(moveset_text)

    # 使用率表里没有配装明细的宝可梦只保留排名与使用率；
    # moveset 里有但使用率表没有的（极少）保留明细、排名为空。
    entries: list[dict] = []
    seen: set[str] = set()
    for row in usage.rows:
        block = blocks.get(row.name)
        seen.add(row.name)
        entries.append(
            {
                "name": row.name,
                "rank": row.rank,
                "usage": row.usage,
                **(_block_payload(block) if block else {}),
            }
        )

    for name, block in blocks.items():
        if name in seen:
            continue
        entries.append(
            {
                "name": name,
                "rank": None,
                "usage": None,
                **_block_payload(block),
            }
        )

    entries.sort(key=lambda entry: (entry["rank"] is None, entry["rank"] or 0, entry["name"]))

    return {
        "schema_version": 1,
        "format": dataset_meta(fmt),
        "battles": usage.battles,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "Smogon Usage Statistics（公开统计文本，非游戏客户端数据）",
        "entries": entries,
    }


def _block_payload(block) -> dict:
    def pairs(entries):
        return [
            [showdown_slug(name), pct]
            for name, pct in entries
            if showdown_slug(name) not in ("nothing", "other")
        ]

    return {
        "raw_count": block.raw_count,
        "abilities": pairs(block.abilities),
        "items": pairs(block.items),
        "moves": pairs(block.moves),
        "teammates": pairs(block.teammates),
        "tera_types": pairs(block.tera_types),
        "spreads": block.spreads,
    }


def collect_labels(datasets: list[dict], existing: dict) -> dict:
    """汇总所有名称 slug，并补齐已有中文标签。"""
    item_slugs: set[str] = set()
    move_slugs: set[str] = set()
    ability_slugs: set[str] = set()
    for dataset in datasets:
        for entry in dataset["entries"]:
            item_slugs.update(slug for slug, _ in entry.get("items", []))
            move_slugs.update(slug for slug, _ in entry.get("moves", []))
            ability_slugs.update(slug for slug, _ in entry.get("abilities", []))

    labels = dict(existing)
    labels["natures"] = load_nature_zh()
    for group, slugs in (
        ("items", item_slugs),
        ("moves", move_slugs),
        ("abilities", ability_slugs),
    ):
        current = dict(labels.get(group, {}))
        # 人工核对过的覆盖优先于上次抓取结果
        current.update(LABEL_OVERRIDES.get(group, {}))
        labels[group] = {
            slug: current.get(slug)
            for slug in sorted((set(current) | slugs) - PLACEHOLDER_LABELS.get(group, set()))
        }
    labels["source"] = "PokéAPI zh-hans（道具 / 招式 / 特性官方中文名；缺失项为 null）"
    return labels


def fetch_labels(labels: dict, *, workers: int = 8) -> dict:
    """为缺失的中文标签补查 PokéAPI。只处理 null / 不存在的键。"""
    kinds = {"items": "item", "moves": "move", "abilities": "ability"}
    jobs: list[tuple[str, str, str]] = []
    for group, kind in kinds.items():
        mapping = labels.setdefault(group, {})
        jobs.extend((group, kind, slug) for slug, zh in mapping.items() if not zh)

    def fetch_one(job: tuple[str, str, str]) -> tuple[str, str, str | None]:
        group, kind, slug = job
        with httpx.Client(
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
            follow_redirects=True,
        ) as client:
            try:
                response = client.get(f"https://pokeapi.co/api/v2/{kind}/{slug}")
                if response.status_code != 200:
                    return group, slug, None
                payload = response.json()
                return (
                    group,
                    slug,
                    next(
                        (
                            name["name"]
                            for name in payload.get("names", [])
                            if name["language"]["name"] == "zh-hans"
                        ),
                        None,
                    ),
                )
            except httpx.HTTPError:
                return group, slug, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, (group, slug, zh) in enumerate(pool.map(fetch_one, jobs), start=1):
            if zh:
                labels[group][slug] = zh
                print(f"  {slug} → {zh}")
            if index % 100 == 0:
                print(f"  … {index}/{len(jobs)}")
    return labels


#: Showdown 英文名与 slug 的特殊对应（括号形态）。
SHOWDOWN_NAME_OVERRIDES: dict[str, dict[str, str]] = {
    "items": {"leek": "Leek", "pretty-feather": "Pretty Feather"},
    "abilities": {
        "as-one-(glastrier)": "As One (Glastrier)",
        "as-one-(spectrier)": "As One (Spectrier)",
    },
    "moves": {},
}


def _showdown_toid(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def fetch_showdown_names(labels: dict) -> dict:
    """补齐 Showdown 英文名（生成导出代码用）。

    来源是 Showdown 公开客户端的 data 文件：
      moves.json / items.js / abilities.js。
    这些名称是贴进 Showdown 的正确写法（如 `U-turn`、`Will-O-Wisp`、`Charizardite Y`）。
    """
    with httpx.Client(
        timeout=httpx.Timeout(60.0, connect=10.0),
        headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
        follow_redirects=True,
    ) as client:
        moves = client.get("https://play.pokemonshowdown.com/data/moves.json").json()
        items_js = client.get("https://play.pokemonshowdown.com/data/items.js").text
        abilities_js = client.get("https://play.pokemonshowdown.com/data/abilities.js").text

    move_names = {
        key: value["name"]
        for key, value in moves.items()
        if isinstance(value, dict) and value.get("name")
    }

    def parse_js_table(text: str) -> dict[str, str]:
        table: dict[str, str] = {}
        for match in re.finditer(r"([a-zA-Z0-9]+):\{", text):
            name = re.search(r'name:"([^"]+)"', text[match.end() : match.end() + 300])
            if name:
                table[match.group(1)] = name.group(1)
        return table

    item_names = parse_js_table(items_js)
    ability_names = parse_js_table(abilities_js)
    tables = {"items": item_names, "moves": move_names, "abilities": ability_names}

    for group, table in tables.items():
        en: dict[str, str] = {}
        overrides = SHOWDOWN_NAME_OVERRIDES.get(group, {})
        for slug in labels.get(group, {}):
            candidates = (slug, _showdown_toid(slug), slug.replace("-", ""))
            value = next((table[c] for c in candidates if c in table), None)
            if value is None:
                value = overrides.get(slug) or next(
                    (v for k, v in overrides.items() if _showdown_toid(k) == _showdown_toid(slug)),
                    None,
                )
            if value:
                en[slug] = value
        labels[f"{group}_en"] = en
        print(f"  {group} 英文名：{len(en)}/{len(labels.get(group, {}))}")
    labels["name_source"] = (
        "Pokémon Showdown 公开客户端数据（moves.json / items.js / abilities.js），"
        "用于生成 Showdown 导出代码"
    )
    return labels


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--format",
        choices=sorted(FORMAT_BY_KEY),
        action="append",
        help="只抓指定格式（可重复）；默认全部",
    )
    parser.add_argument("--labels", action="store_true", help="抓取后用 PokéAPI 补齐中文标签")
    parser.add_argument(
        "--labels-only",
        action="store_true",
        help="不重新抓取统计数据，只汇总并补齐 labels.json（新格式首次全量标签约 1–2 分钟）",
    )
    parser.add_argument(
        "--showdown-names",
        action="store_true",
        help="同时抓取 Showdown 英文名（生成导出代码用）",
    )
    parser.add_argument(
        "--meta-only",
        action="store_true",
        help="只把数据文件里的格式元数据（顺序 / 交易前缀 / 默认等级）刷新成当前定义，不联网",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    labels_path = DATA_DIR / "labels.json"
    existing_labels = (
        json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}
    )

    selected = [FORMAT_BY_KEY[key] for key in (args.format or [])] if args.format else list(FORMATS)
    datasets: list[dict] = []

    if not args.labels_only and not args.meta_only:
        with httpx.Client(
            timeout=httpx.Timeout(120.0, connect=15.0),
            headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
            follow_redirects=True,
        ) as client:
            for fmt in selected:
                print(f"抓取 {fmt.label}（{fmt.month}，cutoff {fmt.cutoff}）…")
                usage_text = _fetch(usage_url(fmt), client)
                moveset_text = _fetch(moveset_url(fmt), client)
                dataset = build_dataset(fmt, usage_text, moveset_text)
                write_json(DATA_DIR / f"{fmt.key}.json", dataset)
                datasets.append(dataset)
                print(
                    f"  ✓ {len(dataset['entries'])} 条记录 · {dataset['battles']} 场对战"
                    f" → data/doubles/{fmt.key}.json"
                )

    # 只重新汇总已抓取的格式；保留其它格式已有的条目
    for path in DATA_DIR.glob("*.json"):
        if path.name == "labels.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format", {}).get("key") not in {d["format"]["key"] for d in datasets}:
            datasets.append(data)
    if args.meta_only:
        written = update_dataset_meta(sorted(DATA_DIR.glob("*.json")))
        print(f"已刷新 {len(written)} 个数据文件的格式元数据：{[p.stem for p in written]}")

    labels = collect_labels(datasets, existing_labels)
    if args.labels or args.labels_only:
        missing = sum(
            1
            for group in ("items", "moves", "abilities")
            for value in labels[group].values()
            if not value
        )
        print(f"补齐中文标签（PokéAPI，{missing} 个待查）…")
        labels = fetch_labels(labels)
    if args.showdown_names or args.labels_only:
        print("补齐 Showdown 英文名…")
        labels = fetch_showdown_names(labels)
    write_json(labels_path, labels)

    print(f"标签文件：{labels_path}（道具 {len(labels['items'])} / 招式 {len(labels['moves'])}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.HTTPError as exc:
        print(f"抓取失败：{exc}", file=sys.stderr)
        sys.exit(2)
