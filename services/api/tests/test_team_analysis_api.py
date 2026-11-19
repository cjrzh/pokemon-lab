"""队伍评价接口测试。

LLM 部分用 monkeypatch 替换 `llm_client.complete`，不打真实网络 ——
计算部分（打击面 / 缺失面 / 共同弱点）是纯函数，照常断言。
"""

from __future__ import annotations

import json

from httpx import AsyncClient

from app.clients import llm_client
from app.db.engine import get_session_factory
from app.repositories import pokemon_repo

ANALYZE_URL = "/api/v1/teams/analyze"


def _pokemon(dex: int, name_en: str, name_zh: str, types: list[str]):
    return pokemon_repo.Pokemon(
        dex_number=dex,
        name_en=name_en,
        name_zh=name_zh,
        types_json=json.dumps(types),
        stats_json="{}",
        abilities_json="[]",
        evolution_json="{}",
        moves_json="{}",
        source="pokeapi",
    )


async def _seed(client: AsyncClient) -> None:
    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                _pokemon(6, "charizard", "喷火龙", ["fire", "flying"]),
                _pokemon(9, "blastoise", "水箭龟", ["water"]),
                _pokemon(26, "raichu", "雷丘", ["electric"]),
            ]
        )
        await session.commit()


def _member(dex: int, name: str, **overrides) -> dict:
    payload = {"dex_number": dex, "showdown_name": name, "evs": [0] * 6, "moves": []}
    payload.update(overrides)
    return payload


async def test_analyze_without_llm_returns_coverage(client: AsyncClient) -> None:
    """use_llm=False 时只做属性计算，不碰 LLM。"""
    await _seed(client)
    payload = (
        await client.post(
            ANALYZE_URL,
            json={
                "members": [_member(6, "Charizard"), _member(9, "Blastoise")],
                "use_llm": False,
            },
        )
    ).json()

    # 属性来自库里的记录
    assert payload["members"][0]["name"] == "喷火龙"
    assert payload["members"][0]["types"] == ["fire", "flying"]

    # 打击面：火系能打到草 / 虫 / 冰 / 钢
    fire = next(item for item in payload["attack"] if item["type"] == "fire")
    assert fire["type_zh"] == "火"
    assert "grass" in fire["hits"]
    assert "草" in fire["hits_zh"]

    # 缺失面带中文
    assert "dragon" in payload["gaps"]
    assert "龙" in payload["gaps_zh"]

    # 共同弱点：喷火龙与水箭龟都被电系克制
    electric = next(item for item in payload["hotspots"] if item["type"] == "electric")
    assert sorted(electric["members"]) == [6, 9]

    assert payload["llm"] is None
    assert payload["llm_error"] is None


async def test_analyze_uses_llm_when_configured(
    client: AsyncClient, monkeypatch
) -> None:
    await _seed(client)
    calls: list[tuple[str, str]] = []

    async def fake_complete(system: str, user: str) -> llm_client.LlmResult:
        calls.append((system, user))
        return llm_client.LlmResult(text="## 队伍评价\n偏特攻。", model="test-model")

    monkeypatch.setattr(llm_client, "complete", fake_complete)

    payload = (
        await client.post(
            ANALYZE_URL,
            json={"members": [_member(6, "Charizard")]},
        )
    ).json()

    assert payload["llm"]["text"].startswith("## 队伍评价")
    assert payload["llm"]["model"] == "test-model"
    assert payload["llm_error"] is None

    # 提示词里带上队伍成员与中文属性（模型据此作答，不能凭空编）
    system, user = calls[0]
    assert "宝可梦" in system
    assert "喷火龙" in user
    assert "火" in user
    assert "缺失面" in user


async def test_analyze_degrades_when_llm_fails(client: AsyncClient, monkeypatch) -> None:
    """LLM 失败不影响计算结果 —— 页面仍能展示打击面与缺失面。"""
    await _seed(client)

    async def failing(system: str, user: str) -> llm_client.LlmResult:
        return llm_client.LlmResult(error="HTTP 503")

    monkeypatch.setattr(llm_client, "complete", failing)

    payload = (
        await client.post(
            ANALYZE_URL,
            json={"members": [_member(6, "Charizard")]},
        )
    ).json()

    assert payload["llm"] is None
    assert payload["llm_error"] == "HTTP 503"
    # 计算结果照常返回
    assert payload["gaps"]
    assert payload["attack"]


async def test_analyze_empty_team(client: AsyncClient) -> None:
    """空队伍不报错：没有打击面，所有属性都是缺口。"""
    await _seed(client)
    payload = (
        await client.post(
            ANALYZE_URL,
            json={"members": [], "use_llm": False},
        )
    ).json()

    assert payload["attack"] == []
    assert payload["hotspots"] == []
    assert len(payload["gaps"]) == 18


