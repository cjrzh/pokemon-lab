"""出卷接口测试：范围筛选、随机/全量、判分、错题集。"""

from __future__ import annotations

import json
import random

from httpx import AsyncClient

from app.db.engine import get_session_factory
from app.domain import quiz as quiz_domain
from app.repositories import pokemon_repo

QUIZ_URL = "/api/v1/quiz"

POKEMON = [
    (1, "bulbasaur", "妙蛙种子", 1),
    (4, "charmander", "小火龙", 1),
    (7, "squirtle", "杰尼龟", 1),
    (25, "pikachu", "皮卡丘", 1),
    (152, "chikorita", "菊草叶", 2),
    (155, "cyndaquil", "火球鼠", 2),
]


def _pokemon(dex: int, name_en: str, name_zh: str, generation: int):
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_zh,
        types_json=json.dumps(["normal"]),
        stats_json="{}",
        abilities_json="[]",
        evolution_json="{}",
        moves_json="{}",
        generation_introduced=generation,
        source="pokeapi",
        artwork_path=f"artwork/{dex}.png",
        sprite_path=f"sprites/{dex}.png",
    )


async def _seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add_all([_pokemon(*row) for row in POKEMON])
        await session.commit()


async def _create(client: AsyncClient, **payload) -> dict:
    response = await client.post(QUIZ_URL, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["session"]


async def test_quiz_hides_answers_until_answered(client: AsyncClient) -> None:
    await _seed()
    quiz = await _create(client, count=2)

    assert quiz["total"] == 2
    for question in quiz["questions"]:
        assert question["name_zh"] is None
        assert question["name_en"] is None
        assert question["expected_en"] is None
        assert question["artwork_url"]  # 图片地址来自本地缓存
        assert question["sprite_url"]


async def test_answer_correct_with_chinese_name(client: AsyncClient) -> None:
    await _seed()
    quiz = await _create(client, mode="all")
    question = quiz["questions"][0]

    response = await client.post(
        f"{QUIZ_URL}/{quiz['id']}/answer",
        json={"position": 0, "answer": question["dex_number"] and "妙蛙种子"},
    )
    # 第一题是全量顺序下的 #1
    assert quiz["questions"][0]["dex_number"] == 1
    body = response.json()
    assert response.status_code == 200, response.text
    assert body["correct"] is True
    assert body["expected_en"] == "bulbasaur"
    assert body["session"]["answered"] == 1
    assert body["session"]["correct"] == 1


async def test_answer_accepts_english_name_and_normalizes(client: AsyncClient) -> None:
    await _seed()
    quiz = await _create(client, mode="all")

    # 英文名，带大写与多余空格
    body = (
        await client.post(
            f"{QUIZ_URL}/{quiz['id']}/answer",
            json={"position": 0, "answer": "  BULBASAUR "},
        )
    ).json()
    assert body["correct"] is True


async def test_wrong_answer_goes_to_mistake_list(client: AsyncClient) -> None:
    await _seed()
    quiz = await _create(client, mode="all")

    body = (
        await client.post(
            f"{QUIZ_URL}/{quiz['id']}/answer",
            json={"position": 0, "answer": "皮卡丘"},
        )
    ).json()
    assert body["correct"] is False
    assert body["expected_zh"] == "妙蛙种子"
    assert body["session"]["correct"] == 0

    mistakes = (await client.get(f"{QUIZ_URL}/mistakes")).json()
    assert mistakes["total"] == 1
    assert mistakes["items"][0]["dex_number"] == 1
    assert mistakes["items"][0]["wrong_count"] == 1
    assert mistakes["items"][0]["last_answer"] == "皮卡丘"


async def test_repeated_mistake_accumulates(client: AsyncClient) -> None:
    await _seed()
    first = await _create(client, mode="all")
    second = await _create(client, mode="all")

    for quiz in (first, second):
        await client.post(
            f"{QUIZ_URL}/{quiz['id']}/answer",
            json={"position": 0, "answer": "错"},
        )

    mistakes = (await client.get(f"{QUIZ_URL}/mistakes")).json()
    assert mistakes["total"] == 1
    assert mistakes["items"][0]["wrong_count"] == 2


async def test_finished_quiz_rejects_more_answers(client: AsyncClient) -> None:
    await _seed()
    quiz = await _create(client, count=1)

    await client.post(f"{QUIZ_URL}/{quiz['id']}/answer", json={"position": 0, "answer": "x"})

    response = await client.post(
        f"{QUIZ_URL}/{quiz['id']}/answer", json={"position": 0, "answer": "y"}
    )
    assert response.status_code == 409


async def test_generation_and_range_filters(client: AsyncClient) -> None:
    await _seed()

    gen2 = await _create(client, generation=2, mode="all")
    assert {q["dex_number"] for q in gen2["questions"]} == {152, 155}

    ranged = await _create(client, dex_from=4, dex_to=25, mode="all")
    assert [q["dex_number"] for q in ranged["questions"]] == [4, 7, 25]

    empty = await client.post(QUIZ_URL, json={"dex_from": 900, "dex_to": 950})
    assert empty.status_code == 422


async def test_random_count_does_not_exceed_candidates(client: AsyncClient) -> None:
    await _seed()
    quiz = await _create(client, count=100, mode="random")
    assert quiz["total"] == len(POKEMON)
    assert len({q["dex_number"] for q in quiz["questions"]}) == quiz["total"]


async def test_mistake_remove_and_clear(client: AsyncClient) -> None:
    await _seed()
    quiz = await _create(client, mode="all")
    for position in range(2):
        await client.post(
            f"{QUIZ_URL}/{quiz['id']}/answer",
            json={"position": position, "answer": "错"},
        )

    assert (await client.get(f"{QUIZ_URL}/mistakes")).json()["total"] == 2
    assert (
        await client.delete(f"{QUIZ_URL}/mistakes/1")
    ).status_code == 204
    assert (await client.get(f"{QUIZ_URL}/mistakes")).json()["total"] == 1

    cleared = (await client.delete(f"{QUIZ_URL}/mistakes")).json()
    assert cleared["deleted"] == 1
    assert (await client.get(f"{QUIZ_URL}/mistakes")).json()["total"] == 0


async def test_unknown_quiz_returns_404(client: AsyncClient) -> None:
    await _seed()
    assert (await client.get(f"{QUIZ_URL}/9999")).status_code == 404


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------


def test_normalize_answer_handles_width_case_and_punctuation() -> None:
    assert quiz_domain.normalize_answer("Mr. Mime") == "mrmime"
    assert quiz_domain.normalize_answer("ｍｒ－ｍｉｍｅ") == "mrmime"
    assert quiz_domain.normalize_answer("  Mr Mime  ") == "mrmime"


def test_judge_accepts_both_languages() -> None:
    assert quiz_domain.judge("妙蛙种子", name_zh="妙蛙种子", name_en="bulbasaur").correct
    assert quiz_domain.judge("BULBASAUR", name_zh="妙蛙种子", name_en="bulbasaur").correct
    assert not quiz_domain.judge("", name_zh="妙蛙种子", name_en="bulbasaur").correct
    assert not quiz_domain.judge("小火龙", name_zh="妙蛙种子", name_en="bulbasaur").correct


def test_pick_dex_numbers_modes() -> None:
    candidates = [7, 1, 4]
    rng = random.Random(0)
    # 全量：按编号升序
    assert quiz_domain.pick_dex_numbers(candidates, count=None, rng=rng) == [1, 4, 7]
    # 数量超过候选：仍返回全部
    assert quiz_domain.pick_dex_numbers(candidates, count=99, rng=rng) == [1, 4, 7]
    # 随机：不重复、数量正确
    picked = quiz_domain.pick_dex_numbers(candidates, count=2, rng=random.Random(1))
    assert len(picked) == 2 and len(set(picked)) == 2
    assert set(picked) <= {1, 4, 7}
