/**
 * 招式百科 API：类型定义与请求函数（公开只读）。
 *
 * 后端契约见 services/api/app/schemas/moves.py。
 * 招式名用 slug（`u-turn`）作为详情路由参数：与后端主键、图鉴详情页的链接一致。
 */

import { apiRequest } from '@/lib/apiClient'

export type DamageClass = 'physical' | 'special' | 'status'
export type MoveSort = 'name' | 'power' | 'accuracy' | 'pp' | 'learners'

export interface MoveSummary {
  name: string
  zh: string | null
  name_en: string | null
  type: string | null
  damage_class: DamageClass | null
  damage_class_zh: string | null
  power: number | null
  accuracy: number | null
  pp: number | null
  description_zh: string | null
  learner_count: number
  is_machine: boolean
}

export interface MoveListMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface MoveListResponse {
  items: MoveSummary[]
  meta: MoveListMeta
}

export interface MoveLearnEntry {
  method: string
  method_label: string
  level: number
}

export interface MoveLearnerPokemon {
  dex_number: number
  name_zh: string | null
  name_en: string
  types: string[]
  is_legendary: boolean
  is_mythical: boolean
  version_groups: Record<string, MoveLearnEntry[]>
  latest_methods: string[]
}

export interface MoveDetail extends MoveSummary {
  learners: MoveLearnerPokemon[]
  learners_by_version: Record<string, number>
  method_counts: Record<string, number>
  version_labels: Record<string, string>
  method_labels: Record<string, string>
}

export interface MoveListParams {
  page?: number
  page_size?: number
  q?: string
  type?: string
  damage_class?: DamageClass
  machine_only?: boolean
  sort?: MoveSort
}

export function fetchMoveList(
  params: MoveListParams,
  signal?: AbortSignal,
): Promise<MoveListResponse> {
  const search = new URLSearchParams()
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  if (params.q) search.set('q', params.q)
  if (params.type) search.set('type', params.type)
  if (params.damage_class) search.set('damage_class', params.damage_class)
  if (params.machine_only) search.set('machine_only', 'true')
  if (params.sort) search.set('sort', params.sort)
  const qs = search.toString()
  return apiRequest<MoveListResponse>(`/moves${qs ? `?${qs}` : ''}`, { signal })
}

export function fetchMoveDetail(name: string, signal?: AbortSignal): Promise<MoveDetail> {
  return apiRequest<MoveDetail>(`/moves/${encodeURIComponent(name)}`, { signal })
}

/** 图鉴详情页 / 列表里的招式链接（slug 为主键）。 */
export function moveDetailLink(name: string): string {
  return `/moves/${encodeURIComponent(name)}`
}

/** 伤害分类的展示标签（与后端 DAMAGE_CLASS_ZH 一致）。 */
export const DAMAGE_CLASS_LABEL: Record<DamageClass, string> = {
  physical: '物理',
  special: '特殊',
  status: '变化',
}

/** 伤害分类的强调色（列表里区分类别，不依赖属性色）。 */
export const DAMAGE_CLASS_TONE: Record<DamageClass, string> = {
  physical: 'bg-type-fighting/15 text-type-fighting',
  special: 'bg-type-psychic/15 text-type-psychic',
  status: 'bg-muted text-muted-foreground',
}

export const MOVE_SORT_LABEL: Record<MoveSort, string> = {
  name: '名称',
  power: '威力',
  accuracy: '命中',
  pp: 'PP',
  learners: '学习者',
}

/** 招式名展示：中文优先，逗号分隔的双语。 */
export function moveDisplayName(move: { zh: string | null; name_en: string | null; name: string }) {
  return move.zh ?? move.name_en ?? move.name
}
