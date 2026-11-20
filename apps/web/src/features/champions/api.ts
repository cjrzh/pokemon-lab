/**
 * 冠军图鉴（Pokémon Champions 双打）的展示辅助。
 *
 * 数据完全复用既有接口，不新增后端契约：
 *   - 榜单：`GET /usage-ranking?format=champions`（与「使用率」页同源）
 *   - 明细：`GET /pokemon/{dex}/doubles` 里 `key = champions` 的那一段
 *
 * 因此这里只放冠军专属的常量与格式化，避免把同一套规则在页面里再写一遍。
 * 统计是 Smogon 月度快照，界面必须展示月份与等级线（见 `datasetLabel`）。
 */

import {
  DOUBLES_STAT_LABELS,
  formatMonth,
  pointsUnit,
  type DoublesFormatBlock,
  type DoublesResponse,
  type DoublesSpread,
  type PointsKind,
} from '@/features/doubles/api'

/** 冠军格式在双打数据里的 key（后端 `doubles_formats.py` 同名）。 */
export const CHAMPIONS_FORMAT = 'champions'

/** 从双打响应里取冠军格式那一段；未导入数据时为 undefined。 */
export function championsBlock(
  data?: DoublesResponse | null,
): DoublesFormatBlock | undefined {
  return data?.formats.find((item) => item.key === CHAMPIONS_FORMAT)
}

/**
 * 配点 → `2 HP / 32 攻击 / 32 速度（点）`，只列非零项。
 *
 * Champions 是能力点（单项上限 32、无个体值），单位跟着 `points_kind` 走，
 * 不把能力点标成 EV。
 */
export function spreadText(spread: DoublesSpread, kind: PointsKind): string {
  const parts = spread.points
    .map((value, index) => ({ label: DOUBLES_STAT_LABELS[index] ?? '', value }))
    .filter((item) => item.value > 0)
    .map((item) => `${item.value} ${item.label}`)

  if (parts.length === 0) return '未分配'
  return `${parts.join(' / ')}（${pointsUnit(kind)}）`
}

/** 数据集标识：`VGC 2026 Reg M-C · 2026 年 9 月统计`。 */
export function datasetLabel(format: DoublesFormatBlock): string {
  return `${format.ruleset} · ${formatMonth(format.month)}统计`
}

/** 配点单位文案：能力点 / EV（冠军恒为能力点，保留函数以便复用）。 */
export function championPointsUnit(kind: PointsKind): string {
  return pointsUnit(kind)
}
