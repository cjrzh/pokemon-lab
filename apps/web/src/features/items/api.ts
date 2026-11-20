/**
 * 道具百科 API：类型定义与请求函数（公开只读）。
 *
 * 后端契约见 services/api/app/schemas/items.py。
 * 数据来自 PokéAPI `/item/{slug}`，覆盖双打统计里出现的道具。
 */

import { apiRequest } from '@/lib/apiClient'

export interface ItemSummary {
  name: string
  zh: string | null
  name_en: string | null
  category: string | null
  category_zh: string | null
  effect_en: string | null
  /** 中文说明（项目自译，非官方文本）。 */
  effect_zh: string | null
  /** 中文说明来源：project（项目自译） */
  effect_zh_source: string | null
  cost: number | null
  icon_url: string | null
}

export interface ItemCategoryOption {
  value: string
  label: string
  count: number
}

export interface ItemListMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface ItemListResponse {
  items: ItemSummary[]
  meta: ItemListMeta
  categories: ItemCategoryOption[]
}

export interface ItemListParams {
  page?: number
  page_size?: number
  q?: string
  category?: string
}

export function fetchItemList(
  params: ItemListParams,
  signal?: AbortSignal,
): Promise<ItemListResponse> {
  const search = new URLSearchParams()
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  if (params.q) search.set('q', params.q)
  if (params.category) search.set('category', params.category)
  const qs = search.toString()
  return apiRequest<ItemListResponse>(`/items${qs ? `?${qs}` : ''}`, { signal })
}

/** 展示名：中文名优先，缺失时回落到英文名或 slug。 */
export function itemDisplayName(item: ItemSummary): string {
  return item.zh ?? item.name_en ?? item.name
}

/**
 * 跳转到道具页并定位到某个道具。
 *
 * 道具没有独立详情页（列表页就是「具体页面」）：用 `q` 带上名称，
 * 目标页会把它回填进搜索框并只显示匹配项。后端 `q` 同时匹配
 * name / name_en / 中文名，所以中文名与 slug 都能命中。
 */
export function itemDetailLink(name: string): string {
  const params = new URLSearchParams({ q: name })
  return `/items?${params.toString()}`
}
