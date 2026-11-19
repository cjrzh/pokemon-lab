"""双打建队路由。

`GET /teams`：队伍列表 + 可建队的格式（个人自用，不做浏览器隔离）。
`POST /teams` / `PUT /teams/{id}` / `DELETE /teams/{id}`：增改删；写入前后都做整队校验。
`GET /teams/{id}/showdown`：整队 Showdown 代码（含交易前缀）。
`GET /pokemon/{dex}/team-options`：某只宝可梦在某格式下的建队选项
（合法招式 / 特性 + 按使用率的推荐配置）。

合法性规则见 `domain/team_rules.py`；本层只做参数校验、取数编排与响应组装。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession
from app.db.engine import session_scope
from app.domain import showdown_export
from app.domain.doubles_formats import FORMAT_BY_KEY, FORMAT_KEYS
from app.domain.smogon_stats import showdown_slug
from app.domain.team_rules import FORMAT_VERSION_GROUP, TEAM_SIZE, validate_team
from app.repositories import pokemon_repo
from app.schemas.teams import (
    TeamAnalysis,
    TeamAnalyzeRequest,
    TeamBatchRequest,
    TeamBatchResponse,
    TeamCreate,
    TeamDetail,
    TeamFormOption,
    TeamImportRequest,
    TeamImportResponse,
    TeamListResponse,
    TeamMemberInput,
    TeamMemberOptions,
    TeamMemberView,
    TeamOptionUsage,
    TeamReorderRequest,
    TeamSummary,
    TeamUpdate,
    TeamValidationResult,
    ValidationIssue,
)
from app.services import (
    doubles_service,
    form_service,
    team_analysis_service,
    team_service,
)

router = APIRouter(tags=["teams"])

#: 明确选择「默认形态」时前端传的伪 slug（与图鉴详情页 URL 同一约定）。
DEFAULT_FORM = "default"


def _validate_format(format_key: str) -> None:
    if format_key not in FORMAT_BY_KEY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"format_key 只接受 {FORMAT_KEYS}",
        )


def _summary(team, *, member_count: int) -> TeamSummary:
    fmt = FORMAT_BY_KEY.get(team.format_key)
    return TeamSummary(
        id=team.id,
        name=team.name,
        format_key=team.format_key,
        format_label=fmt.label if fmt else None,
        note=team.note,
        member_count=member_count,
        updated_at=team.updated_at.isoformat() if team.updated_at else None,
        has_analysis=bool(team.analysis_json),
    )


async def _detail(session, team) -> TeamDetail:
    members = await team_service.get_members(session, team.id)
    meta = team_service.format_meta(team.format_key)
    base = _summary(team, member_count=len(members))
    member_payloads = [team_service.member_payload(member) for member in members]
    # 已保存队伍只存 Showdown 名；反查回本地形态以便编辑器定位选择器。
    # 只认 `pokemon_form` 里的非默认形态：默认形态（`Garchomp`）不能作为
    # `form=` 参数回传，否则前端请求 `?form=garchomp` 会 422。
    form_names = await pokemon_repo.get_form_showdown_names(
        session, [member.dex_number for member in members]
    )
    base_names = await pokemon_repo.get_base_names(
        session, [member.dex_number for member in members]
    )
    return TeamDetail(
        **base.model_dump(),
        members=[
            TeamMemberView(
                **payload,
                form=_resolve_member_form(payload, form_names, base_names),
            )
            for payload in member_payloads
        ],
        trade_prefix=meta.get("trade_prefix"),
        default_level=meta.get("default_level", 50),
        points_kind=meta.get("points_kind", "ev"),  # type: ignore[arg-type]
        analysis=team_analysis_service.stored_analysis(team, member_payloads),
    )


def _resolve_member_form(
    payload: dict,
    form_names: dict[tuple[int, str], str],
    base_names: dict[int, str],
) -> str | None:
    """成员配置 → 本地形态（`default` 表示明确选择默认形态）。

    已保存队伍只存 Showdown 名，这里按优先级还原：
      1. 与默认形态的 Showdown 名相同 → `default`（避免编辑器把它当成「自动」
         而替换成使用率更高的形态）；
      2. 命中 `pokemon_form` 的非默认形态 → 该形态 slug；
      3. 都不是（数据缺失 / 自定义名字）→ None，交给前端「自动」。
    """
    showdown_name = (payload.get("showdown_name") or "").lower()
    dex = payload.get("dex_number")
    if not showdown_name or dex is None:
        return None
    base_name = base_names.get(dex, "")
    default_showdown = form_service.showdown_name_for(base_name) or base_name
    if default_showdown and showdown_name == default_showdown.lower():
        return "default"
    return form_names.get((dex, showdown_name))


@router.get(
    "/teams",
    response_model=TeamListResponse,
    summary="队伍列表",
    description="全部双打队伍（个人自用，不做浏览器隔离），以及可建队的格式。",
)
async def list_teams(session: DbSession) -> TeamListResponse:
    teams = await team_service.list_teams(session)
    items = []
    for team in teams:
        members = await team_service.get_members(session, team.id)
        items.append(_summary(team, member_count=len(members)))

    formats = [
        {
            **team_service.format_meta(fmt.key),
            "entries": 0,
        }
        for fmt in await team_service.available_formats(session)
    ]
    return TeamListResponse(items=items, formats=formats)


@router.put(
    "/teams/order",
    response_model=TeamListResponse,
    summary="保存队伍顺序",
    description=(
        "拖拽排序后提交完整 id 列表，按顺序重写显示权重。"
        "不存在的 id 会被忽略（例如另一标签页刚删除）。"
    ),
)
async def reorder_teams(session: DbSession, payload: TeamReorderRequest) -> TeamListResponse:
    await team_service.reorder_teams(session, payload.team_ids)
    return await list_teams(session)


@router.post(
    "/teams",
    response_model=TeamDetail,
    summary="新建队伍",
    description=f"最多 {TEAM_SIZE} 只；编号与道具不可重复，招式 / 特性需在该版本可用。",
)
async def create_team(session: DbSession, payload: TeamCreate) -> TeamDetail:
    _validate_format(payload.format_key)
    members = [member.model_dump() for member in payload.members]
    validation = await team_service.validate_members(session, payload.format_key, members)
    if not validation.ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[issue.message for issue in validation.issues],
        )

    try:
        team = await team_service.create_team(
            session,
            name=payload.name,
            format_key=payload.format_key,
            note=payload.note,
            members=members,
        )
    except team_service.TeamError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return await _detail(session, team)


@router.get(
    "/teams/{team_id}",
    response_model=TeamDetail,
    summary="队伍详情",
)
async def get_team(session: DbSession, team_id: int) -> TeamDetail:
    team = await team_service.get_team(session, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="队伍不存在")
    return await _detail(session, team)


@router.put(
    "/teams/{team_id}",
    response_model=TeamDetail,
    summary="更新队伍",
)
async def update_team(
    session: DbSession, team_id: int, payload: TeamUpdate
) -> TeamDetail:
    team = await team_service.get_team(session, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="队伍不存在")

    members = None
    if payload.members is not None:
        members = [member.model_dump() for member in payload.members]
        validation = await team_service.validate_members(session, team.format_key, members)
        if not validation.ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=[issue.message for issue in validation.issues],
            )

    await team_service.update_team(
        session,
        team,
        name=payload.name,
        note=payload.note,
        members=members,
    )
    return await _detail(session, team)


@router.delete(
    "/teams/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除队伍",
)
async def delete_team(session: DbSession, team_id: int) -> None:
    team = await team_service.get_team(session, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="队伍不存在")
    await team_service.delete_team(session, team)


@router.post(
    "/teams/import",
    response_model=TeamImportResponse,
    summary="从 Showdown 代码导入",
    description=(
        "解析 Showdown 队伍文本，返回可编辑的成员配置（不落库）。"
        "无法识别的物种 / 超出的条目会列在 `problems` 里，前端展示给用户确认。"
    ),
)
async def import_team(
    session: DbSession, payload: TeamImportRequest
) -> TeamImportResponse:
    _validate_format(payload.format_key)
    outcome = await team_service.import_showdown(session, payload.format_key, payload.text)
    return TeamImportResponse(
        format_key=payload.format_key,
        members=[TeamMemberInput(**member) for member in outcome.members],
        problems=outcome.problems,
        warnings=outcome.warnings,
    )


@router.post(
    "/teams/batch",
    response_model=TeamBatchResponse,
    summary="批量修改成员",
    description=(
        "对一组成员统一设置闪光 / 等级 / 性别，返回改好的成员（不落库）。"
        "不合法的改动会保持原样并在 `skipped` 里说明（如尼多朗只能雄性）。"
    ),
)
async def batch_members(
    session: DbSession, payload: TeamBatchRequest
) -> TeamBatchResponse:
    fields = payload.model_fields_set
    members = [member.model_dump() for member in payload.members]
    updated, skipped = await team_service.apply_batch(
        session,
        members,
        shine=payload.shine if "shine" in fields else None,
        set_level="level" in fields,
        level=payload.level,
        set_gender="gender" in fields,
        gender=payload.gender,
    )
    return TeamBatchResponse(
        members=[
            TeamMemberView(**{**member, "position": position})
            for position, member in enumerate(updated)
        ],
        skipped=skipped,
    )


@router.post(
    "/teams/analyze",
    response_model=TeamAnalysis,
    summary="队伍评价（草稿）",
    description=(
        "按属性计算打击面 / 缺失面 / 共同弱点，并（可选）由 LLM 生成改进建议与玩法推荐。"
        "只评价请求里带来的成员，**不落库** —— 已保存的队伍请用 "
        "`POST /teams/{id}/analyze`，评价会存到队伍上。"
        "LLM 不可用时仍返回计算结果，`llm_error` 说明原因。"
    ),
)
async def analyze_team_payload(
    session: DbSession, payload: TeamAnalyzeRequest
) -> TeamAnalysis:
    _validate_format(payload.format_key)
    members = [member.model_dump() for member in payload.members]
    meta = team_service.format_meta(payload.format_key)
    result = await team_analysis_service.evaluate_team(
        session,
        members,
        use_llm=payload.use_llm,
        format_key=payload.format_key,
        default_level=meta.get("default_level", 50),
    )
    return TeamAnalysis(**result)


#: SSE 响应头。`X-Accel-Buffering: no` 关掉反向代理的缓冲，否则前端收不到增量。
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(payload: dict) -> str:
    """SSE 帧（`data: <json>\\n\\n`）。事件类型放在 JSON 里，前端解析更省事。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post(
    "/teams/analyze/stream",
    summary="队伍评价（草稿，流式）",
    description=(
        "与 `POST /teams/analyze` 同样的计算，但以 SSE 流式返回："
        "先推 `coverage`（打击面 / 缺失面 / 共同弱点），再逐段推 `delta`（AI 正文增量），"
        "最后推 `done`。不落库。"
    ),
)
async def analyze_team_stream(payload: TeamAnalyzeRequest) -> StreamingResponse:
    _validate_format(payload.format_key)
    members = [member.model_dump() for member in payload.members]
    meta = team_service.format_meta(payload.format_key)
    return StreamingResponse(
        _stream_draft(
            members,
            payload.use_llm,
            format_key=payload.format_key,
            default_level=meta.get("default_level", 50),
        ),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _stream_draft(
    members: list[dict], use_llm: bool, *, format_key: str, default_level: int
) -> AsyncIterator[str]:
    """草稿流：不落库。生成器里自开会话 —— SSE 期间请求依赖注入的会话已关闭。"""
    async with session_scope() as session:
        async for event in team_analysis_service.stream_team_analysis(
            session,
            members,
            use_llm=use_llm,
            format_key=format_key,
            default_level=default_level,
        ):
            yield _sse(event)


@router.post(
    "/teams/{team_id}/analyze",
    response_model=TeamDetail,
    summary="生成并保存队伍评价",
    description=(
        "对已保存的队伍按**库里的成员**重新评价（忽略请求体里的 members，"
        "所以评价永远对应真实保存的配置），并把结果存到队伍上。"
        "再次调用即「更新评价」：覆盖旧快照与时间戳。"
    ),
)
async def analyze_saved_team(
    session: DbSession,
    team_id: int,
    use_llm: bool = Query(default=True, description="是否调用 LLM 生成建议"),
) -> TeamDetail:
    team = await team_service.get_team(session, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="队伍不存在")

    stored = await team_service.get_members(session, team.id)
    members = [team_service.member_payload(member) for member in stored]
    meta = team_service.format_meta(team.format_key)
    analysis = await team_analysis_service.evaluate_team(
        session,
        members,
        use_llm=use_llm,
        format_key=team.format_key,
        default_level=meta.get("default_level", 50),
    )
    await team_analysis_service.save_analysis(session, team, analysis, members)
    return await _detail(session, team)


@router.post(
    "/teams/{team_id}/analyze/stream",
    summary="生成并保存队伍评价（流式）",
    description=(
        "与 `POST /teams/{id}/analyze` 相同，但以 SSE 流式返回。"
        "流结束时把完整评价连同成员指纹存到队伍上；若 LLM 失败，仍会保存计算结果。"
    ),
)
async def analyze_saved_team_stream(
    team_id: int,
    use_llm: bool = Query(default=True, description="是否调用 LLM 生成建议"),
) -> StreamingResponse:
    # 先在同一请求里确认队伍存在，避免流开始后才报 404（状态码已经发出去了）
    async with session_scope() as session:
        team = await team_service.get_team(session, team_id)
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="队伍不存在")

    return StreamingResponse(
        _stream_saved(team_id, use_llm),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _stream_saved(team_id: int, use_llm: bool) -> AsyncIterator[str]:
    """落库流：边推边攒，结束时把完整评价存到队伍上。"""
    async with session_scope() as session:
        team = await team_service.get_team(session, team_id)
        if team is None:  # 理论上已被上面的存在性检查拦下
            yield _sse({"event": "error", "text": "队伍不存在"})
            return

        stored = await team_service.get_members(session, team.id)
        members = [team_service.member_payload(member) for member in stored]
        meta = team_service.format_meta(team.format_key)

        analysis: dict | None = None
        async for event in team_analysis_service.stream_team_analysis(
            session,
            members,
            use_llm=use_llm,
            format_key=team.format_key,
            default_level=meta.get("default_level", 50),
        ):
            if event["event"] == "coverage":
                analysis = event["data"]
            elif event["event"] == "done":
                # 把流式正文拼回快照，读回时与一次性接口完全一致
                if analysis is not None and event.get("text"):
                    analysis["llm"] = {"text": event["text"], "model": event.get("model")}
                if analysis is not None:
                    await team_analysis_service.save_analysis(
                        session, team, analysis, members
                    )
            elif event["event"] == "error":
                # LLM 失败也把计算结果存下来（与一次性接口的降级行为一致）
                if analysis is not None:
                    analysis["llm_error"] = event["text"]
                    await team_analysis_service.save_analysis(
                        session, team, analysis, members
                    )
            yield _sse(event)


@router.post(
    "/teams/validate",
    response_model=TeamValidationResult,
    summary="校验队伍",
    description="不落库，只返回校验结果；前端在编辑过程中实时调用。",
)
async def validate_team_payload(
    session: DbSession, payload: TeamCreate
) -> TeamValidationResult:
    _validate_format(payload.format_key)
    members = [member.model_dump() for member in payload.members]
    dex_numbers = [member["dex_number"] for member in members]
    context = await team_service.build_validation_context(
        session, payload.format_key, dex_numbers
    )
    result = validate_team(
        members,
        points_kind=context.points_kind,
        legal_moves=context.legal_moves,
        legal_abilities=context.legal_abilities,
        moves_known=context.moves_known,
        format_key=payload.format_key,
        gmax_allowed=team_service.gigantamax_allowed_names(),
    )
    return TeamValidationResult(
        ok=result.ok,
        issues=[
            ValidationIssue(field=issue.field, message=issue.message)
            for issue in result.issues
        ],
        data_warnings=context.warnings,
        warnings=context.warnings,
    )


@router.get(
    "/teams/{team_id}/showdown",
    summary="队伍 Showdown 代码",
    description="整队导出为 Showdown 文本；BDSP / 剑盾 / 朱紫带交易前缀，冠军不带。",
)
async def team_showdown(session: DbSession, team_id: int) -> dict:
    team = await team_service.get_team(session, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="队伍不存在")

    members = await team_service.get_members(session, team.id)
    meta = team_service.format_meta(team.format_key)
    body = showdown_export.render_team(
        (team_service.member_payload(member) for member in members),
        format_key=team.format_key,
        default_level=meta.get("default_level", 50),
    )
    prefix = meta.get("trade_prefix")
    return {
        "team_id": team.id,
        "name": team.name,
        "format_key": team.format_key,
        "format_label": meta.get("label"),
        "trade_prefix": prefix,
        "points_kind": meta.get("points_kind", "ev"),
        "text": f"{prefix}\n{body}" if prefix and body else body,
    }


@router.get(
    "/pokemon/{dex_number}/team-options",
    response_model=TeamMemberOptions,
    summary="建队选项",
    description=(
        "某只宝可梦在某个格式下的建队选项：可切换的形态、该形态在该版本可学的全部招式、"
        "可用特性，以及按使用率整理的推荐配置（特性 / 道具 / 招式 / 配点 / 性格 / IV 建议）。"
        "传 `form` 时按该形态返回；不传时取该编号下使用率最高的形态（如洛托姆 → 清洗洛托姆）。"
    ),
)
async def team_options(
    session: DbSession,
    dex_number: int,
    format: str = Query(default="sv", description=f"格式：{', '.join(FORMAT_KEYS)}"),
    form: str | None = Query(
        default=None,
        max_length=64,
        description=(
            "形态 slug（`pokemon_form.name`，如 `rotom-wash`）；"
            "`default` 表示明确选默认形态；不传则取使用率最高的形态"
        ),
    ),
) -> TeamMemberOptions:
    _validate_format(format)
    pokemon = await pokemon_repo.get_by_dex_number(session, dex_number)
    if pokemon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"图鉴编号 {dex_number} 不存在"
        )
    fmt = FORMAT_BY_KEY[format]

    # `form=default` 表示明确选默认形态（与图鉴详情页同一约定）；
    # 不传 form 则是「自动选使用率最高的形态」，两者必须区分开。
    explicit_default = form == DEFAULT_FORM
    selected_form = None if explicit_default else form
    # `form=xxx-gmax`：超极巨化不是可选形态，按「默认形态 + 超极巨化」处理
    gmax_requested = bool(selected_form and selected_form.endswith("-gmax"))
    if gmax_requested:
        explicit_default = True
        selected_form = None

    local_forms = await form_service.list_forms_with_showdown(session, dex_number)
    known_forms = {item["form"] for item in local_forms}
    if selected_form is not None and selected_form not in known_forms:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"未知形态 {form!r}；可选值见不带 form 时的 forms 字段",
        )

    # ---------- 每个形态的统计（每个形态一条，按使用率降序） ----------
    stats = await doubles_service.get_stats_for_dex(session, dex_number, fmt.key)
    stat_by_name = {row.showdown_name: row for row in stats}

    # ---------- 形态清单（含默认形态），按使用率降序 ----------
    showdown_map = form_service.load_form_showdown_map()
    default_showdown = showdown_map.get(pokemon.name_en) or _display_en(pokemon.name_en)
    candidates: list[dict] = [
        {
            "form": None,
            "label": pokemon.name_zh or pokemon.name_en,
            "showdown_name": default_showdown,
            "types": pokemon_repo.parse_json_fields(pokemon)["types"],
            "sprite_url": _media_or_remote(pokemon_repo.parse_json_fields(pokemon), "sprite"),
            "is_default": True,
            "usage": stat_by_name.get(default_showdown).usage
            if stat_by_name.get(default_showdown)
            else None,
        }
    ]
    for item in local_forms:
        showdown_name = item["showdown_name"] or _display_en(item["form"])
        stat = stat_by_name.get(showdown_name)
        candidates.append(
            {
                "form": item["form"],
                "label": item["label"],
                "showdown_name": showdown_name,
                "types": item["types"],
                "sprite_url": item["sprite_url"],
                "is_default": False,
                "usage": stat.usage if stat is not None else None,
            }
        )
    # 使用率降序；没有统计的排后面（保持默认形态优先的稳定顺序）
    candidates.sort(
        key=lambda item: (
            item["usage"] is None,
            -(item["usage"] or 0.0),
            0 if item["is_default"] else 1,
        )
    )

    if explicit_default:
        chosen = next(item for item in candidates if item["is_default"])
    elif selected_form is not None:
        chosen = next(item for item in candidates if item["form"] == selected_form)
    else:
        # 不传 form：取使用率最高的形态；全都没有统计时用默认形态
        chosen = next((item for item in candidates if item["usage"] is not None), candidates[0])

    # 默认形态没有独立统计时，退回该编号下使用率最高的那条（与旧行为一致）
    stat = stat_by_name.get(chosen["showdown_name"]) or (stats[0] if stats else None)

    # ---------- 该形态的合法招式 / 特性 ----------
    legal_move_slugs = await _legal_moves_for_form(session, dex_number, chosen["form"], format)
    move_refs = await pokemon_repo.get_move_refs(session, sorted(legal_move_slugs))
    labels = doubles_service.load_labels()
    move_labels = labels.get("moves", {})
    move_labels_en = labels.get("moves_en", {})

    legal_moves = [
        TeamOptionUsage(
            slug=slug,
            name=move_labels.get(slug) or move_refs.get(slug, {}).get("zh") or slug,
            name_en=move_labels_en.get(slug) or _display_en(slug),
            type=move_refs.get(slug, {}).get("type"),
            pct=0,
        )
        for slug in sorted(legal_move_slugs)
    ]

    ability_names = await _legal_abilities_for_form(
        session, dex_number, chosen["form"], format
    )
    ability_labels_zh = _ability_labels()
    ability_labels_en = _ability_labels_en()
    legal_abilities = [
        TeamOptionUsage(
            slug=name,
            name=(
                ability_labels_zh.get(doubles_service.showdown_slug(name))
                or ability_labels_zh.get(name)
                or name
            ),
            name_en=(
                ability_labels_en.get(doubles_service.showdown_slug(name))
                or ability_labels_en.get(name)
                or name
            ),
            pct=0,
        )
        for name in sorted(ability_names)
    ]

    recommendations = await _recommendation_for_stat(session, stat)
    legal_items = await _legal_items(session, recommendations)
    gmax = form_service.gigantamax_info(chosen["showdown_name"])

    fields = pokemon_repo.parse_json_fields(pokemon)
    return TeamMemberOptions(
        dex_number=dex_number,
        showdown_name=chosen["showdown_name"],
        name_zh=pokemon.name_zh,
        name_en=pokemon.name_en,
        types=chosen["types"],
        artwork_url=_media_or_remote(fields, "artwork")
        if chosen["is_default"]
        else chosen["sprite_url"],
        sprite_url=chosen["sprite_url"],
        gender_rate=pokemon.gender_rate,
        form=chosen["form"],
        forms=[TeamFormOption(**item) for item in candidates],
        legal_moves=legal_moves,
        legal_abilities=legal_abilities,
        legal_items=legal_items,
        recommended=recommendations,
        has_stats=recommendations is not None,
        can_gigantamax=gmax is not None,
        gigantamax_move=gmax["gmax_move"] if gmax else None,
        gigantamax=gmax is not None and gmax_requested,
    )


