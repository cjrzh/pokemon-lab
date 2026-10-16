"""生成规范属性克制表 `data/type-chart.json`。

数据流：PokéAPI `/type/{id}` 的 damage_relations → 反推 → 稀疏克制表 + 来源标注。

用法（在 services/api 目录下）：
    uv run python scripts/gen_type_chart.py           # 拉取并生成/更新 data/type-chart.json
    uv run python scripts/gen_type_chart.py --check   # 只校验本地文件与测试向量，不写入

两个护栏：
  1. 生成时校验 damage_relations 内部一致性（同一对属性不允许同时出现在
     double 与 half/no 列表里），避免上游数据异常时产出错表。
  2. 若 `data/type-chart.cases.json` 存在，逐条核对测试向量的期望值与
     拉取到的克制表一致 —— 手写向量里的笔误在这里被拦下，而不是等两端测试
     「一致地错下去」。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# 允许 `uv run python scripts/gen_type_chart.py` 直接运行：把 services/api 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.core.config import get_settings  # noqa: E402

#: PokéAPI 中 1–18 号属性即官方顺序（normal…fairy）；10001+ 为阴影/未知属性，不取。
TYPE_IDS = range(1, 19)

#: 兜底中文名：仅当上游缺少 zh-Hans 本地化时使用（理论上不会发生）。
ZH_FALLBACK = {
    "normal": "一般",
    "fire": "火",
    "water": "水",
    "electric": "电",
    "grass": "草",
    "ice": "冰",
    "fighting": "格斗",
    "poison": "毒",
    "ground": "地面",
    "flying": "飞行",
    "psychic": "超能力",
    "bug": "虫",
    "rock": "岩石",
    "ghost": "幽灵",
    "dragon": "龙",
    "dark": "恶",
    "steel": "钢",
    "fairy": "妖精",
}


class TypeChartBuildError(RuntimeError):
    """生成过程中发现数据不一致，拒绝产出可能错误的克制表。"""


@dataclass(frozen=True)
class RawType:
    name: str
    zh: str
    double_damage_to: tuple[str, ...]
    half_damage_to: tuple[str, ...]
    no_damage_to: tuple[str, ...]


def fetch_raw_types(client: httpx.Client) -> list[RawType]:
    """拉取 18 个属性的 damage_relations 与中文名。"""
    raws: list[RawType] = []
    for type_id in TYPE_IDS:
        response = client.get(f"/type/{type_id}")
        response.raise_for_status()
        payload = response.json()

        zh = next(
            (n["name"] for n in payload["names"] if n["language"]["name"] == "zh-Hans"),
            ZH_FALLBACK.get(payload["name"], payload["name"]),
        )
        raws.append(
            RawType(
                name=payload["name"],
                zh=zh,
                double_damage_to=tuple(
                    d["name"] for d in payload["damage_relations"]["double_damage_to"]
                ),
                half_damage_to=tuple(
                    d["name"] for d in payload["damage_relations"]["half_damage_to"]
                ),
                no_damage_to=tuple(d["name"] for d in payload["damage_relations"]["no_damage_to"]),
            )
        )
    return raws


def build_chart(raws: list[RawType]) -> dict[str, dict[str, float]]:
    """从 damage_relations 反推稀疏克制表（attack → {defense: 倍率}，缺省 1.0）。"""
    known = {raw.name for raw in raws}

    chart: dict[str, dict[str, float]] = {}
    for raw in raws:
        # 同一防守属性不允许同时出现在多个列表里 —— 这是 PokéAPI 数据的硬约束
        seen: dict[str, str] = {}
        for list_name, names in (
            ("double_damage_to", raw.double_damage_to),
            ("half_damage_to", raw.half_damage_to),
            ("no_damage_to", raw.no_damage_to),
        ):
            for defender in names:
                if defender not in known:
                    raise TypeChartBuildError(f"{raw.name} 的 {list_name} 含未知属性 {defender!r}")
                if defender in seen:
                    raise TypeChartBuildError(
                        f"{raw.name} 对 {defender} 同时出现在 {seen[defender]} 与 {list_name}"
                    )
                seen[defender] = list_name

        row: dict[str, float] = {}
        for defender in raw.double_damage_to:
            row[defender] = 2.0
        for defender in raw.half_damage_to:
            row[defender] = 0.5
        for defender in raw.no_damage_to:
            row[defender] = 0.0
        chart[raw.name] = row

    return chart


def validate_cases(chart: dict[str, dict[str, float]], cases_path: Path) -> None:
    """逐条核对测试向量的期望值与刚生成的克制表一致。"""
    if not cases_path.exists():
        print(f"跳过测试向量校验（未找到 {cases_path}）")
        return

    cases_payload = json.loads(cases_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    for case in cases_payload["cases"]:
        case_id = case.get("id", "<无id>")
        if case["kind"] == "evaluate":
            expected = float(case["expected"])
            actual = 1.0
            for defense in case["defense"]:
                actual *= chart[case["attack"]].get(defense, 1.0)
            if actual != expected:
                errors.append(
                    f"[{case_id}] {case['attack']} → {case['defense']}:"
                    f" 期望 {expected}，实际 {actual}"
                )
        elif case["kind"] == "reverse":
            for attack, expected in case["expected"].items():
                actual = 1.0
                for defense in case["defense"]:
                    actual *= chart[attack].get(defense, 1.0)
                if actual != float(expected):
                    errors.append(
                        f"[{case_id}] 反查 {case['defense']} 中 {attack}:"
                        f" 期望 {expected}，实际 {actual}"
                    )
            # 期望里列出的必须是全部非 1 倍项
            actual_non_neutral = {
                attack: multiplier
                for attack in chart
                if (multiplier := _product(chart, attack, case["defense"])) != 1.0
            }
            missing = set(actual_non_neutral) - set(case["expected"])
            if missing:
                errors.append(f"[{case_id}] 反查 {case['defense']} 漏了: {sorted(missing)}")

    if errors:
        raise TypeChartBuildError("测试向量与 PokéAPI 数据不一致：\n  " + "\n  ".join(errors))
    print(f"测试向量校验通过：{len(cases_payload['cases'])} 条")


def _product(chart: dict[str, dict[str, float]], attack: str, defense: list[str]) -> float:
    result = 1.0
    for defense_type in defense:
        result *= chart[attack].get(defense_type, 1.0)
    return result


def render_document(chart: dict[str, dict[str, float]], raws: list[RawType]) -> dict:
    """组装带元数据的规范文档。"""
    return {
        "schema_version": 1,
        "label": "属性克制表 · Gen 6+",
        "generation": {"min": 6, "max": 9, "note": "第 6 代起规则一致；Gen 1–5 差异后续逐代补齐"},
        "types": [{"name": raw.name, "zh": raw.zh} for raw in raws],
        "chart": chart,
        "source": {
            "upstream": "https://pokeapi.co/api/v2/type/{id} (1-18)",
            "method": "由 damage_relations 反推（double=2 / half=0.5 / no=0，缺省 1.0）",
            "generator": "services/api/scripts/gen_type_chart.py",
            "fetched_at": date.today().isoformat(),
            "license_note": (
                "游戏数据版权归 任天堂 / GAME FREAK / Creatures Inc.；本项目仅作个人非商业学习用途"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只校验，不写入文件")
    args = parser.parse_args()

    settings = get_settings()
    chart_path = settings.data_dir / "type-chart.json"
    cases_path = settings.data_dir / "type-chart.cases.json"

    with httpx.Client(
        base_url=settings.pokeapi_base_url,
        timeout=httpx.Timeout(settings.pokeapi_read_timeout_seconds),
        headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
        follow_redirects=True,
    ) as client:
        raws = fetch_raw_types(client)

    chart = build_chart(raws)
    validate_cases(chart, cases_path)

    document = render_document(chart, raws)
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        existing = chart_path.read_text(encoding="utf-8") if chart_path.exists() else ""
        if existing == rendered:
            print(f"校验通过：{chart_path} 与上游一致")
            return 0
        print(f"校验失败：{chart_path} 与上游数据不一致（fetched_at 字段除外，见下）")
        # fetched_at 每天变化会导致 diff，比较时忽略它
        import re

        normalized_existing = re.sub(r'"fetched_at": "[^"]*"', '"fetched_at": "<date>"', existing)
        normalized_rendered = re.sub(r'"fetched_at": "[^"]*"', '"fetched_at": "<date>"', rendered)
        if normalized_existing == normalized_rendered:
            print("仅 fetched_at 日期不同，数据本身一致")
            return 0
        return 1

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(rendered, encoding="utf-8")
    print(f"已生成：{chart_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (TypeChartBuildError, httpx.HTTPError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        sys.exit(2)
