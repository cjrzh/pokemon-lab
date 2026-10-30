/**
 * 双打配置的展示逻辑（纯函数，便于单测）。
 *
 * 把后端返回的「一坨统计」整理成「推荐配置 + 备选」两层：
 *   - 推荐配置取使用率最高的一组：性格、配点、特性、道具、招式；
 *   - 其余条目按使用率降序保留，供展开查看。
 * 不做任何「加权评分」之类的二次推断 —— 排名与使用率就是数据源给的结论。
 */

import {
  DOUBLES_STAT_LABELS,
  pointsUnit,
  type DoublesFormatBlock,
  type DoublesProfile,
  type DoublesSpread,
  type DoublesUsage,
  type PointsKind,
} from './api'

export interface RecommendedBuild {
  nature: DoublesSpread | null
  ability: DoublesUsage | null
  item: DoublesUsage | null
  moves: DoublesUsage[]
}

/** 从统计里挑出推荐配置：每类条目已由后端按使用率降序排列。 */
export function recommendedBuild(profile: DoublesProfile): RecommendedBuild {
  return {
    nature: profile.spreads[0] ?? null,
    ability: profile.abilities[0] ?? null,
    item: profile.items[0] ?? null,
    moves: profile.moves.slice(0, 6),
  }
}

/** `[252, 0, 4, 0, 0, 252]` → `[{label:'HP', value:252}, ...]`。 */
export function splitPoints(points: number[]): { label: string; value: number }[] {
  return DOUBLES_STAT_LABELS.map((label, index) => ({
    label,
    value: points[index] ?? 0,
  }))
}

/** 配点条形的满量程：EV 为 252，Champions 能力点为 32。 */
export function pointsScale(kind: PointsKind): number {
  return kind === 'stat_points' ? 32 : 252
}

/** 一行配点摘要，例如 `固执 · 252/4/0/0/0/252`。 */
export function spreadSummary(spread: DoublesSpread, kind: PointsKind): string {
  return `${spread.nature_label} · ${spread.points.join('/')} ${pointsUnit(kind)}`
}

/**
 * 该格式是否值得展示空态之外的提示：
 * 有格式数据但当前宝可梦缺席 →「该格式无统计数据」。
 */
export function formatHasProfiles(format: DoublesFormatBlock): boolean {
  return format.profiles.length > 0
}

/** 取该格式下使用率最高的形态作为默认显示。 */
export function defaultProfile(format: DoublesFormatBlock): DoublesProfile | null {
  return format.profiles[0] ?? null
}

/** 队友显示名：优先中文名，退回显示名的可读化处理。 */
export function teammateLabel(teammate: {
  name_zh: string | null
  showdown_name: string
}): string {
  if (teammate.name_zh) return teammate.name_zh
  return teammate.showdown_name
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}
