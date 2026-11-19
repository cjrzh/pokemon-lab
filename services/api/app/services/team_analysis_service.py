"""队伍评价：属性层面的计算 + LLM 解读。

分工（重要）：
  - **打击面 / 缺失面 / 共同弱点**由 `domain/team_analysis.py` 纯函数算出，
    有测试、可复现，不依赖任何外部服务；
  - **改进建议 / 玩法推荐**交给 LLM —— 这部分是把结构化结论翻译成可执行的建议，
    LLM 挂了也只是少了这两段，不影响上面的数字。

LLM 输出格式约定（见 `_SYSTEM_PROMPT`）：用固定的小标题分段，前端按行渲染。
不强制 JSON：模型偶尔会包一层 markdown 代码块，解析 JSON 反而更脆。
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import llm_client
from app.db.models import Team
from app.domain.showdown_export import render_member
from app.domain.team_analysis import TeamCoverage, analyze_team
from app.repositories import pokemon_repo
from app.services.type_chart_service import load_type_chart

logger = logging.getLogger(__name__)

#: 属性英文键 → 中文名（提示词与页面都读这份，避免两处各写一套）。
_TYPE_ZH = {
    "normal": "一般", "fire": "火", "water": "水", "electric": "电", "grass": "草",
    "ice": "冰", "fighting": "格斗", "poison": "毒", "ground": "地面", "flying": "飞行",
    "psychic": "超能力", "bug": "虫", "rock": "岩石", "ghost": "幽灵", "dragon": "龙",
    "dark": "恶", "steel": "钢", "fairy": "妖精",
}


def type_zh(key: str) -> str:
    return _TYPE_ZH.get(key, key)


_SYSTEM_PROMPT = """你是一位宝可梦 VGC 双打对战教练，擅长把队伍构成的分析翻译成简洁、可执行的建议。

规则：
- 只依据用户给出的队伍数据作答，不要编造看不到的招式 / 道具 / 种族值。
- 如果数据不足以支撑某个判断，直接说明「数据不足」，不要猜。
- 用中文回答，控制在 400 字以内。
- 严格按下面三个小标题输出，每个标题下用短句或列表，不要加额外的开场白：

## 队伍评价
（一句话概括这支队伍的定位与强度倾向）

## 改进建议
（针对缺失面与共同弱点，给出 2–4 条具体、可操作的调整）

