"""出卷编排：筛选候选 → 抽题 → 建卷 → 判分 → 记错题。

分层：规则（归一化 / 判分 / 抽样）在 `domain/quiz.py` 纯函数里；
本模块负责取数与事务；路由只做参数校验与响应组装。

数据边界：题目里的名称与图片**不落库**，每次都从 `pokemon` 表取当前值 ——
图鉴同步或人工修订后，历史试卷与错题集展示的也是最新名称，不会各存一份。
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QuizMistake, QuizQuestion, QuizSession
from app.domain import quiz as quiz_domain
from app.repositories import pokemon_repo

#: 图片挂载前缀（与路由层一致：本地缓存优先）。
_MEDIA_PREFIX = "/media"


class QuizError(ValueError):
    """出卷 / 答题失败（路由转 4xx）。"""


class QuizNotFound(QuizError):
    """试卷或题目不存在。"""


def _media_or_remote(path: str | None, remote: str | None) -> str | None:
    if path:
        return f"{_MEDIA_PREFIX}/{path}"
    return remote


def _question_view(
    question: QuizQuestion,
    row: tuple[str, str | None, str | None, str | None, str | None] | None,
    *,
    reveal: bool,
) -> dict:
    """一题的响应字段。`reveal=False` 时不泄露答案（答题中直接看 JSON 也猜不到）。"""
    name_en, name_zh, art_path, art_url, sprite_path = row or ("", None, None, None, None)
    view: dict = {
        "position": question.position,
        "dex_number": question.dex_number,
        "artwork_url": _media_or_remote(art_path, art_url),
        "artwork_fallback_url": None,
        "sprite_url": _media_or_remote(sprite_path, None),
        "answer": None,
        "is_correct": None,
        "expected_zh": None,
        "expected_en": None,
    }
    if not reveal:
        return view

    view.update(
        {
            "name_zh": name_zh,
            "name_en": name_en,
            "answer": question.answer,
            "is_correct": question.is_correct,
        }
    )
    # 答错的题目、以及结果页（全部揭开）都给出标准答案
    view["expected_zh"] = name_zh
    view["expected_en"] = name_en
    return view


def _score(correct: int, answered: int) -> int:
    if answered <= 0:
        return 0
    return round(correct * 100 / answered)


async def _session_view(session: AsyncSession, quiz: QuizSession) -> dict:
    questions = list(
        (
            await session.execute(
                select(QuizQuestion)
                .where(QuizQuestion.session_id == quiz.id)
                .order_by(QuizQuestion.position.asc())
            )
        )
        .scalars()
        .all()
    )
    rows = await pokemon_repo.get_quiz_rows_by_dex(
        session, [question.dex_number for question in questions]
    )

    items = []
    for question in questions:
        # 已作答（含答错）的题在答题阶段也要能回看答案；未作答的只给题干
        reveal = bool(quiz.finished_at) or question.is_correct is not None
        items.append(_question_view(question, rows.get(question.dex_number), reveal=reveal))

    return {
        "id": quiz.id,
        "total": quiz.total,
        "answered": quiz.answered,
        "correct": quiz.correct,
        "score": _score(quiz.correct, quiz.answered),
        "finished": bool(quiz.finished_at),
        "scope": json.loads(quiz.scope_json or "{}"),
        "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
        "finished_at": quiz.finished_at.isoformat() if quiz.finished_at else None,
        "questions": items,
    }


async def create_quiz(
    session: AsyncSession,
    *,
    generation: int | None,
    dex_from: int | None,
    dex_to: int | None,
    count: int | None,
    mode: str,
    rng: random.Random | None = None,
) -> dict:
    """按范围抽题并建卷。返回 `QuizSessionView` 结构。"""
    candidates = await pokemon_repo.quiz_candidates(
        session, generation=generation, dex_from=dex_from, dex_to=dex_to
    )
    if not candidates:
        raise QuizError("该范围内没有可出题的宝可梦，请调整世代或编号区间")

    dex_numbers = [row[0] for row in candidates]
    wanted = None if mode == "all" else count
    picked = quiz_domain.pick_dex_numbers(dex_numbers, count=wanted, rng=rng or random.Random())
    if not picked:
        raise QuizError("题目数量必须大于 0")

    scope = {
        "generation": generation,
        "dex_from": dex_from,
        "dex_to": dex_to,
        "count": len(picked),
        "mode": mode,
        "available": len(candidates),
    }
    quiz = QuizSession(
        scope_json=json.dumps(scope, ensure_ascii=False),
        total=len(picked),
        answered=0,
        correct=0,
    )
    session.add(quiz)
    await session.flush()

    session.add_all(
        [
            QuizQuestion(session_id=quiz.id, position=index, dex_number=dex)
            for index, dex in enumerate(picked)
        ]
    )
    await session.flush()
    await session.refresh(quiz)
    return await _session_view(session, quiz)


async def get_quiz(session: AsyncSession, quiz_id: int) -> dict:
    quiz = await session.get(QuizSession, quiz_id)
    if quiz is None:
        raise QuizNotFound("试卷不存在")
    return await _session_view(session, quiz)


async def answer_question(
    session: AsyncSession, quiz_id: int, position: int, answer: str
) -> dict:
    """判分并累计进度；答错自动进错题集。

    同一题重复提交：以最后一次为准（覆盖作答与计数），不会把正确数重复累加 ——
    用户的「错题集」只反映最终作答是错误的那些。
    """
    quiz = await session.get(QuizSession, quiz_id)
    if quiz is None:
        raise QuizNotFound("试卷不存在")
    if quiz.finished_at is not None:
        raise QuizError("这份试卷已完成，不能继续作答")

    question = (
        await session.execute(
            select(QuizQuestion).where(
                QuizQuestion.session_id == quiz_id, QuizQuestion.position == position
            )
        )
    ).scalar_one_or_none()
    if question is None:
        raise QuizNotFound("题目不存在")
    if question.is_correct is not None:
        raise QuizError("这道题已经答过了")

    row = (await pokemon_repo.get_quiz_rows_by_dex(session, [question.dex_number])).get(
        question.dex_number
    )
    if row is None:
        raise QuizNotFound("题目对应的宝可梦已不在图鉴中")
    name_en, name_zh = row[0], row[1]

    verdict = quiz_domain.judge(answer, name_zh=name_zh, name_en=name_en)
    question.answer = answer.strip()[:64] or None
    question.is_correct = verdict.correct
    question.answered_at = datetime.now(UTC)
    quiz.answered += 1
    if verdict.correct:
        quiz.correct += 1

    if not verdict.correct:
        await _record_mistake(session, question.dex_number, answer)

    if quiz.answered >= quiz.total:
        quiz.finished_at = datetime.now(UTC)

    await session.flush()
    await session.refresh(quiz)
    return {
        "correct": verdict.correct,
        "expected_zh": name_zh,
        "expected_en": name_en,
        "session": await _session_view(session, quiz),
    }


async def _record_mistake(session: AsyncSession, dex_number: int, answer: str) -> None:
    """错题 upsert：同一只累计次数，保留最近一次的作答原文。"""
    mistake = (
        await session.execute(
            select(QuizMistake).where(QuizMistake.dex_number == dex_number)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if mistake is None:
        session.add(
            QuizMistake(
                dex_number=dex_number,
                wrong_count=1,
                last_answer=answer.strip()[:64] or None,
                first_wrong_at=now,
                last_wrong_at=now,
            )
        )
    else:
        mistake.wrong_count += 1
        mistake.last_answer = answer.strip()[:64] or None
        mistake.last_wrong_at = now


async def list_mistakes(session: AsyncSession) -> dict:
    """错题集：错误的次数降序，其次最近出错时间。"""
    mistakes = list(
        (
            await session.execute(
                select(QuizMistake).order_by(
                    QuizMistake.wrong_count.desc(), QuizMistake.last_wrong_at.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    rows = await pokemon_repo.get_quiz_rows_by_dex(
        session, [mistake.dex_number for mistake in mistakes]
    )

    items = []
    for mistake in mistakes:
        row = rows.get(mistake.dex_number)
        if row is None:
            continue  # 图鉴里已没有这只（例如手工删过），不展示悬空条目
        name_en, name_zh, art_path, art_url, sprite_path = row
        items.append(
            {
                "dex_number": mistake.dex_number,
                "name_zh": name_zh,
                "name_en": name_en,
                "sprite_url": _media_or_remote(sprite_path, None),
                "artwork_url": _media_or_remote(art_path, art_url),
                "wrong_count": mistake.wrong_count,
                "last_answer": mistake.last_answer,
                "first_wrong_at": (
                    mistake.first_wrong_at.isoformat() if mistake.first_wrong_at else None
                ),
                "last_wrong_at": (
                    mistake.last_wrong_at.isoformat() if mistake.last_wrong_at else None
                ),
            }
        )
    return {"items": items, "total": len(items)}


async def remove_mistake(session: AsyncSession, dex_number: int) -> None:
    result = await session.execute(
        delete(QuizMistake).where(QuizMistake.dex_number == dex_number)
    )
    if result.rowcount == 0:
        raise QuizNotFound("错题集里没有这只宝可梦")


async def clear_mistakes(session: AsyncSession) -> int:
    result = await session.execute(delete(QuizMistake))
    return int(result.rowcount or 0)


async def mistake_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(QuizMistake))).scalar_one()


__all__ = [
    "QuizError",
    "QuizNotFound",
    "answer_question",
    "clear_mistakes",
    "create_quiz",
    "get_quiz",
    "list_mistakes",
    "mistake_count",
    "remove_mistake",
]
