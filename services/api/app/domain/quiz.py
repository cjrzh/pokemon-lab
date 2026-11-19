"""出卷与判分规则（纯函数：无 IO、无随机源依赖、可单测）。

设计取舍：

  - **判分宽松但不猜**：只接受该宝可梦的中文名或英文名；忽略大小写、空格、
    连字符与标点（`Mr. Mime` / `mr mime` / `mr-mime` 视为同一个答案）。
    不做模糊匹配 —— 「差不多对」的自动判定比判错更伤，界面会给出正确答案。
  - **随机抽样由调用方传入 random.Random**，本模块不自己建随机源，
    这样测试可以固定种子复现。
  - **全量出卷按图鉴编号升序**；随机的顺序也是洗牌后的顺序，
    避免「前几只简单、后几只难」的规律被利用。
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass

#: 判分时要忽略的字符：空白、连字符（含各种破折号）、中英文标点、点号等。
_IGNORED = re.compile(r"[\s\-‐‑‒–—―_.·・'’\"“”()（）\[\]【】:：,，、/\\]+")


def normalize_answer(text: str) -> str:
    """答案归一化：全角转半角、统一小写、去掉分隔符与标点。

    只做「写法差异」的归一，不做同义词或错别字替换。
    """
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    return _IGNORED.sub("", folded)


def is_correct(answer: str, *, name_zh: str | None, name_en: str) -> bool:
    """答案是否命中该宝可梦（中文名或英文名任一即可）。"""
    normalized = normalize_answer(answer)
    if not normalized:
        return False
    accepted = {normalize_answer(name_en)}
    if name_zh:
        accepted.add(normalize_answer(name_zh))
    accepted.discard("")
    return normalized in accepted


def pick_dex_numbers(
    candidates: list[int], *, count: int | None, rng: random.Random
) -> list[int]:
    """从候选编号里抽题。

    `count` 为 None 或大于候选数时取全量。全量保持编号升序（可预期、便于核对）；
    随机抽样则洗牌后取前 N —— 顺序也是随机的，避免按编号递增的规律。
    """
    unique = sorted(set(candidates))
    if count is None or count >= len(unique):
        return unique
    if count <= 0:
        return []
    shuffled = unique[:]
    rng.shuffle(shuffled)
    return shuffled[:count]


@dataclass(frozen=True)
class AnswerVerdict:
    """一次作答的结果。"""

    correct: bool
    expected_zh: str | None
    expected_en: str
    #: 归一化后命中哪个名称（`zh` / `en`）；未答对时为 None。
    matched: str | None = None


def judge(answer: str, *, name_zh: str | None, name_en: str) -> AnswerVerdict:
    """判分并给出标准答案（答错时界面要展示）。"""
    normalized = normalize_answer(answer)
    if not normalized:
        return AnswerVerdict(False, name_zh, name_en)

    if name_zh and normalized == normalize_answer(name_zh):
        return AnswerVerdict(True, name_zh, name_en, matched="zh")
    if normalized == normalize_answer(name_en):
        return AnswerVerdict(True, name_zh, name_en, matched="en")
    return AnswerVerdict(False, name_zh, name_en)
