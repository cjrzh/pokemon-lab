/**
 * 对战使用率排行 API：类型定义与请求函数（公开只读）。
 *
 * 后端契约见 services/api/app/schemas/usage.py。
 * 数据来自 Smogon 月度统计快照，页面必须展示 `month` 与 `cutoff`。
 */

import { apiRequest } from '@/lib/apiClient'
import type { DoublesSpread, DoublesUsage } from '@/features/doubles/api'

/** 排行榜支持的四个格式（顺序即页面标签顺序）。 */
export type UsageFormat = 'bdsp' | 'swsh' | 'sv' | 'champions'

export const USAGE_FORMATS: readonly UsageFormat[] = ['bdsp', 'swsh', 'sv', 'champions']

export function isUsageFormat(value: unknown): value is UsageFormat {
  return typeof value === 'string' && (USAGE_FORMATS as readonly string[]).includes(value)
}

export interface UsageFormatInfo {
  key: UsageFormat
  label: string
  short_label: string
  game: string
  ruleset: string
  month: string
  cutoff: number
  points_kind: 'ev' | 'stat_points'
  battles: number
  note: string | null
  source_url: string | null
  /** 该格式的排行条目数 */
  entries: number
  /** 数据是否已导入本地库 */
  imported: boolean
}

export interface UsageRankingItem {
  showdown_name: string
  dex_number: number | null
  name_zh: string | null
  name_en: string | null
  types: string[]
  artwork_url: string | null
  artwork_fallback_url: string | null
  /** 96×96 小图标（本地缓存优先）。 */
  sprite_url?: string | null
  is_legendary: boolean
  is_mythical: boolean
  rank: number | null
  usage: number | null
  raw_count: number
  abilities: DoublesUsage[]
  items: DoublesUsage[]
  moves: DoublesUsage[]
  spread: DoublesSpread | null
}

export interface UsageRankingMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface UsageRankingResponse {
  formats: UsageFormatInfo[]
  format_key: string
  items: UsageRankingItem[]
  meta: UsageRankingMeta
  has_data: boolean
}

export interface UsageRankingParams {
  format: UsageFormat
  q?: string
  page?: number
  page_size?: number
}

export function fetchUsageRanking(
  params: UsageRankingParams,
  signal?: AbortSignal,
): Promise<UsageRankingResponse> {
  const search = new URLSearchParams({ format: params.format })
  if (params.q) search.set('q', params.q)
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  return apiRequest<UsageRankingResponse>(`/usage-ranking?${search.toString()}`, { signal })
}

/** 展示名：中文名优先，回落到 Showdown 显示名（不编造翻译）。 */
export function usageDisplayName(item: UsageRankingItem): string {
  return item.name_zh ?? item.name_en ?? item.showdown_name
}
