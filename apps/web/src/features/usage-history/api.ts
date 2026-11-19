/**
 * Smogon 历史使用率 API。
 *
 * 与现有的 `/usage-ranking`（四固定格式快照）不同，这里查询「任意月份 ×
 * 格式 × 等级线」的历史数据，数据由同步按钮按需抓取。
 */

import { apiRequest } from '@/lib/apiClient'

export const CUTOFF_OPTIONS = [1500, 1630, 1760] as const

export interface UsageFormatInfo {
  format_id: string
  label: string
  game: string
  ruleset: string
  kind: string
  /** 库里已同步的月份数；0 表示还没数据 */
  months: number
}

export interface UsageEntry {
  rank: number
  showdown_name: string
  dex_number: number | null
  name_zh: string | null
  name_en: string | null
  types: string[]
  sprite_url: string | null
  usage: number
  raw_count: number
}

export interface UsageHistoryQuery {
  format_id: string
  format_label: string
  game: string
  ruleset: string
  month: string
  cutoff: number
  battles: number
  /** 该 (格式, 月份, 等级线) 是否已有快照；false 表示还没同步。 */
  has_snapshot: boolean
  total: number
  page: number
  page_size: number
  total_pages: number
  items: UsageEntry[]
  months: string[]
  formats: UsageFormatInfo[]
  cutoffs: number[]
}

export interface UsageQueryParams {
  format?: string
  month?: string
  cutoff?: number
  q?: string
  page?: number
  page_size?: number
}

export function fetchUsageHistory(
  params: UsageQueryParams,
  signal?: AbortSignal,
): Promise<UsageHistoryQuery> {
  const search = new URLSearchParams()
  if (params.format) search.set('format', params.format)
  if (params.month) search.set('month', params.month)
  if (params.cutoff) search.set('cutoff', String(params.cutoff))
  if (params.q) search.set('q', params.q)
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  const qs = search.toString()
  return apiRequest<UsageHistoryQuery>(`/usage${qs ? `?${qs}` : ''}`, { signal })
}

export interface SyncRun {
  id: number
  status: 'running' | 'done' | 'error' | 'cancelled'
  total: number
  done: number
  created: number
  skipped: number
  failed: number
  current: string | null
  message: string | null
  scope: Record<string, unknown>
  started_at: string | null
  finished_at: string | null
}

export interface SyncPayload {
  months?: string[]
  format_ids?: string[]
  cutoffs?: number[]
  /** 只同步最近 N 个月（按钮默认用它） */
  recent_months?: number
}

export function startUsageSync(payload: SyncPayload): Promise<SyncRun> {
  return apiRequest<SyncRun>('/usage/sync', { method: 'POST', body: payload })
}

export function fetchSyncRun(runId: number, signal?: AbortSignal): Promise<SyncRun> {
  return apiRequest<SyncRun>(`/usage/sync/${runId}`, { signal })
}

export function fetchLatestSync(signal?: AbortSignal): Promise<SyncRun | null> {
  return apiRequest<SyncRun | null>('/usage/sync/latest', { signal })
}

export function cancelUsageSync(runId: number): Promise<SyncRun> {
  return apiRequest<SyncRun>(`/usage/sync/${runId}/cancel`, { method: 'POST' })
}
