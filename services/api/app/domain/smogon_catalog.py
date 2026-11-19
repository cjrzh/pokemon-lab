"""Smogon 历史使用率：格式目录与月份发现（纯数据 + 轻量网络）。

范围（已与项目负责人确认）：
  - **只抓双打 / VGC 相关格式**，跳过单打与各类 OMs；
  - 每个格式抓 **1500 / 1630 / 1760** 三档等级线（0 = 全分段不抓）；
  - 历史覆盖 Smogon 提供的全部月份（2014-11 起），首次同步全量、之后增量。

为什么维护一份显式目录而不是「抓目录页里所有含 doubles 的文件」：
Smogon 的格式名随世代演进（`vgc2015` → `gen7vgc2019ultraseries` → `gen9vgc2026regf`），
且部分格式会消失。显式目录 + 展示名，才能让页面上的「版本 / 规则」筛选稳定可读。
未知格式（目录里没有但服务器上出现）会在同步时记录到 run.message，提示人工补充。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

SMOGON_STATS_ROOT = "https://www.smogon.com/stats/"

#: 抓取的等级线（升序）。
CUTOFFS = (1500, 1630, 1760)

#: 请求头：Smogon 对普通 UA 友好；标明来源便于对方识别。
USER_AGENT = "pokemon-lab/0.1 (personal project; usage statistics sync)"


@dataclass(frozen=True)
class SmogonFormat:
    """目录里的一个双打 / VGC 格式。"""

    format_id: str
    game: str
    ruleset: str
    #: 展示名（中文优先）
    label: str
    #: 归类：vgc / doubles / other
    kind: str


def _f(format_id: str, game: str, ruleset: str, label: str, kind: str = "doubles") -> SmogonFormat:
    return SmogonFormat(format_id, game, ruleset, label, kind)


#: 目录：按世代倒序、同世代内 VGC 在前。
FORMAT_CATALOG: tuple[SmogonFormat, ...] = (
    _f(
        "gen9championsvgc2026regmc",
        "宝可梦冠军",
        "VGC 2026 Reg M-C",
        "冠军 VGC 2026 Reg M-C",
        "vgc",
    ),
    _f(
        "gen9championsvgc2026regmcbo3",
        "宝可梦冠军",
        "VGC 2026 Reg M-C Bo3",
        "冠军 VGC 2026 Reg M-C（Bo3）",
        "vgc",
    ),
    _f("gen9championsou", "宝可梦冠军", "OU", "冠军 OU"),
    _f("gen9championsuu", "宝可梦冠军", "UU", "冠军 UU"),
    _f("gen9championsbssregmc", "宝可梦冠军", "BSS Reg M-C", "冠军 BSS Reg M-C"),
    _f(
        "gen9championsmegaevolutionbattle",
        "宝可梦冠军",
        "Mega 进化战",
        "冠军 Mega 进化战",
    ),
    _f("gen9vgc2026regf", "朱紫", "VGC 2026 Reg F", "朱紫 VGC 2026 Reg F", "vgc"),
    _f(
        "gen9vgc2026regfbo3",
        "朱紫",
        "VGC 2026 Reg F Bo3",
        "朱紫 VGC 2026 Reg F（Bo3）",
        "vgc",
    ),
    _f("gen9vgc2025regj", "朱紫", "VGC 2025 Reg J", "朱紫 VGC 2025 Reg J", "vgc"),
    _f("gen9vgc2025regh", "朱紫", "VGC 2025 Reg H", "朱紫 VGC 2025 Reg H", "vgc"),
    _f(
        "gen9vgc2025reghbo3",
        "朱紫",
        "VGC 2025 Reg H Bo3",
        "朱紫 VGC 2025 Reg H（Bo3）",
        "vgc",
    ),
    _f("gen9vgc2025regg", "朱紫", "VGC 2025 Reg G", "朱紫 VGC 2025 Reg G", "vgc"),
    _f(
        "gen9vgc2025reggbo3",
        "朱紫",
        "VGC 2025 Reg G Bo3",
        "朱紫 VGC 2025 Reg G（Bo3）",
        "vgc",
    ),
    _f("gen9vgc2024regh", "朱紫", "VGC 2024 Reg H", "朱紫 VGC 2024 Reg H", "vgc"),
    _f(
        "gen9vgc2024reghbo3",
        "朱紫",
        "VGC 2024 Reg H Bo3",
        "朱紫 VGC 2024 Reg H（Bo3）",
        "vgc",
    ),
    _f("gen9vgc2024regg", "朱紫", "VGC 2024 Reg G", "朱紫 VGC 2024 Reg G", "vgc"),
    _f("gen9vgc2024regf", "朱紫", "VGC 2024 Reg F", "朱紫 VGC 2024 Reg F", "vgc"),
    _f(
        "gen9vgc2024regfbo3",
        "朱紫",
        "VGC 2024 Reg F Bo3",
        "朱紫 VGC 2024 Reg F（Bo3）",
        "vgc",
    ),
    _f("gen9vgc2023regulatione", "朱紫", "VGC 2023 Reg E", "朱紫 VGC 2023 Reg E", "vgc"),
    _f(
        "gen9vgc2023regulationebo3",
        "朱紫",
        "VGC 2023 Reg E Bo3",
        "朱紫 VGC 2023 Reg E（Bo3）",
        "vgc",
    ),
    _f("gen9vgc2023series1", "朱紫", "VGC 2023 Series 1", "朱紫 VGC 2023 Series 1", "vgc"),
    _f("gen9doublesou", "朱紫", "Doubles OU", "朱紫 双打 OU"),
    _f("gen9doublesubers", "朱紫", "Doubles Ubers", "朱紫 双打 Ubers"),
    _f("gen9doublesuu", "朱紫", "Doubles UU", "朱紫 双打 UU"),
    _f("gen9nationaldexdoubles", "朱紫", "National Dex Doubles", "朱紫 全国图鉴双打"),
    _f(
        "gen9nationaldexdoublesubers",
        "朱紫",
        "National Dex Doubles Ubers",
        "朱紫 全国图鉴双打 Ubers",
    ),
    _f("gen9battlestadiumdoubles", "朱紫", "对战塔双打", "朱紫 对战塔双打"),
    _f("gen9mixandmegadoubles", "朱紫", "Mix and Mega Doubles", "朱紫 Mix and Mega 双打"),
    _f("gen92v2doubles", "朱紫", "2v2 双打", "朱紫 2v2 双打"),
    _f("gen8vgc2022", "剑盾", "VGC 2022", "剑盾 VGC 2022", "vgc"),
    _f("gen8vgc2021series11", "剑盾", "VGC 2021 Series 11", "剑盾 VGC 2021 Series 11", "vgc"),
    _f("gen8vgc2021", "剑盾", "VGC 2021", "剑盾 VGC 2021", "vgc"),
    _f("gen8vgc2020", "剑盾", "VGC 2020", "剑盾 VGC 2020", "vgc"),
    _f("gen8doublesou", "剑盾", "Doubles OU", "剑盾 双打 OU"),
    _f("gen8doublesubers", "剑盾", "Doubles Ubers", "剑盾 双打 Ubers"),
    _f("gen8doublesuu", "剑盾", "Doubles UU", "剑盾 双打 UU"),
    _f("gen8bdspdoublesou", "BDSP", "Doubles OU", "BDSP 双打 OU"),
    _f("gen8bdspbattlefestivaldoubles", "BDSP", "对战庆典双打", "BDSP 对战庆典双打"),
    _f("gen8battlestadiumdoubles", "剑盾", "对战塔双打", "剑盾 对战塔双打"),
    _f("gen8aaadoubles", "剑盾", "Almost Any Ability Doubles", "剑盾 AAA 双打"),
    _f("gen82v2doubles", "剑盾", "2v2 双打", "剑盾 2v2 双打"),
    _f(
        "gen7vgc2019ultraseries",
        "究极日月",
        "VGC 2019 Ultra Series",
        "究极日月 VGC 2019 Ultra Series",
        "vgc",
    ),
    _f(
        "gen7vgc2019moonseries",
        "究极日月",
        "VGC 2019 Moon Series",
        "究极日月 VGC 2019 Moon Series",
        "vgc",
    ),
    _f(
        "gen7vgc2019sunseries",
        "究极日月",
        "VGC 2019 Sun Series",
        "究极日月 VGC 2019 Sun Series",
        "vgc",
    ),
    _f("gen7vgc2018", "究极日月", "VGC 2018", "究极日月 VGC 2018", "vgc"),
    _f("gen7vgc2017", "日月", "VGC 2017", "日月 VGC 2017", "vgc"),
    _f("gen7doublesou", "日月", "Doubles OU", "日月 双打 OU"),
    _f("gen7doublesubers", "日月", "Doubles Ubers", "日月 双打 Ubers"),
    _f("gen7doublesuu", "日月", "Doubles UU", "日月 双打 UU"),
    _f(
        "gen7pokebankdoublesubers",
        "日月",
        "PokéBank Doubles Ubers",
        "日月 PokéBank 双打 Ubers",
    ),
    _f("gen7battlespotdoubles", "日月", "对战树双打", "日月 对战树双打"),
    _f("gen7letsgodoublesou", "Let's Go", "Let's Go 双打 OU", "Let's Go 双打 OU"),
    _f(
        "gen7letsgodoublesnorestrictions",
        "Let's Go",
        "Let's Go 双打（无限制）",
        "Let's Go 双打（无限制）",
    ),
    _f("gen6vgc2014", "XY", "VGC 2014", "XY VGC 2014", "vgc"),
    _f("gen6doublesou", "XY", "Doubles OU", "XY 双打 OU"),
    _f("gen5doublesou", "黑2白2", "Doubles OU", "黑2白2 双打 OU"),
    _f("gen5gbudoubles", "黑2白2", "GBU 双打", "黑2白2 GBU 双打"),
    _f("gen4doublesou", "白金", "Doubles OU", "白金 双打 OU"),
    _f("gen3doublesou", "绿宝石", "Doubles OU", "绿宝石 双打 OU"),
    _f("gen2gscdoubles", "金心魂银", "GSC 双打", "金心魂银 GSC 双打"),
    _f("vgc2016", "ORAS", "VGC 2016", "ORAS VGC 2016", "vgc"),
    _f("vgc2015", "ORAS", "VGC 2015", "ORAS VGC 2015", "vgc"),
    _f("doublesou", "ORAS", "Doubles OU", "ORAS 双打 OU"),
    _f("doublesubers", "ORAS", "Doubles Ubers", "ORAS 双打 Ubers"),
    _f("doublesuu", "ORAS", "Doubles UU", "ORAS 双打 UU"),
    _f("2v2doubles", "ORAS", "2v2 双打", "ORAS 2v2 双打"),
)

FORMAT_BY_ID = {fmt.format_id: fmt for fmt in FORMAT_CATALOG}

#: 不抓的随机格式（无固定配置，无法与其他格式比较）。
EXCLUDED = {"randomdoublesbattle", "gen7randomdoublesbattle"}

_MONTH_RE = re.compile(r'href="(\d{4}-\d{2})/"')


class SmogonFetchError(RuntimeError):
    """网络或解析失败。"""


def make_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


def make_async_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """同步服务用：全异步客户端，避免在事件循环里开线程。"""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        # 服务器进程的环境可能带代理变量导致连接卡住；这里显式忽略，
        # 与 curl 的行为对齐（同一网络命名空间，直连可用）。
        trust_env=False,
    )


def discover_months(client: httpx.Client | None = None) -> list[str]:
    """列出 Smogon 提供统计的全部月份（升序）。"""
    own = client is None
    client = client or make_client()
    try:
        response = client.get(SMOGON_STATS_ROOT)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SmogonFetchError(f"无法访问 Smogon 统计目录：{exc}") from exc
    finally:
        if own:
            client.close()
    months = sorted(set(_MONTH_RE.findall(response.text)))
    if not months:
        raise SmogonFetchError("Smogon 目录页没有解析到任何月份")
    return months


def usage_url(format_id: str, month: str, cutoff: int) -> str:
    return f"{SMOGON_STATS_ROOT}{month}/{format_id}-{cutoff}.txt"


def fetch_usage_text(format_id: str, month: str, cutoff: int, client: httpx.Client) -> str | None:
    """抓一个使用率文件；404（该月/该格式不存在）返回 None。"""
    response = client.get(usage_url(format_id, month, cutoff))
    if response.status_code == 404:
        return None
    try:
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SmogonFetchError(f"{format_id} {month} {cutoff}：{exc}") from exc
    return response.text


async def discover_months_async(client: httpx.AsyncClient) -> list[str]:
    """`discover_months` 的异步版本（同步服务在事件循环里用）。"""
    try:
        response = await client.get(SMOGON_STATS_ROOT)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SmogonFetchError(f"无法访问 Smogon 统计目录：{exc}") from exc
    months = sorted(set(_MONTH_RE.findall(response.text)))
    if not months:
        raise SmogonFetchError("Smogon 目录页没有解析到任何月份")
    return months


async def fetch_usage_text_async(
    format_id: str, month: str, cutoff: int, client: httpx.AsyncClient
) -> str | None:
    """`fetch_usage_text` 的异步版本。"""
    response = await client.get(usage_url(format_id, month, cutoff))
    if response.status_code == 404:
        return None
    try:
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SmogonFetchError(f"{format_id} {month} {cutoff}：{exc}") from exc
    return response.text
