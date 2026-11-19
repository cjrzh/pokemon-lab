"""Showdown 队伍文本导出（纯函数：结构化配置 → 文本，不访问网络 / 数据库）。

与 `showdown_parser.py` 互为逆操作。两个使用方：
  - `GET /teams/{id}/showdown`：给用户复制到 Showdown / 交换机器人；
  - LLM 提示词：把整队配置原样交给模型，比只给属性 + 招式名信息完整得多
    （道具、特性、性格、EV、IV、等级、太晶都影响结论）。

约定与 Showdown 自身一致：
  - 头部 `Nickname (Species) (M) @ Item`；无昵称时只写物种；
  - IV 全 31 时省略 IV 行；EV 为 0 的项省略；
  - 极巨化等级仅在剑盾输出，**始终写一行**（未设置按默认值 10），
    这样复制出去的代码能明确带上这个参数；
  - 超极巨化仅在剑盾输出，写成 `Gigantamax: Yes`，紧跟在 `Dynamax Level` 之后
    （两行的相对顺序与 Showdown 一致；解析按行识别，整体行序不影响导入）；
  - `Language:` 行只在非剑盾格式输出（剑盾导出 / 复制代码不需要语言标记）；
  - 交易前缀（`!tradeSV` 等）由调用方决定是否加，这里只渲染队伍本体。
"""

from __future__ import annotations

from collections.abc import Iterable

#: Showdown 六项短名（与前端 `showdown.ts` 一致）。
STAT_SHORT = ("HP", "Atk", "Def", "SpA", "SpD", "Spe")

#: 性格 slug → Showdown 显示名。未收录的按 Hardy 处理（与游戏中性性格一致）。
NATURE_EN = {
    "hardy": "Hardy", "lonely": "Lonely", "brave": "Brave", "adamant": "Adamant",
    "naughty": "Naughty", "bold": "Bold", "docile": "Docile", "relaxed": "Relaxed",
    "impish": "Impish", "lax": "Lax", "timid": "Timid", "hasty": "Hasty",
    "serious": "Serious", "jolly": "Jolly", "naive": "Naive", "modest": "Modest",
    "mild": "Mild", "quiet": "Quiet", "bashful": "Bashful", "rash": "Rash",
    "calm": "Calm", "gentle": "Gentle", "sassy": "Sassy", "careful": "Careful",
    "quirky": "Quirky",
}

_DEFAULT_LANGUAGE = "CHS"

#: Showdown 文本的行尾是两个空格（换行符在纯文本里不显眼，便于复制后阅读）。
_LINE_SUFFIX = "  "


def render_member(payload: dict, *, format_key: str, default_level: int = 50) -> str:
    """单只的 Showdown 文本。

    `payload` 是 `team_service.member_payload` 的结构（含 evs / ivs / moves …）。
    """
    lines: list[str] = []

    head = payload.get("nickname") or payload.get("showdown_name") or ""
    if payload.get("nickname"):
        head = f"{payload['nickname']} ({payload.get('showdown_name') or ''})"
    if payload.get("gender"):
        head += f" ({payload['gender']})"
    if payload.get("item"):
        head += f" @ {payload['item']}"
    lines.append(head)

    if payload.get("ability"):
        lines.append(f"Ability: {payload['ability']}")
    level = payload.get("level") or default_level or 50
    if level and level != 100:
        lines.append(f"Level: {level}")
    # 极巨化等级只在剑盾输出；未设置时按 Showdown 默认值 10 补齐 ——
    # 建队页复制出去的代码要明确带上这个参数（而不是靠隐式默认）。
    if format_key == "swsh":
        dynamax_level = payload.get("dynamax_level")
        if dynamax_level is None:
            dynamax_level = 10
        lines.append(f"Dynamax Level: {dynamax_level}")
        # 超极巨化同样只在剑盾输出（Showdown 的导出行是 `Gigantamax: Yes`）
        if payload.get("gigantamax"):
            lines.append("Gigantamax: Yes")
    if payload.get("shiny"):
        lines.append("Shiny: Yes")
    # 剑盾的复制 / 导出代码不带语言标记（其余格式仍保留，便于交换机器人识别）
    if format_key != "swsh":
        lines.append(f"Language: {payload.get('language') or _DEFAULT_LANGUAGE}")
    if format_key == "sv" and payload.get("tera_type"):
        lines.append(f"Tera Type: {payload['tera_type']}")

    evs = [
        f"{value} {STAT_SHORT[index]}"
        for index, value in enumerate(payload.get("evs") or [])
        if value > 0
    ]
    if evs:
        lines.append(f"EVs: {' / '.join(evs)}")

    lines.append(f"{NATURE_EN.get(payload.get('nature') or '', 'Hardy')} Nature")

    if payload.get("ivs"):
        ivs = [
            f"{value} {STAT_SHORT[index]}"
            for index, value in enumerate(payload["ivs"])
            if value != 31
        ]
        if ivs:
            lines.append(f"IVs: {' / '.join(ivs)}")

    for move in payload.get("moves") or []:
        if move:
            lines.append(f"- {move}")

    return "\n".join(f"{line}{_LINE_SUFFIX}" for line in lines)


def render_team(
    payloads: Iterable[dict], *, format_key: str, default_level: int = 50
) -> str:
    """整队 Showdown 文本（不含交易前缀；空行分隔每只）。"""
    return "\n\n".join(
        render_member(payload, format_key=format_key, default_level=default_level)
        for payload in payloads
    )
