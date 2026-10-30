"""双打对战数据源的格式化定义。

四个关注的格式（均为双打）：
  - bdsp：BDSP 双打（Smogon gen8bdspdoublesou）
  - swsh：剑盾 VGC 2022（gen8vgc2022，含剑盾全部可用宝可梦）
  - sv：朱紫 VGC 2026 Reg I（gen9vgc2026regi，最后一个朱紫官方规则）
  - champions：宝可梦冠军 VGC 2026 Reg M-C（gen9championsvgc2026regmc）

每个格式固定「抓取月份 + 等级线」：Smogon 的 moveset 文件在高分段往往只收录
样本量足够的宝可梦，因此选档原则是「样本量优先」——BDSP / 剑盾受限于历史，
只能选低等级线；朱紫 / 冠军取 1630 / 1760。选择结果写进数据文件，页面如实展示
统计月份与等级线，不把旧数据冒充成当前环境。

格式定义是纯数据，供脚本抓取与入库共用；不包含任何 IO。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: 配点类型：旧世代是 EV（0–252），Champions 是能力点（0–32）。
POINTS_EV = "ev"
POINTS_STAT = "stat_points"


@dataclass(frozen=True)
class DoublesFormat:
    """一个双打格式的抓取参数与展示文案。"""

    key: str
    label: str
    short_label: str
    game: str
    ruleset: str
    #: Smogon 格式 id（url 中使用的名字）
    smogon_format: str
    #: 抓取的统计月份（YYYY-MM）
    month: str
    #: 等级线（cutoff）
    cutoff: int
    #: 配点含义
    points_kind: str
    #: 数据覆盖说明（为什么选这个月份 / 等级线）
    note: str
    #: 导出的 Showdown 交易命令前缀（Chatot 等交换机器人使用）；None 表示不需要
    trade_prefix: str | None = None
    #: 导出代码的默认等级（VGC 为 50，BDSP 双打 OU 为 100）
    default_level: int = 50


#: 顺序即页面上的标签顺序：BDSP → 剑盾 → 朱紫 → 冠军（按交换机器人使用频率与用户习惯）。
FORMATS: tuple[DoublesFormat, ...] = (
    DoublesFormat(
        key="bdsp",
        label="晶灿钻石／明亮珍珠 · 双打",
        short_label="BDSP",
        game="Brilliant Diamond & Shining Pearl",
        ruleset="Doubles OU",
        smogon_format="gen8bdspdoublesou",
        month="2021-12",
        cutoff=1500,
        points_kind=POINTS_EV,
        note="BDSP 双打活跃期较早（2021-12 对战量最大），1500 等级线覆盖最广。",
        trade_prefix="!tradeBDSP",
        default_level=100,
    ),
    DoublesFormat(
        key="swsh",
        label="剑盾 · VGC 2022",
        short_label="剑盾",
        game="Sword & Shield",
        ruleset="VGC 2022",
        smogon_format="gen8vgc2022",
        month="2022-11",
        cutoff=1630,
        points_kind=POINTS_EV,
        note="剑盾末期（2022-11）天梯统计；1630 等级线保留更多宝可梦样本。",
        trade_prefix="!tradeSWSH",
        default_level=50,
    ),
    DoublesFormat(
        key="sv",
        label="朱紫 · VGC 2026 Reg I",
        short_label="朱紫",
        game="Scarlet & Violet",
        ruleset="VGC 2026 Reg I",
        smogon_format="gen9vgc2026regi",
        month="2026-04",
        cutoff=1630,
        points_kind=POINTS_EV,
        note="朱紫最后一个官方双打规则（Reg I）的天梯统计。",
        trade_prefix="!tradeSV",
        default_level=50,
    ),
    DoublesFormat(
        key="champions",
        label="宝可梦冠军 · VGC 2026 Reg M-C",
        short_label="冠军",
        game="Pokémon Champions",
        ruleset="VGC 2026 Reg M-C",
        smogon_format="gen9championsvgc2026regmc",
        month="2026-09",
        cutoff=1760,
        points_kind=POINTS_STAT,
        note="Smogon 双打天梯；Champions 使用能力点（单项上限 32），无个体值系统。",
        trade_prefix=None,
        default_level=50,
    ),
)

FORMAT_KEYS: tuple[str, ...] = tuple(item.key for item in FORMATS)
FORMAT_BY_KEY: dict[str, DoublesFormat] = {item.key: item for item in FORMATS}

#: 抓取地址模板。
STATS_BASE_URL = "https://www.smogon.com/stats"


def usage_url(fmt: DoublesFormat) -> str:
    return f"{STATS_BASE_URL}/{fmt.month}/{fmt.smogon_format}-{fmt.cutoff}.txt"


def moveset_url(fmt: DoublesFormat) -> str:
    return f"{STATS_BASE_URL}/{fmt.month}/moveset/{fmt.smogon_format}-{fmt.cutoff}.txt"


def get_format(key: str) -> DoublesFormat | None:
    return FORMAT_BY_KEY.get(key)


def dataset_meta(fmt: DoublesFormat) -> dict:
    """写入 `data/doubles/{key}.json` 的格式元数据（含导出用的交易前缀）。"""
    return {
        "key": fmt.key,
        "label": fmt.label,
        "short_label": fmt.short_label,
        "game": fmt.game,
        "ruleset": fmt.ruleset,
        "smogon_format": fmt.smogon_format,
        "month": fmt.month,
        "cutoff": fmt.cutoff,
        "points_kind": fmt.points_kind,
        "note": fmt.note,
        "trade_prefix": fmt.trade_prefix,
        "default_level": fmt.default_level,
        "usage_url": usage_url(fmt),
        "moveset_url": moveset_url(fmt),
    }


def update_dataset_meta(paths: list[Path]) -> list[Path]:
    """把仓库内已抓取的数据文件的 `format` 元数据刷新成当前定义。

    只改元数据（顺序 / 交易前缀 / 默认等级等展示与导出参数），不动统计内容，
    因此不需要重新联网抓取。返回实际写入的文件。
    """
    written: list[Path] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = payload.get("format", {}).get("key") or path.stem
        fmt = FORMAT_BY_KEY.get(key)
        if fmt is None:
            continue
        payload["format"] = dataset_meta(fmt)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written
