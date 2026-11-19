"""出卷路由（图鉴识别自测 + 错题集）。

`POST /quiz`                     建卷（范围 / 数量 / 随机或全量）
`GET  /quiz/{id}`                读卷（含已答结果；未答的题不泄露答案）
`POST /quiz/{id}/answer`         作答并判分（答错自动进错题集）
`GET  /quiz/mistakes`            错题集
`DELETE /quiz/mistakes/{dex}`    移出错题集
`DELETE /quiz/mistakes`          清空错题集

判分规则见 `domain/quiz.py`：接受中英文名，忽略大小写 / 空格 / 连字符 / 标点。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.schemas.quiz import (
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizCreateRequest,
    QuizCreateResponse,
    QuizMistakeListResponse,
    QuizSessionView,
)
from app.services import quiz_service

router = APIRouter(prefix="/quiz", tags=["quiz"])


def _to_view(data: dict) -> QuizSessionView:
    return QuizSessionView(**data)


@router.post(
    "",
    response_model=QuizCreateResponse,
    summary="出一份试卷",
    description=(
        "按世代 / 编号区间筛选候选，随机抽 `count` 只或出全量（`mode=all`）。"
        "题目只含图鉴图片，答案（名称）在作答前不返回。"
    ),
)
async def create_quiz(session: DbSession, payload: QuizCreateRequest) -> QuizCreateResponse:
    try:
        data = await quiz_service.create_quiz(
            session,
            generation=payload.generation,
            dex_from=payload.dex_from,
            dex_to=payload.dex_to,
            count=payload.count,
            mode=payload.mode,
        )
    except quiz_service.QuizError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return QuizCreateResponse(session=_to_view(data))


@router.get(
    "/mistakes",
    response_model=QuizMistakeListResponse,
    summary="错题集",
    description="答错自动记录，按错误次数降序；名称与图片取当前图鉴数据。",
)
async def list_mistakes(session: DbSession) -> QuizMistakeListResponse:
    return QuizMistakeListResponse(**await quiz_service.list_mistakes(session))


@router.delete(
    "/mistakes",
    summary="清空错题集",
    description="删除全部错题记录，返回删除条数。",
)
async def clear_mistakes(session: DbSession) -> dict:
    return {"deleted": await quiz_service.clear_mistakes(session)}


@router.delete(
    "/mistakes/{dex_number}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移出一道错题",
)
async def remove_mistake(session: DbSession, dex_number: int) -> None:
    try:
        await quiz_service.remove_mistake(session, dex_number)
    except quiz_service.QuizNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/{quiz_id}", response_model=QuizSessionView, summary="读取试卷")
async def get_quiz(session: DbSession, quiz_id: int) -> QuizSessionView:
    try:
        return _to_view(await quiz_service.get_quiz(session, quiz_id))
    except quiz_service.QuizNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post(
    "/{quiz_id}/answer",
    response_model=QuizAnswerResponse,
    summary="作答一题",
    description="接受中文名或英文名；答错会自动进错题集。返回判分结果与整卷进度。",
)
async def answer_question(
    session: DbSession, quiz_id: int, payload: QuizAnswerRequest
) -> QuizAnswerResponse:
    try:
        data = await quiz_service.answer_question(
            session, quiz_id, payload.position, payload.answer
        )
    except quiz_service.QuizNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except quiz_service.QuizError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return QuizAnswerResponse(
        correct=data["correct"],
        expected_zh=data["expected_zh"],
        expected_en=data["expected_en"],
        session=_to_view(data["session"]),
    )
