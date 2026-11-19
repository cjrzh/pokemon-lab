"""LLM 客户端（OpenAI 兼容的 chat/completions）。

用途：队伍评价里的「改进建议」与「玩法推荐」—— 这两项需要的是把结构化分析
翻译成人话，而不是再算一遍数据。**计算类结论（打击面 / 缺失面 / 共同弱点）
不依赖 LLM**，LLM 只负责解读。

失败处理（个人站点，宁可少给建议也不要报错打断）：
  - 未配置（缺 base_url / key）→ 直接返回 None，接口降级为「只给计算结果」；
  - 主模型超时 / 5xx → 用备用模型再试一次；
  - 仍失败 → 返回 None 并把原因交给调用方，页面显示「暂无法生成建议」。

**流式（`stream`）是队伍评价的主路径。** 网关上的模型是推理模型（会先输出一大段
`reasoning_content` 再给出 `content`），一次完整回答要 10–50 秒；一次性请求会撞上
前端 10 秒的请求超时。改成 SSE 边生成边下发后，只要字节在流动就不会超时，用户也能
更早看到内容。非流式入口 `complete` 保留给不需要增量的场合。

不用 openai SDK：这里只有一个调用点，`httpx` 已经在依赖里，少一个依赖少一处版本耦合。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LlmResult:
    """一次调用的结果。`text` 为 None 表示没拿到内容，`error` 说明原因。"""

    text: str | None = None
    model: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.text)


@dataclass
class LlmChunk:
    """流式增量。

    `kind`：
      - `reasoning`：推理模型的思维链（页面可显示「思考中」但不展示正文）；
      - `content`：正式回答（要展示给用户的部分）；
      - `error`：调用失败，`text` 是原因。
    """

    kind: Literal["reasoning", "content", "error"]
    text: str
    model: str | None = None


def _models() -> list[str]:
    """主模型 + 备用模型（去重）。"""
    settings = get_settings()
    models = [settings.llm_model]
    if settings.llm_fallback_model and settings.llm_fallback_model != settings.llm_model:
        models.append(settings.llm_fallback_model)
    return models


def _payload(model: str, system: str, user: str, *, stream: bool) -> dict:
    settings = get_settings()
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": settings.llm_temperature,
        "top_p": settings.llm_top_p,
        "max_tokens": settings.llm_max_tokens,
    }
    if stream:
        payload["stream"] = True
    if settings.llm_enable_thinking:
        # 部分网关用这个开关控制是否输出思维链；不支持时被忽略（当前网关即忽略）
        payload["enable_thinking"] = True
    return payload


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


async def complete(system: str, user: str) -> LlmResult:
    """发一次非流式 chat/completions。

    返回值永远不抛异常 —— 调用方（队伍评价接口）不该因为 LLM 不可用而 500。
    """
    settings = get_settings()
    if not settings.llm_configured:
        return LlmResult(error="LLM 未配置（缺少 TELECOM_BASE_URL / TELECOM_API_KEY）")

    last_error: str | None = None
    for model in _models():
        result = await _request(model, system, user)
        if result.ok:
            return result
        last_error = result.error
        logger.warning("LLM 调用失败（model=%s）：%s", model, result.error)

    return LlmResult(error=last_error or "LLM 调用失败")


async def stream(system: str, user: str) -> AsyncIterator[LlmChunk]:
    """流式调用：边生成边 yield 增量。

    先试主模型；**在还没吐出任何正文前**失败就换备用模型重试一次。
    一旦已有正文，中途失败就不再重试（避免重复/错乱），直接 yield 一个 error。
    调用方（SSE 接口）据此决定是继续还是提示。
    """
    settings = get_settings()
    if not settings.llm_configured:
        yield LlmChunk(kind="error", text="LLM 未配置（缺少 TELECOM_BASE_URL / TELECOM_API_KEY）")
        return

    models = _models()
    for index, model in enumerate(models):
        produced = False
        failed = False
        async for chunk in _stream_model(model, system, user):
            if chunk.kind == "error":
                # 已经吐过正文就不再换模型重试；否则留给下一个模型
                if produced or index == len(models) - 1:
                    yield chunk
                    return
                logger.warning("LLM 流式失败（model=%s）：%s，尝试备用模型", model, chunk.text)
                failed = True
                break
            produced = True
            yield chunk
        if not failed:
            return  # 正常结束（或已把 error 交给调用方）


async def _stream_model(model: str, system: str, user: str) -> AsyncIterator[LlmChunk]:
    """对单个模型发一次流式请求，逐条解析 SSE。"""
    settings = get_settings()
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = _payload(model, system, user, stream=True)
    # 读超时放宽到「多久没有新字节」的粒度：推理模型可能先思考十几秒才出正文。
    timeout = httpx.Timeout(settings.llm_timeout_seconds, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=_headers()) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")[:200]
                    yield LlmChunk(kind="error", text=f"HTTP {response.status_code}：{body}")
                    return
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        yield LlmChunk(kind="reasoning", text=reasoning, model=model)
                    content = delta.get("content")
                    if content:
                        yield LlmChunk(kind="content", text=content, model=model)
    except httpx.HTTPError as exc:
        yield LlmChunk(kind="error", text=f"{type(exc).__name__}: {exc}")
    except json.JSONDecodeError:
        yield LlmChunk(kind="error", text="响应不是合法 JSON")


async def _request(model: str, system: str, user: str) -> LlmResult:
    settings = get_settings()
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = _payload(model, system, user, stream=False)

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        return LlmResult(error=f"HTTP {exc.response.status_code}")
    except httpx.HTTPError as exc:
        return LlmResult(error=f"{type(exc).__name__}: {exc}")
    except json.JSONDecodeError:
        return LlmResult(error="响应不是合法 JSON")

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return LlmResult(error="响应结构不符合 chat/completions 约定")

    text = (content or "").strip()
    if not text:
        return LlmResult(error="模型返回了空内容")
    return LlmResult(text=text, model=model)
