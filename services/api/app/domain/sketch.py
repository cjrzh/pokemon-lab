"""图图犬「写生」的招式范围（纯函数，便于单测）。

图图犬（Smeargle, #235）的招式表里只有「写生」，但游戏里写生可以复制绝大多数
招式。PokéAPI 的 `moves_json` 只记录写生本身，所以建队页的「合法招式」如果直接
用它，就只剩一个选项 —— 这是「图图犬招式里没有技能」的原因。

本模块按 Pokémon Showdown 官方校验器（`sim/team-validator.ts`）的规则描述
可写生范围：

  - 招式必须在本版本组里可学（任意宝可梦能学会即可作为写生来源）；
  - 带 `nosketch` 标记的招式不能写生（暗黑洞、复活祈祷、晶光星群等）；
  - Z 招式与极巨化招式不能写生（本项目招式目录不收录这两类，无需额外处理）；
  - Gen 8 规则只允许写生第八代以前的招式；Gen 9 与 BDSP 允许写生当前版本的
    招式（Ruination 等第九代招式在 Gen 9 赛事里确实被写生使用过）。
    本地没有「招式世代」字段，因此按「本版本可学」近似 —— 对 Gen 9 / BDSP
    与官方口径一致；对剑盾会略宽松，但图图犬本身不在剑盾图鉴里，不影响实战。

范围之外的招式（如上面列出的 `nosketch` 招式）会被建队校验拒绝，并给出明确原因。
"""

from __future__ import annotations

#: 图图犬的图鉴编号。
SMEARGLE_DEX = 235

#: 写生这个招式本身。
SKETCH_MOVE = "sketch"

#: 不能通过写生获得的招式（来自 Showdown `data/moves.ts` 的 `flags.nosketch`）。
#: 名称是本地 slug（与 `move_ref.name` / `move_learner.move_name` 同口径）。
NON_SKETCHABLE: frozenset[str] = frozenset(
    {
        "dark-void",
        "hyperspace-fury",
        "revival-blessing",
        "tera-starstorm",
        "sketch",
        "struggle",
        # 第九代「XX扭矩」系列（源站标记 nosketch；本地目录若收录也会被排除）
        "blazing-torque",
        "combat-torque",
        "magical-torque",
        "noxious-torque",
    }
)


def is_smeargle(dex_number: int, legal_moves: set[str]) -> bool:
    """该编号是否能写生：图图犬，或招式表里确实带写生的记录。"""
    return dex_number == SMEARGLE_DEX or SKETCH_MOVE in legal_moves


def sketchable_moves(version_moves: set[str]) -> set[str]:
    """本版本可学招式 → 图图犬可写生的招式集合。"""
    return {move for move in version_moves if move not in NON_SKETCHABLE}
