"""出卷与错题集的请求 / 响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

#: 题干图片偏好的展示方式（接口统一返回两种，页面按需选择）。
QuizImageKind = Literal["artwork", "sprite"]


class QuizCreateRequest(BaseModel):
    """出卷配置。

    范围优先级：`generation` 与 `dex_from` / `dex_to` 可同时给（取交集）；
    都不给表示全国图鉴。
    """

    generation: int | None = Field(default=None, ge=1, le=9, description="只考该世代登场的")
    dex_from: int | None = Field(default=None, ge=1, le=10000, description="编号下限（含）")
    dex_to: int | None = Field(default=None, ge=1, le=10000, description="编号上限（含）")
    #: 题目数量；`mode="all"` 或为 None 时出全量。
    count: int | None = Field(default=None, ge=1, le=2000)
    mode: Literal["random", "all"] = Field(default="random", description="随机抽题 / 全量")

    @model_validator(mode="after")
    def _check_range(self) -> QuizCreateRequest:
        if self.dex_from is not None and self.dex_to is not None and self.dex_from > self.dex_to:
            raise ValueError("编号下限不能大于上限")
        return self


class QuizQuestionView(BaseModel):
    """一题（答题时发题干，结果页发答案）。"""

    position: int
    dex_number: int
    #: 图片（本地缓存优先）：立绘与小图标二选一展示，两者都给便于页面按尺寸用。
    artwork_url: str | None = None
    artwork_fallback_url: str | None = None
    sprite_url: str | None = None
    #: 仅结果页 / 已作答后返回
    name_zh: str | None = None
    name_en: str | None = None
    answer: str | None = None
    is_correct: bool | None = None
    #: 答错时给出正确答案（与 name_zh / name_en 相同，单独字段便于页面直接展示）
    expected_zh: str | None = None
    expected_en: str | None = None


class QuizSessionView(BaseModel):
    id: int
    total: int
    answered: int
    correct: int
    score: int = Field(description="正确率（0–100 整数，四舍五入）")
    finished: bool
    scope: dict = Field(default_factory=dict)
    created_at: str | None = None
    finished_at: str | None = None
    questions: list[QuizQuestionView] = []


class QuizCreateResponse(BaseModel):
    session: QuizSessionView


class QuizAnswerRequest(BaseModel):
    position: int = Field(ge=0, description="卷内题号（从 0 起）")
    answer: str = Field(default="", max_length=64)


class QuizAnswerResponse(BaseModel):
    correct: bool
    expected_zh: str | None
    expected_en: str
    #: 作答后的整卷状态（页面据此推进进度 / 显示结果）
    session: QuizSessionView


class QuizMistakeView(BaseModel):
    dex_number: int
    name_zh: str | None
    name_en: str
    sprite_url: str | None = None
    artwork_url: str | None = None
    wrong_count: int
    last_answer: str | None = None
    first_wrong_at: str | None = None
    last_wrong_at: str | None = None


class QuizMistakeListResponse(BaseModel):
    items: list[QuizMistakeView]
    total: int
