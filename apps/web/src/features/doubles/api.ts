/**
 * 双打对战辅助 API：类型定义与请求函数。
 *
 * 后端契约见 services/api/app/schemas/doubles.py。
 * 数据来自 Smogon 公开月度统计，是历史快照；界面必须展示 `month` 与 `cutoff`。
 */

import { apiRequest } from '@/lib/apiClient'

export type PointsKind = 'ev' | 'stat_points'

export interface DoublesUsage {
  slug: string
  name: string
  /** Showdown 英文名（生成导出代码用；缺失时为 null）。 */
  name_en: string | null
  /** 招式属性（只有招式条目有值，如 `fire`）。 */
  type?: string | null
  /** 道具图标（只有道具条目有值；本地缓存优先，缺失为 null）。 */
  icon_url?: string | null
  pct: number
}

export interface DoublesSpread {
  nature: string
  nature_label: string
  points: number[]
  pct: number
}

export interface DoublesIVSuggestion {
  ivs: Record<string, number>
  reasons: string[]
  inferred: boolean
}

export interface DoublesTeammate {
  showdown_name: string
  dex_number: number | null
  name_zh: string | null
  pct: number
}

export interface DoublesTeraType {
  type: string
  pct: number
}

export interface DoublesProfile {
  showdown_name: string
  rank: number | null
  usage: number | null
  raw_count: number
  abilities: DoublesUsage[]
  items: DoublesUsage[]
  moves: DoublesUsage[]
  teammates: DoublesTeammate[]
  tera_types: DoublesTeraType[]
  spreads: DoublesSpread[]
  ivs: DoublesIVSuggestion | null
}

export interface DoublesFormatBlock {
  key: string
  label: string
  short_label: string
  game: string
  ruleset: string
  month: string
  cutoff: number
  points_kind: PointsKind
  battles: number
  /** 导出 Showdown 代码时使用的交易命令前缀（如 !tradeSV）；冠军为 null。 */
  trade_prefix: string | null
  /** 导出代码的默认等级（VGC 50，BDSP 双打 OU 100）。 */
  default_level: number
  note: string | null
  source_url: string | null
  imported_at: string | null
  profiles: DoublesProfile[]
}

export interface DoublesResponse {
  dex_number: number
  formats: DoublesFormatBlock[]
  has_data: boolean
}

export function fetchDoubles(
  dexNumber: number,
  signal?: AbortSignal,
): Promise<DoublesResponse> {
  return apiRequest<DoublesResponse>(`/pokemon/${dexNumber}/doubles`, { signal })
}

/** 该格式是否使用能力点（Champions）而非 EV/IV。 */
export function usesStatPoints(format: DoublesFormatBlock): boolean {
  return format.points_kind === 'stat_points'
}

/** 双打界面里的六项顺序（与后端 `stat_keys` 一致）。 */
export const DOUBLES_STAT_LABELS = ['HP', '攻击', '防御', '特攻', '特防', '速度'] as const

/** 配点展示单位：旧世代是 EV，Champions 是能力点。 */
export function pointsUnit(kind: PointsKind): string {
  return kind === 'stat_points' ? '点' : 'EV'
}

/** 百分比展示：统计里最小的值也会出现（0.0001%），保留两位小数足够。 */
export function formatPct(value: number): string {
  if (value >= 10) return `${value.toFixed(1)}%`
  if (value >= 1) return `${value.toFixed(2)}%`
  return `${value.toFixed(3)}%`
}

/** 月份 `2026-04` → `2026 年 4 月`；格式不符时原样返回。 */
export function formatMonth(month: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(month)
  if (!match) return month
  return `${match[1]} 年 ${Number(match[2])} 月`
}