async def _legal_moves_for_form(
    session, dex_number: int, form: str | None, format_key: str
) -> set[str]:
    """该形态在该版本可学的招式。

    形态专属招式（洛托姆的「热水」、厄诡椪的「棘藤棒」）只在形态的招式表里，
    所以选了形态就按形态取；不选形态时用校验上下文的合并结果（含进化链前代）。
    """
    if form is None:
        context = await team_service.build_validation_context(session, format_key, [dex_number])
        return context.legal_moves.get(dex_number, set())

    version_group = FORMAT_VERSION_GROUP[format_key]
    rows = await pokemon_repo.get_form_moves_map(session, [dex_number], version_group)
    legal: set[str] = set()
    for form_name, methods_json in rows.get(dex_number, []):
        if showdown_slug(form_name) != showdown_slug(form):
            continue
        try:
            methods = json.loads(methods_json or "{}")
        except json.JSONDecodeError:
            continue
        for entries in methods.values():
            for entry in entries:
                if isinstance(entry, dict) and entry.get("name"):
                    legal.add(entry["name"])
    if legal:
        return legal
    # 形态招式表缺失（旧库未回填）时退回合并结果，不把「没数据」当成「不会」
    context = await team_service.build_validation_context(session, format_key, [dex_number])
    return context.legal_moves.get(dex_number, set())


