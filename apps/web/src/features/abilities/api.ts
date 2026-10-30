/**
 * 特性 API：类型、请求与评级工具。
 *
 * 后端契约见 services/api/app/schemas/abilities.py。
 * S 级特性在图鉴页需要标红加粗，所以列表与详情页共用同一份「S 级特性名集合」查询。
 */

import { apiRequest } from '@/lib/apiClient'

export type AbilityTier = 's' | 'normal'
export type RatingSource = 'llm' | 'manual'

export interface AbilityHolder {
  dex_number: number
  name_zh: string | null
  name_en: string
  types: string[]
  is_hidden: boolean
  is_legendary: boolean
  is_mythical: boolean
  /** 96×96 小图标（本地缓存优先）。 */
  sprite_url?: string | null
}

export interface AbilitySummary {
  name: string
  zh: string | null
  effect_zh: string | null
  tier: AbilityTier
  rating_source: RatingSource
  rating_note: string | null
  holder_count: number
}

export interface AbilityListMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
  s_tier_total: number
}

export interface AbilityListResponse {
  items: AbilitySummary[]
  meta: AbilityListMeta
}

export interface AbilityDetail {
  name: string
  zh: string | null
  effect_zh: string | null
  effect_en: string | null
  tier: AbilityTier
  rating_source: RatingSource
  rating_note: string | null
  holders: AbilityHolder[]
}

export interface AbilityListParams {
  page?: number
  page_size?: number
  q?: string
  tier?: AbilityTier
}

export function fetchAbilityList(
  params: AbilityListParams,
  signal?: AbortSignal,
): Promise<AbilityListResponse> {
  const search = new URLSearchParams()
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  if (params.q) search.set('q', params.q)
  if (params.tier) search.set('tier', params.tier)
  const qs = search.toString()
  return apiRequest<AbilityListResponse>(`/abilities${qs ? `?${qs}` : ''}`, { signal })
}

export function fetchAbilityDetail(
  name: string,
  signal?: AbortSignal,
): Promise<AbilityDetail> {
  return apiRequest<AbilityDetail>(`/abilities/${encodeURIComponent(name)}`, { signal })
}

/** 人工修改评级（仅后台使用，但放在同一模块避免重复类型）。 */
export function updateAbilityRating(
  name: string,
  payload: { tier: AbilityTier; note?: string | null },
): Promise<AbilityDetail> {
  return apiRequest<AbilityDetail>(`/admin/abilities/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: payload,
  })
}

/** 拉取全部 S 级特性名（图鉴页高亮用）。分页拉取，通常 1 页即可。 */
export async function fetchSTierAbilityNames(signal?: AbortSignal): Promise<Set<string>> {
  const first = await fetchAbilityList({ tier: 's', page: 1, page_size: 200 }, signal)
  const names = new Set(first.items.map((item) => item.name))
  for (let page = 2; page <= first.meta.total_pages; page += 1) {
    const next = await fetchAbilityList({ tier: 's', page, page_size: 200 }, signal)
    next.items.forEach((item) => names.add(item.name))
  }
  return names
}

export const TIER_LABEL: Record<AbilityTier, string> = {
  s: 'S 级',
  normal: '普通',
}

export const RATING_SOURCE_LABEL: Record<RatingSource, string> = {
  llm: 'LLM 预评',
  manual: '人工修改',
}

/**
 * 图鉴 / 列表里跳转到特性页的链接。
 *
 * 用英文 slug 作为 `q`：特性名唯一，能精确定位；`expand` 让目标行进入展开状态，
 * 再配合锚点滚动，避免落到列表顶部还要自己找。
 */
export function abilityDetailLink(name: string): string {
  const params = new URLSearchParams({ q: name, expand: name })
  return `/abilities?${params.toString()}`
}
