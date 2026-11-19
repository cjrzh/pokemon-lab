"""形态（forms）数据的同步与读取。

背景：PokéAPI 的 `pokemon-species/{dex}` 用 `varieties` 描述同一图鉴编号下的
多个样子（默认形态 + 其它形态）。默认形态的数据在 `pokemon` 表；这里把**机制上
不同**的其它形态写入 `pokemon_form` 表：

  - 属性 / 种族值 / 特性 / 体重任一不同 → 收录（例如连击流武道熊师、清洗洛托姆）；
  - 只改外形（性别、只差身高、剑盾的极巨化、仅模型不同的"启动"形态）→ 不收录。

为什么不做成 `pokemon` 表的第二条记录：图鉴编号是 1–1025 的一对一主键，
详情页、搜索、双打映射都依赖它。形态是"同一只宝可梦的另一个样子"，
单独一张表更贴近事实，也避免图鉴列表出现重复编号。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Pokemon, PokemonForm, PokemonFormMove
from app.services.ability_service import sync_abilities

logger = logging.getLogger(__name__)

POKEAPI_POKEMON_URL = "https://pokeapi.co/api/v2/pokemon/{name}"
POKEAPI_FORM_URL = "https://pokeapi.co/api/v2/pokemon-form/{id}"

FORMS_LABELS_FILE = Path("forms") / "zh-hans.json"
#: 本地形态名 → Showdown 显示名（由 scripts/gen_form_showdown.py 生成）。
FORMS_SHOWDOWN_FILE = Path("forms") / "showdown.json"

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_CONCURRENCY = 8

#: 不收录的形态后缀：只改外观 / 极巨化 / 图腾 / 仅性别差异已由默认形态覆盖。
#: 用整段匹配，避免 `low-key` 被 `gmax` 误伤。
SKIP_SUFFIXES = {
    "gmax",
    "totem",
    "totem-alola",
    "totem-disguised",
    "totem-busted",
}

def _is_cosmetic_suffix(suffix: str) -> bool:
    """只改外观的形态后缀：超极巨化、霸主等（`rapid-strike-gmax` 也算）。"""
    return suffix in SKIP_SUFFIXES or suffix.endswith("-gmax") or suffix.startswith("totem-")


#: 决定形态是否"机制上不同"的字段。
_COMPARED_STATS = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")


@dataclass
class FormSyncResult:
    """一次形态同步的结果。"""

    species: int = 0
    forms: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    artwork: int = 0
    sprites: int = 0
    #: 写入的 形态 × 版本组 招式表条数
    move_groups: int = 0

    def summary(self) -> str:
        return (
            f"形态同步：{self.species} 个物种 / 写入 {len(self.forms)} 个形态，"
            f"跳过 {len(self.skipped)}，失败 {len(self.failed)}；"
            f"招式表 {self.move_groups} 组；立绘 {self.artwork}，小图标 {self.sprites}"
        )


# ---------------------------------------------------------------------------
# 标签
# ---------------------------------------------------------------------------


def load_form_labels() -> dict:
    """读取 `data/forms/zh-hans.json`（同步脚本与接口共用）。"""
    path = get_settings().data_dir / FORMS_LABELS_FILE
    if not path.exists():
        logger.warning("形态标签文件不存在：%s", path)
        return {"suffixes": {}, "forms": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("形态标签文件损坏（%s）：%s", path, exc)
        return {"suffixes": {}, "forms": {}}
    payload.setdefault("suffixes", {})
    payload.setdefault("forms", {})
    return payload


@lru_cache(maxsize=1)
def load_form_showdown_map() -> dict[str, str]:
    """本地形态名 → Showdown 显示名。

    建队与导出需要 Showdown 口径的名称（`Rotom-Wash` / `Ogerpon-Wellspring`），
    而本地图鉴用 PokéAPI 的 slug（`rotom-wash` / `ogerpon-wellspring-mask`）。
    映射由 `scripts/gen_form_showdown.py` 生成；文件缺失时返回空字典，
    调用方回落到「形态 slug 的展示写法」，不会阻断建队。
    """
    path = get_settings().data_dir / FORMS_SHOWDOWN_FILE
    if not path.exists():
        logger.warning("形态 → Showdown 映射文件不存在：%s", path)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("形态 → Showdown 映射文件损坏（%s）：%s", path, exc)
        return {}
    forms = payload.get("forms") or {}
    return {str(key): str(value) for key, value in forms.items()}


def showdown_name_for(form_name: str) -> str | None:
    """本地形态名 → Showdown 显示名；未收录时返回 None（调用方回落到展示名）。"""
    return load_form_showdown_map().get(form_name)


@lru_cache(maxsize=1)
def _reverse_showdown_map() -> dict[str, list[str]]:
    """Showdown 显示名（归一化）→ 本地形态名（可能多个，如 Minior 的颜色）。"""
    reverse: dict[str, list[str]] = {}
    for form_name, showdown_name in load_form_showdown_map().items():
        reverse.setdefault(showdown_name.lower(), []).append(form_name)
    return reverse


def form_for_showdown_name(showdown_name: str | None) -> str | None:
    """按 Showdown 显示名反查本地形态 slug（**仅限非默认形态**）。

    注意：映射文件里也包含默认形态（`garchomp` → `Garchomp`）。默认形态不能作为
    `team-options?form=` 的参数返回 —— 前端会把它当成可选形态去请求，而后端只认
    `pokemon_form` 里的非默认形态，于是 422。调用方应优先使用
    `pokemon_repo.get_form_showdown_names`（以数据库为准，天然排除默认形态）。
    """
    if not showdown_name:
        return None
    candidates = _reverse_showdown_map().get(showdown_name.strip().lower()) or []
    return candidates[0] if candidates else None


def reset_form_showdown_cache() -> None:
    """测试用：清空映射缓存。"""
    load_form_showdown_map.cache_clear()
    _reverse_showdown_map.cache_clear()
    load_gigantamax_map.cache_clear()


# ---------------------------------------------------------------------------
# 超极巨化（Gigantamax）
# ---------------------------------------------------------------------------

#: 能超极巨化的物种 / 形态 → `{showdown_name, gmax_name, gmax_move}`。
#: 键是 **Showdown 名**的 slug（`charizard` / `toxtricity-low-key` / `urshifu`），
#: 不是本地形态名 —— 本地默认名常带形态后缀（`urshifu-single-strike`），
#: 与 Showdown 的 `Urshifu` 对不上。与形态映射同源：
#: `scripts/gen_form_showdown.py` 从 Showdown `pokedex.json` 的 `canGigantamax` 生成，
#: 运行时读取同一份 `data/forms/showdown.json`。


@lru_cache(maxsize=1)
def load_gigantamax_map() -> dict[str, dict]:
    """能超极巨化的宝可梦清单；文件缺失时为空（界面不显示开关，不阻断建队）。"""
    path = get_settings().data_dir / FORMS_SHOWDOWN_FILE
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("超极巨化清单读取失败（%s）：%s", path, exc)
        return {}
    entries = payload.get("gigantamax") or {}
    return {
        str(key): dict(value)
        for key, value in entries.items()
        if isinstance(value, dict) and value.get("gmax_name")
    }


def _gmax_key(showdown_name: str) -> str:
    from app.domain.smogon_stats import showdown_slug

    key = showdown_slug(showdown_name)
    # 误传了 G 形态名（`Charizard-Gmax`）时也能命中基础条目
    return key[: -len("-gmax")] if key.endswith("-gmax") else key


def gigantamax_info(showdown_name: str | None) -> dict | None:
    """Showdown 显示名 → 超极巨化信息；没有 G 形态时返回 None。"""
    if not showdown_name:
        return None
    return load_gigantamax_map().get(_gmax_key(showdown_name))


def can_gigantamax(showdown_name: str | None) -> bool:
    """该物种 / 形态是否有超极巨化形态。"""
    return gigantamax_info(showdown_name) is not None


def form_label(forms_document: dict, name: str, suffix: str) -> str | None:
    """形态中文名：具体形态优先，其次通用后缀；都没有返回 None（不猜译）。

    后缀可能带复合形式（`galar-zen` → 先查 `galar-zen`，再逆序拆分查 `zen`）。
    """
    specific = forms_document.get("forms", {}).get(name)
    if specific:
        return specific
    suffixes = forms_document.get("suffixes", {})
    if suffix in suffixes:
        return suffixes[suffix]
    parts = suffix.split("-")
    for start in range(1, len(parts)):
        candidate = "-".join(parts[start:])
        if candidate in suffixes:
            return suffixes[candidate]
    return None


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------


def parse_variety(payload: dict, *, base_name: str, position: int) -> dict:
    """把 PokéAPI `/pokemon/{variant}` 解析成 `pokemon_form` 的字段。

    `suffix` 取 PokéAPI 的 `forms[0].form_name`（最准确，如 `mega-x`）；
    缺失时退回「完整名去掉物种名」。
    """
    name = str(payload.get("name") or "")
    form_name = ""
    forms = payload.get("forms") or []
    if forms and isinstance(forms[0], dict):
        form_name = str(forms[0].get("form_name") or "")
    if not form_name:
        form_name = name[len(base_name) :].lstrip("-") if name.startswith(base_name) else name

    abilities = []
    for entry in payload.get("abilities") or []:
        ability = entry.get("ability") or {}
        abilities.append(
            {
                "name": ability.get("name"),
                "is_hidden": bool(entry.get("is_hidden", False)),
                # 中文名 / 说明由 ability 参考表补齐（与默认形态共用）
                "zh": None,
                "effect_zh": None,
                "effect_en": None,
            }
        )
    stats = {
        (entry.get("stat") or {}).get("name"): int(entry.get("base_stat") or 0)
        for entry in payload.get("stats") or []
        if (entry.get("stat") or {}).get("name") in _COMPARED_STATS
    }
    sprites = payload.get("sprites") or {}
    artwork = (sprites.get("other") or {}).get("official-artwork") or {}

    return {
        "name": name,
        "suffix": form_name,
        "position": position,
        "types_json": json.dumps(
            [slot["type"]["name"] for slot in payload.get("types") or []], ensure_ascii=False
        ),
        "stats_json": json.dumps(stats, ensure_ascii=False),
        "abilities_json": json.dumps(abilities, ensure_ascii=False),
        "height_dm": payload.get("height"),
        "weight_hg": payload.get("weight"),
        "artwork_url": artwork.get("front_default"),
        "sprite_url": sprites.get("front_default"),
        "name_en_label": None,
    }


def extract_variety_moves(payload: dict) -> dict[str, dict[str, list[dict]]]:
    """形态 `/pokemon/{name}` 的招式 → {版本组: {学习方式: [{name, level}, …]}}。

    与默认形态的 `pokemon_parser.extract_all_moves` 同一口径，便于校验时合并。
    只保留有 move_learn_method / version_group 的条目，去掉重复。
    """
    buckets: dict[str, dict[str, list[dict]]] = {}
    for entry in payload.get("moves") or []:
        move_name = (entry.get("move") or {}).get("name")
        if not move_name:
            continue
        for detail in entry.get("version_group_details") or []:
            method = (detail.get("move_learn_method") or {}).get("name")
            group = (detail.get("version_group") or {}).get("name")
            if not method or not group:
                continue
            level = int(detail.get("level_learned_at") or 0)
            buckets.setdefault(group, {}).setdefault(method, []).append(
                {"name": move_name, "level": level}
            )
    for methods in buckets.values():
        for method, moves in methods.items():
            deduped = {(m["name"], m["level"]): m for m in moves}.values()
            if method == "level-up":
                methods[method] = sorted(deduped, key=lambda m: (m["level"], m["name"]))
            else:
                methods[method] = sorted(deduped, key=lambda m: m["name"])
    return buckets


async def upsert_form_moves(
    session: AsyncSession,
    *,
    form_name: str,
    dex_number: int,
    groups: dict[str, dict[str, list[dict]]],
) -> int:
    """把形态的招式表（按版本组）写入 `pokemon_form_move`（幂等，整体替换）。"""
    await session.execute(
        delete(PokemonFormMove).where(PokemonFormMove.form_name == form_name)
    )
    for version_group, methods in groups.items():
        session.add(
            PokemonFormMove(
                form_name=form_name,
                dex_number=dex_number,
                version_group=version_group,
                methods_json=json.dumps(methods, ensure_ascii=False),
            )
        )
    await session.flush()
    return len(groups)


def differs_from_base(variety: dict, base: Pokemon) -> bool:
    """形态是否与默认形态在机制上不同（属性 / 种族值 / 特性 / 身高体重）。"""
    try:
        base_types = json.loads(base.types_json or "[]")
        base_stats = json.loads(base.stats_json or "{}")
        base_abilities = json.loads(base.abilities_json or "[]")
    except (json.JSONDecodeError, TypeError):
        return True  # 本地数据异常时不擅自跳过

    base_keys = sorted(
        (a.get("name"), bool(a.get("is_hidden"))) for a in base_abilities if isinstance(a, dict)
    )
    variety_abilities = json.loads(variety["abilities_json"])
    variety_keys = sorted(
        (a.get("name"), bool(a.get("is_hidden"))) for a in variety_abilities if isinstance(a, dict)
    )

    if json.loads(variety["types_json"]) != base_types:
        return True
    variety_stats = json.loads(variety["stats_json"])
    base_stats_subset = {key: base_stats.get(key) for key in _COMPARED_STATS}
    if {key: variety_stats.get(key) for key in _COMPARED_STATS} != base_stats_subset:
        return True
    if variety_keys != base_keys:
        return True
    # 体重会影响「重磅冲撞 / 踢倒」等招式的伤害，算机制差异；
    # 身高只影响图鉴展示，不算（否则故勒顿/密勒顿的骑乘姿态会被当成形态）。
    return variety.get("weight_hg") != base.weight_hg


# ---------------------------------------------------------------------------
# 同步
# ---------------------------------------------------------------------------


async def _fetch(client: httpx.AsyncClient, url: str) -> dict | None:
    response = await client.get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def sync_forms(
    session: AsyncSession,
    dex_numbers: list[int] | None = None,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    progress=None,
    include_forms: bool = False,
) -> FormSyncResult:
    """同步形态数据（幂等）：只处理「默认形态之外、机制上不同」的形态。

    两阶段执行，避免串行请求把全量同步拖到十分钟以上：
      1. 并发拉取全部物种的 `pokemon-species/{dex}`，收集非默认 varieties；
      2. 并发拉取这些 variety 的 `/pokemon/{name}` 与 `pokemon-form/{id}`，
         与默认形态比较后批量写库。

    只有机制上不同的形态才写入 `pokemon_form` 图鉴表；**所有**非纯外观形态的
    招式表都会写入 `pokemon_form_move`（队伍校验按编号合并）—— 像 mega 形态
    种族值 / 特性与默认形态不同、但图鉴条目已有，校验时仍需要它的招式数据。

    `include_forms=True` 时跳过「与默认形态相同」的判定，把全部非纯外观形态都
    写进图鉴表（用于补齐早期同步遗漏的形态数据）。
    """
    result = FormSyncResult()
    settings = get_settings()
    document = load_form_labels()

    stmt = select(Pokemon).order_by(Pokemon.dex_number.asc())
    if dex_numbers:
        stmt = stmt.where(Pokemon.dex_number.in_(set(dex_numbers)))
    bases = {row.dex_number: row for row in (await session.execute(stmt)).scalars().all()}
    if not bases:
        return result

    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
        follow_redirects=True,
        limits=httpx.Limits(max_connections=concurrency * 2),
    ) as client:

        async def fetch(url: str) -> dict | None:
            async with semaphore:
                return await _fetch(client, url)

        # ---------- 阶段 1：并发取 species，整理待抓取的 varieties ----------
        species_rows = await asyncio.gather(
            *(fetch(f"https://pokeapi.co/api/v2/pokemon-species/{dex}") for dex in bases)
        )

        wanted: list[tuple[int, Pokemon, str, str, int]] = []
        for dex_number, species in zip(bases, species_rows, strict=True):
            result.species += 1
            if not species:
                continue
            varieties = [v for v in species.get("varieties") or [] if not v.get("is_default")]
            if not varieties:
                continue
            base = bases[dex_number]
            base_name = str(species.get("name") or base.name_en)
            for position, entry in enumerate(varieties, start=1):
                name = ((entry.get("pokemon") or {}).get("name")) or ""
                if not name:
                    continue
                suffix_hint = (
                    name[len(base_name) :].lstrip("-") if name.startswith(base_name) else name
                )
                if _is_cosmetic_suffix(suffix_hint):
                    result.skipped.append(name)
                    continue
                wanted.append((dex_number, base, base_name, name, position))

        if progress is not None:
            progress("species", result.species, len(wanted))

        # ---------- 阶段 2：并发取 variety + form 名称 ----------
        async def load_variety(
            dex_number: int, base: Pokemon, base_name: str, name: str, position: int
        ) -> tuple[int, Pokemon, dict | None, dict | None]:
            payload = await fetch(POKEAPI_POKEMON_URL.format(name=name))
            if payload is None:
                return dex_number, base, None, None
            variety = parse_variety(payload, base_name=base_name, position=position)
            forms = payload.get("forms") or []
            if forms and isinstance(forms[0], dict) and forms[0].get("url"):
                form_id = forms[0]["url"].rstrip("/").split("/")[-1]
                form_payload = await fetch(POKEAPI_FORM_URL.format(id=form_id))
                if form_payload:
                    for entry in form_payload.get("names") or []:
                        if (entry.get("language") or {}).get("name") == "en":
                            variety["name_en_label"] = entry.get("name")
                            break
            return dex_number, base, variety, payload

        loaded = await asyncio.gather(
            *(
                load_variety(dex_number, base, base_name, name, position)
                for dex_number, base, base_name, name, position in wanted
            )
        )

        for dex_number, base, variety, payload in loaded:
            if variety is None or payload is None:
                continue
            if _is_cosmetic_suffix(variety["suffix"]) or not differs_from_base(variety, base):
                result.skipped.append(variety["name"])
                continue
            variety["dex_number"] = dex_number
            variety["zh"] = form_label(document, variety["name"], variety["suffix"])
            # 与默认形态机制相同的形态（如蕾冠王骑乘形态只差招式）仍然是
            # 「可用的形态」，其专属招式 / 特性必须入校验上下文；这里分开记录，
            # 不改变「哪些形态进图鉴」的既有判定。
            await upsert_form(session, variety)
            # 形态专属招式（如连击流的「水流连打」）只出现在形态的 /pokemon 响应里，
            # 队伍校验按编号合并；这里一并落库，避免「合法配置被判非法」。
            result.move_groups += await upsert_form_moves(
                session,
                form_name=variety["name"],
                dex_number=dex_number,
                groups=extract_variety_moves(payload),
            )
            result.forms.append(variety["name"])

        await session.flush()

    # 形态可能带来新的特性（如阿罗拉形态的独有特性），刷新参考表
    await sync_abilities(session)
    await session.flush()

    # 立绘 / 小图标：并发下载，失败只 warning
    image_targets: list[tuple[PokemonForm, str, str, Path]] = []
    for name in result.forms:
        form = await session.get(PokemonForm, name)
        if form is None:
            continue
        if form.artwork_path is None and form.artwork_url:
            image_targets.append(
                (
                    form,
                    form.artwork_url,
                    "artwork",
                    settings.resolved_media_dir / "forms" / "artwork" / f"{name}.png",
                )
            )
        if form.sprite_path is None and form.sprite_url:
            image_targets.append(
                (
                    form,
                    form.sprite_url,
                    "sprites",
                    settings.resolved_media_dir / "forms" / "sprites" / f"{name}.png",
                )
            )

    image_semaphore = asyncio.Semaphore(concurrency)

    async def download(form: PokemonForm, url: str, kind: str, target: Path) -> None:
        async with image_semaphore:
            relative = f"forms/{kind}/{form.name}.png"
            path = await _cache_image(url, target, relative)
        if path is None:
            return
        if kind == "artwork":
            form.artwork_path = path
            result.artwork += 1
        else:
            form.sprite_path = path
            result.sprites += 1

    await asyncio.gather(
        *(download(form, url, kind, target) for form, url, kind, target in image_targets)
    )
    await session.flush()

    return result


def _proxy_image_url(url: str) -> str:
    """raw.githubusercontent 在部分网络不可直连，统一走 wsrv 图片代理。"""
    if "raw.githubusercontent.com" in url and "wsrv.nl" not in url:
        return f"https://wsrv.nl/?url={url.removeprefix('https://')}"
    return url


async def _cache_image(url: str, target: Path, relative: str) -> str | None:
    """下载形态图片到本地（已存在则复用）；失败只 warning。"""
    if target.exists() and target.stat().st_size > 0:
        return relative
    url = _proxy_image_url(url)
    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={"User-Agent": "pokemon-lab/0.1 (personal learning project)"},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
        if not content:
            raise httpx.HTTPError("空响应")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".png.part")
        tmp.write_bytes(content)
        tmp.replace(target)
        return relative
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("形态图片下载失败（%s）：%s", url, exc)
        return None


async def upsert_form(session: AsyncSession, record: dict) -> PokemonForm:
    """按形态 slug 写入 / 更新（幂等）。"""
    form = await session.get(PokemonForm, record["name"])
    if form is None:
        form = PokemonForm(name=record["name"])
        session.add(form)
    for key, value in record.items():
        setattr(form, key, value)
    await session.flush()
    return form


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------


async def list_forms_for_dex(session: AsyncSession, dex_number: int) -> list[PokemonForm]:
    stmt = (
        select(PokemonForm)
        .where(PokemonForm.dex_number == dex_number)
        .order_by(PokemonForm.position.asc(), PokemonForm.name.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_form(session: AsyncSession, name: str) -> PokemonForm | None:
    return await session.get(PokemonForm, name)


def form_media_url(path: str | None, remote: str | None) -> str | None:
    """形态图片地址：本地缓存优先（`/media/...`），缺失时回落远程。"""
    if path:
        return f"/media/{path}"
    return remote


def form_summary(form: PokemonForm, *, label: str) -> dict:
    """形态切换菜单项。"""
    return {
        "name": form.name,
        "label": label,
        "zh": form.zh,
        "name_en": form.name_en_label,
        "types": json.loads(form.types_json or "[]"),
        "is_default": False,
        "sprite_url": form_media_url(form.sprite_path, form.sprite_url),
    }


def default_form_summary(pokemon: Pokemon) -> dict:
    """默认形态在菜单里的表示（数据来自 `pokemon` 表）。"""
    return {
        "name": pokemon.name_en,
        "label": pokemon.name_zh or pokemon.name_en,
        "zh": None,
        "name_en": None,
        "types": json.loads(pokemon.types_json or "[]"),
        "is_default": True,
        "sprite_url": None,  # 调用方用 sprite_media_url 补齐
    }


async def list_forms_with_showdown(
    session: AsyncSession, dex_number: int
) -> list[dict]:
    """建队用的形态清单：本地形态 + Showdown 名 + 属性 / 图标。

    只返回**机制上不同、已收录**的形态（`pokemon_form`）；默认形态不在列表里，
    由调用方单独表示（`form=None`）。
    """
    forms = await list_forms_for_dex(session, dex_number)
    mapping = load_form_showdown_map()
    result = []
    for form in forms:
        result.append(
            {
                "form": form.name,
                "label": form.zh or form.name_en_label or form.name,
                "suffix": form.suffix,
                "types": json.loads(form.types_json or "[]"),
                "sprite_url": form_media_url(form.sprite_path, form.sprite_url),
                "showdown_name": mapping.get(form.name),
            }
        )
    return result