async def _legal_abilities_for_form(
    session, dex_number: int, form: str | None, format_key: str
) -> set[str]:
    """该形态可用的特性；不指定形态时用校验上下文的合并结果。"""
    context = await team_service.build_validation_context(session, format_key, [dex_number])
    merged = context.legal_abilities.get(dex_number) or set()
    if form is None:
        return merged

    forms = await pokemon_repo.get_form_abilities_map(session, [dex_number])
    for form_json in forms.get(dex_number, []):
        try:
            payload = json.loads(form_json or "[]")
        except json.JSONDecodeError:
            continue
        # 形态表只存 slug，按编号合并；这里无法区分是哪一个形态，直接取并集
        names = {item["name"] for item in payload if isinstance(item, dict) and item.get("name")}
        if names:
            return names | merged
    return merged


async def _recommendation_for_stat(session, stat) -> dict | None:
    """按一条统计记录整理推荐配置（与详情页双打辅助同源）。"""
    if stat is None:
        return None
    return await _build_recommendation(session, stat)


async def _legal_items(session, recommendations: dict | None) -> list[TeamOptionUsage]:
    """该格式统计里出现过的道具（按使用率降序，带图标），供下拉框候选。

    用「这只宝可梦用过」的道具而不是全部 257 个：候选与统计口径一致，
    不会列出一堆从来没在该格式里出现过的条目；统计没有这只宝可梦时为空，
    前端回落到道具百科的全量列表。
    """
    entries = (recommendations or {}).get("items") or []
    return [
        TeamOptionUsage(
            slug=item["slug"],
            name=item["name"],
            name_en=item.get("name_en"),
            icon_url=item.get("icon_url"),
            pct=item.get("pct", 0.0),
        )
        for item in entries
    ]


