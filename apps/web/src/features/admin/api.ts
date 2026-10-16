/**
 * 后台管理 API：同步状态、触发同步、内容编辑、操作日志。
 *
 * 这些接口只有 /admin 页面使用；公开浏览页（图鉴等）一律不引用本文件 ——
 * 「前端仅浏览、编辑集中在后台」的边界在前端目录结构上就是可见的。
 */

import { apiRequest } from '@/lib/apiClient'

export interface SyncStatus {
  total: number
  from_pokeapi: number
  from_manual: number
  demo: number
  last_synced_at: string | null
  default_range: { start: number; end: number }
  expected_in_range: number
  coverage: number | null
}

export interface SyncResult {
  synced_count: number
  skipped_manual: number[]
  failed: Record<string, string>
  summary: string
}

export interface AdminOpLog {
  id: number
  action: string
  target: string | null
  detail: string | null
  operator: string
  created_at: string
}

export interface PokemonEditPayload {
  name_en?: string
  name_zh?: string
  types?: string[]
  stats?: Record<string, number>
  abilities?: { name: string; zh: string | null; is_hidden: boolean }[]
  evolution?: Record<string, unknown>
  generation_introduced?: number
  height_dm?: number
  weight_hg?: number
  is_demo?: boolean
}

export function fetchSyncStatus(signal?: AbortSignal): Promise<SyncStatus> {
  return apiRequest<SyncStatus>('/admin/pokemon/sync/status', { signal })
}

export function triggerSync(
  payload: { start: number; end: number; force?: boolean },
  signal?: AbortSignal,
): Promise<SyncResult> {
  return apiRequest<SyncResult>('/admin/pokemon/sync', { method: 'POST', body: payload, signal })
}

export function fetchOpLogs(signal?: AbortSignal): Promise<{ items: AdminOpLog[] }> {
  return apiRequest<{ items: AdminOpLog[] }>('/admin/ops', { signal })
}

export function editPokemon(
  dexNumber: number,
  payload: PokemonEditPayload,
  signal?: AbortSignal,
): Promise<unknown> {
  return apiRequest(`/admin/pokemon/${dexNumber}`, { method: 'PUT', body: payload, signal })
}

export function createPokemon(
  payload: PokemonEditPayload & { dex_number: number },
  signal?: AbortSignal,
): Promise<unknown> {
  return apiRequest('/admin/pokemon', { method: 'POST', body: payload, signal })
}