# ---------------------------------------------------------------------------
# 流式评价（SSE）
# ---------------------------------------------------------------------------

STREAM_URL = "/api/v1/teams/analyze/stream"


def _parse_sse(text: str) -> list[dict]:
    """把 SSE 文本解析成事件列表（与前端 streamSse 的解析口径一致）。"""
    events: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


async def test_stream_emits_coverage_then_deltas(
    client: AsyncClient, monkeypatch
) -> None:
    """流式顺序：先 coverage（计算），再 delta（正文增量），最后 done。"""
    from app.clients import llm_client

    await _seed(client)

    async def fake_stream(system: str, user: str):
        yield llm_client.LlmChunk(kind="reasoning", text="思考中…", model="test-model")
        yield llm_client.LlmChunk(kind="content", text="## 队伍评价\n", model="test-model")
        yield llm_client.LlmChunk(kind="content", text="偏特攻。", model="test-model")

    monkeypatch.setattr(llm_client, "stream", fake_stream)

    response = await client.post(
        STREAM_URL,
        json={"members": [_member(6, "Charizard"), _member(9, "Blastoise")]},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    kinds = [event["event"] for event in events]
    assert kinds[0] == "coverage"
    assert kinds[-1] == "done"
    assert kinds.count("delta") == 2

    # 计算部分与一次性接口同结构：属性来自库里
    coverage = events[0]["data"]
    assert coverage["members"][0]["name"] == "喷火龙"
    fire = next(item for item in coverage["attack"] if item["type"] == "fire")
    assert "grass" in fire["hits"]

    # 正文增量拼接后等于完整文本
    joined = "".join(e["text"] for e in events if e["event"] == "delta")
    assert joined == "## 队伍评价\n偏特攻。"
    assert events[-1]["text"] == joined


async def test_stream_degrades_when_llm_fails(
    client: AsyncClient, monkeypatch
) -> None:
    """LLM 失败时：coverage 已送达，随后一个 error 事件说明原因。"""
    from app.clients import llm_client

    await _seed(client)

    async def failing_stream(system: str, user: str):
        yield llm_client.LlmChunk(kind="error", text="HTTP 503")

    monkeypatch.setattr(llm_client, "stream", failing_stream)

    response = await client.post(STREAM_URL, json={"members": [_member(6, "Charizard")]})
    events = _parse_sse(response.text)
    kinds = [event["event"] for event in events]

    assert kinds == ["coverage", "error"]
    assert events[0]["data"]["attack"]  # 计算结果仍在
    assert events[1]["text"] == "HTTP 503"


async def test_stream_without_llm_only_coverage(client: AsyncClient) -> None:
    """use_llm=false：只推 coverage + done，不碰 LLM。"""
    await _seed(client)
    response = await client.post(
        STREAM_URL, json={"members": [_member(6, "Charizard")], "use_llm": False}
    )
    events = _parse_sse(response.text)
    assert [event["event"] for event in events] == ["coverage", "done"]


async def test_prompt_includes_full_showdown_config(
    client: AsyncClient, monkeypatch
) -> None:
    """提示词要带整支队伍的 Showdown 代码（道具 / 特性 / 性格 / EV / 招式 / 太晶）。"""
    from app.clients import llm_client

    await _seed(client)
    seen: list[str] = []

    async def fake_complete(system: str, user: str) -> llm_client.LlmResult:
        seen.append(user)
        return llm_client.LlmResult(text="## 队伍评价\nok", model="test-model")

    monkeypatch.setattr(llm_client, "complete", fake_complete)

    member = _member(
        6,
        "Charizard",
        item="Life Orb",
        ability="blaze",
        nature="timid",
        evs=[4, 0, 0, 252, 0, 252],
        moves=["flamethrower", "air-slash", "protect", "roost"],
        tera_type="Fire",
        shiny=True,
    )
    await client.post(
        ANALYZE_URL,
        json={"members": [member], "format_key": "sv"},
    )

    prompt = seen[0]
    # Showdown 代码块里有完整配置
    assert "Charizard @ Life Orb" in prompt
    assert "Ability: blaze" in prompt
    assert "Shiny: Yes" in prompt
    assert "Tera Type: Fire" in prompt
    assert "EVs: 4 HP / 252 SpA / 252 Spe" in prompt
    assert "Timid Nature" in prompt
    assert "- flamethrower" in prompt and "- roost" in prompt
    # 中文名与属性仍保留，便于模型用界面用语作答
    assert "喷火龙" in prompt and "火" in prompt
    # 计算结论也一并给出
    assert "缺失面" in prompt