## 玩法推荐
（这支队伍的作战节奏 / 先发思路 / 关键回合的取舍，2–3 条）"""


async def evaluate_team(
    session: AsyncSession,
    members: list[dict],
    *,
    use_llm: bool = True,
    format_key: str = "sv",
    default_level: int = 50,
) -> dict:
    """组装队伍评价（一次性返回，含 LLM 解读）。

    Args:
        members: `TeamMemberInput` 转成的 dict（至少含 dex_number / showdown_name）。
        use_llm: 为 False 时只做计算（前端可用来「先看数据再生成建议」）。
        format_key: 队伍所在版本，决定 Showdown 里是否输出太晶属性。
        default_level: 未显式设置等级时的默认值（提示词里要写全）。

    Returns:
        dict，字段见 `schemas/teams.py:TeamAnalysis`。
    """
    enriched, coverage, analysis = await _build_analysis(session, members)

    if not use_llm:
        return analysis

    prompt = _build_prompt(
        enriched, coverage, format_key=format_key, default_level=default_level
    )
    result = await llm_client.complete(_SYSTEM_PROMPT, prompt)
    if result.ok:
        analysis["llm"] = {"text": result.text, "model": result.model}
    else:
        analysis["llm_error"] = result.error

    return analysis


async def stream_team_analysis(
    session: AsyncSession,
    members: list[dict],
    *,
    use_llm: bool = True,
    format_key: str = "sv",
    default_level: int = 50,
) -> AsyncIterator[dict]:
    """流式组装：先给计算结果，再逐段 yield LLM 增量。

    yield 的事件（dict，`event` 字段区分）：
      - `coverage`：开始就有，含打击面 / 缺失面 / 共同弱点（与一次性接口同结构）；
      - `delta`：LLM 的正文增量（`text`）；`reasoning=True` 表示这是思维链、不必展示；
      - `done`：正文收尾（`text` 是完整正文，便于调用方落库）；
      - `error`：LLM 不可用，`text` 是原因（计算结果已在前面的 coverage 里给出）。
    """
    enriched, coverage, analysis = await _build_analysis(session, members)
    yield {"event": "coverage", "data": analysis}

    if not use_llm:
        yield {"event": "done", "text": "", "model": None}
        return

    parts: list[str] = []
    model: str | None = None
    failed = False
    prompt = _build_prompt(
        enriched, coverage, format_key=format_key, default_level=default_level
    )
    async for chunk in llm_client.stream(_SYSTEM_PROMPT, prompt):
        if chunk.kind == "error":
            failed = True
            yield {"event": "error", "text": chunk.text}
            break
        model = chunk.model or model
        if chunk.kind == "content":
            parts.append(chunk.text)
            yield {"event": "delta", "text": chunk.text, "model": model}

    if not failed:
        yield {"event": "done", "text": "".join(parts), "model": model}


async def _build_analysis(
    session: AsyncSession, members: list[dict]
) -> tuple[list[dict], TeamCoverage, dict]:
    """计算部分：补属性 → 打击面 / 缺失面 / 共同弱点。

    返回 (enriched, coverage, analysis)。enriched 还要给 LLM 提示词用；
    coverage 供 `_build_prompt` 生成结构化结论。抽出来是为了让一次性与流式
    两条路径共用同一套计算，不会算出两份不同的结论。
    """
    chart = load_type_chart()
    dex_numbers = [member["dex_number"] for member in members if member.get("dex_number")]
    briefs = await pokemon_repo.get_pokemon_briefs(session, dex_numbers)

    # 补上属性：客户端传来的配置未必带 types，以库里的为准
    enriched: list[dict] = []
    for member in members:
        brief = briefs.get(member.get("dex_number"))
        types = []
        if brief is not None:
            try:
                types = json.loads(brief[2] or "[]")
            except (json.JSONDecodeError, TypeError):
                types = []
        enriched.append(
            {
                "dex_number": member.get("dex_number"),
                "name": (brief[0] if brief else None) or member.get("showdown_name") or "",
                "types": types,
                "member": member,
            }
        )

    coverage = analyze_team(enriched, chart.chart)

    analysis = {
        "members": [
            {
                "dex_number": item["dex_number"],
                "name": item["name"],
                "types": item["types"],
            }
            for item in enriched
        ],
        "attack": [
            {
                "type": entry.type,
                "type_zh": type_zh(entry.type),
                "hits": entry.hits,
                "hits_zh": [type_zh(hit) for hit in entry.hits],
                "member_count": entry.member_count,
            }
            for entry in coverage.attack
        ],
        "gaps": coverage.gaps,
        "gaps_zh": [type_zh(gap) for gap in coverage.gaps],
        "hotspots": [
            {
                "type": hotspot.type,
                "type_zh": type_zh(hotspot.type),
                "members": hotspot.members,
            }
            for hotspot in coverage.hotspots
        ],
        "llm": None,
        "llm_error": None,
    }
    return enriched, coverage, analysis


def _build_prompt(
    enriched: list[dict],
    coverage: TeamCoverage,
    *,
    format_key: str = "sv",
    default_level: int = 50,
) -> str:
    """把整队配置与结构化分析写成提示词。只在 LLM 这一段用到中文。

    队伍本身用 **Showdown 代码**原样给出：道具、特性、性格、EV、IV、等级、
    太晶属性、招式全在里面，比手写摘要更完整，也不会漏字段。模型对 Showdown
    格式很熟悉，附上中文名 / 属性只是帮助它把结论落回界面用语。
    """
    lines = [
        "这是一支宝可梦 VGC 双打队伍。下面是完整的 Showdown 配置（含道具、特性、"
        "性格、EV/IV、等级与招式）：",
        "",
        "```",
    ]
    for item in enriched:
        config = item["member"]
        lines.append(
            render_member(config, format_key=format_key, default_level=default_level).rstrip()
        )
        lines.append("")
    lines.append("```")
    lines.append("")

    # 中文名 + 属性：模型据此把「Fire」这类英文写成界面上的「火」，也便于指出具体是谁
    lines.append("队伍成员（中文名 · 属性）：")
    for item in enriched:
        types = "、".join(type_zh(t) for t in item["types"]) or "未知"
        name = item["name"] or item["member"].get("showdown_name") or "未知"
        lines.append(f"- {name}（{types}）")

    covering = "、".join(
        f"{type_zh(entry.type)}（可克制 {len(entry.hits)} 种属性）"
        for entry in coverage.attack[:8]
    )
    gaps_text = "、".join(type_zh(gap) for gap in coverage.gaps) or "无"
    hotspots_text = (
        "、".join(f"{type_zh(h.type)}（{len(h.members)} 只）" for h in coverage.hotspots)
        or "无"
    )
    lines += [
        "",
        "按属性推算的结果（由程序计算，可直接引用）：",
        f"- 打击面：{covering or '无'}",
        f"- 缺失面（没有任何队员能 2 倍克制）：{gaps_text}",
        f"- 共同弱点（2 只以上队员同时被 2 倍克制）：{hotspots_text}",
        "",
        "请结合上面的完整配置（不只是属性）给出评价、改进建议与玩法推荐；"
        "引用招式 / 道具 / 特性时使用配置里的原文。",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 评价落库：存快照 + 成员指纹，读取时判断是否还对新配置
# ---------------------------------------------------------------------------


def members_fingerprint(members: list[dict]) -> str:
    """一组成员的稳定指纹，用于判断已存评价是否还对应当前配置。

    只取影响评价结论的字段（编号 / 招式 / 特性 / 道具 / 太晶），昵称、语言、
    等级这类与打击面无关的改动不该把评价标记为过期。列表按编号排序后再哈希，
    这样仅调整槽位顺序也不会误判为「已改动」。JSON 的 `sort_keys` 保证字段顺序无关。
    """
    normalized = sorted(
        (
            {
                "dex": member.get("dex_number"),
                "moves": sorted(m for m in (member.get("moves") or []) if m),
                "ability": member.get("ability"),
                "item": member.get("item"),
                "tera": member.get("tera_type"),
            }
            for member in members
        ),
        key=lambda item: (item["dex"] is None, item["dex"]),
    )
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def save_analysis(
    session: AsyncSession, team: Team, analysis: dict, members: list[dict]
) -> Team:
    """把评价快照写到队伍上，并记录生成时间与成员指纹。

    `members` 是原始成员配置（含招式 / 特性 / 道具），指纹取自它 ——
    评价结果里的 `members` 只有编号与属性，判断不出配置是否改过。
    传空成员时清空旧评价：空队伍的评价没有意义，留着只会误导。
    """
    if not members:
        team.analysis_json = None
        team.analysis_at = None
        team.analysis_members_hash = None
    else:
        team.analysis_json = json.dumps(analysis, ensure_ascii=False)
        team.analysis_at = datetime.now(UTC)
        team.analysis_members_hash = members_fingerprint(members)
    await session.flush()
    await session.refresh(team)
    return team


def stored_analysis(team: Team, members: list[dict]) -> dict | None:
    """把队伍上存的评价解析成响应结构；没有或解析失败时返回 None。"""
    if not team.analysis_json:
        return None
    try:
        analysis = json.loads(team.analysis_json)
    except (json.JSONDecodeError, TypeError):
        logger.warning("队伍 #%s 的评价快照无法解析，已忽略", team.id)
        return None
    if not isinstance(analysis, dict):
        return None

    fingerprint = members_fingerprint(members)
    return {
        "analysis": analysis,
        "generated_at": team.analysis_at.isoformat() if team.analysis_at else None,
        "stale": team.analysis_members_hash != fingerprint,
    }