def _media_or_remote(fields: dict, kind: str) -> str | None:
    """本地缓存优先的图片地址（与图鉴接口同一约定）。"""
    path = fields.get(f"{kind}_path")
    if path:
        return f"/media/{path}"
    if kind == "artwork":
        return fields.get("artwork_url_remote")
    return fields.get("sprite_url")


def _display_en(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _ability_labels() -> dict[str, str]:
    return doubles_service.load_labels().get("abilities", {})


def _ability_labels_en() -> dict[str, str]:
    return doubles_service.load_labels().get("abilities_en", {})


async def _build_recommendation(session, stat) -> dict:
    """把一条统计记录整理成推荐配置（特性 / 道具 / 招式 / 配点）。"""
    stat_rows = {"abilities": _json(stat.abilities_json), "items": _json(stat.items_json)}
    abilities = doubles_service._usage("abilities", stat_rows["abilities"])
    # 道具带图标（与使用率排行页一致）；_usage 只对 group == "items" 填 icon_url
    items = doubles_service._usage(
        "items",
        stat_rows["items"],
        None,
        doubles_service.item_icon_lookup(
            await doubles_service.load_item_rows(
                session, {slug for slug, _ in stat_rows["items"] if isinstance(slug, str)}
            )
        ),
    )

    move_slugs = [slug for slug, _ in doubles_service.parse_json(stat.moves_json)]
    move_refs = await pokemon_repo.get_move_refs(session, move_slugs)
    move_types = {slug: ref["type"] for slug, ref in move_refs.items() if ref.get("type")}
    moves = doubles_service._usage("moves", doubles_service.parse_json(stat.moves_json), move_types)

    spreads = doubles_service.parse_json(stat.spreads_json)
    top_spread = spreads[0] if spreads else None
    natures = doubles_service.load_labels().get("natures", {})

    return {
        "showdown_name": stat.showdown_name,
        "rank": stat.rank,
        "usage": stat.usage,
        "abilities": abilities,
        "items": items,
        "moves": moves,
        "spread": (
            {
                "nature": top_spread["nature"],
                "nature_label": natures.get(
                    top_spread["nature"], doubles_service.pretty_name(top_spread["nature"])
                ),
                "points": top_spread["points"],
                "pct": top_spread["pct"],
            }
            if top_spread
            else None
        ),
        "spreads": [
            {
                "nature": spread["nature"],
                "nature_label": natures.get(
                    spread["nature"], doubles_service.pretty_name(spread["nature"])
                ),
                "points": spread["points"],
                "pct": spread["pct"],
            }
            for spread in spreads
        ],
    }


def _json(text: str | None) -> list:
    try:
        value = json.loads(text or "[]")
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
