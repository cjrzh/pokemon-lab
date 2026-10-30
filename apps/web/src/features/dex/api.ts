/**
 * 图鉴 API：类型定义与请求函数（公开只读接口）。
 *
 * 后端契约见 services/api/app/schemas/pokemon.py。
 */

import { apiRequest } from '@/lib/apiClient'

import type { DexSort } from './view'

export interface PokemonListAbility {
  name: string
  zh: string | null
  is_hidden: boolean
  is_s_tier: boolean
}

export interface PokemonSummary {
  dex_number: number
  name_en: string
  name_zh: string | null
  name_ja: string | null
  types: string[]
  /** 六项种族值（列表模式按项展示）。 */
  stats: Record<string, number>
  total_stats: number | null
  artwork_url: string | null
  artwork_fallback_url: string | null
  /** 96×96 小图标（本地缓存优先）；列表模式与特性页使用。 */
  sprite_url?: string | null
  is_legendary: boolean
  is_mythical: boolean
  abilities: PokemonListAbility[]
  is_demo: boolean
}

export interface PokemonListMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface PokemonListResponse {
  items: PokemonSummary[]
  meta: PokemonListMeta
}

export interface PokemonAbility {
  name: string
  zh: string | null
  is_hidden: boolean
  effect_zh: string | null
  effect_en: string | null
  tier: 's' | 'normal'
  is_s_tier: boolean
}

export interface PokemonMove {
  name: string
  zh: string | null
  level: number
  type: string | null
  damage_class: string | null
  damage_class_zh: string | null
  power: number | null
  accuracy: number | null
  pp: number | null
  description_zh: string | null
}

/** 一个版本组下的一种学习方式（升级 / 学习器 / 蛋招式 / 教学 …）。 */
export interface PokemonMoveMethod {
  method: string
  label: string
  moves: PokemonMove[]
}

export interface PokemonMoveVersionGroup {
  version_group: string
  label: string
  methods: PokemonMoveMethod[]
}

/** 全部招式：按版本组分组，组内再按学习方式分组。 */
export interface PokemonMoves {
  default_version_group: string | null
  version_groups: PokemonMoveVersionGroup[]
}

export interface EvolutionNode {
  name: string
  dex: number
  zh: string | null
  detail: string | null
  evolves_to: EvolutionNode[]
}

export interface PokemonNeighbor {
  dex_number: number
  name_zh: string | null
  name_en: string
}

export interface PokemonDetail {
  dex_number: number
  name_en: string
  name_zh: string | null
  name_ja: string | null
  types: string[]
  stats: Record<string, number>
  total_stats: number | null
  abilities: PokemonAbility[]
  evolution: {
    chain_id?: string
    chain?: EvolutionNode
  }
  moves: PokemonMoves

  genus_zh: string | null
  genus_en: string | null
  flavor_zh: string | null
  flavor_en: string | null
  flavor_zh_source: 'pokeapi' | 'project' | null
  genus_zh_source: 'pokeapi' | 'project' | null
  artwork_url: string | null
  artwork_fallback_url: string | null
  sprite_url: string | null
  is_legendary: boolean
  is_mythical: boolean
  is_baby: boolean
  gender_rate: number | null
  capture_rate: number | null
  base_happiness: number | null
  hatch_counter: number | null
  growth_rate: string | null
  habitat: string | null
  color: string | null
  shape: string | null
  egg_groups: string[]

  generation_introduced: number | null
  height_dm: number | null
  weight_hg: number | null
  prev: PokemonNeighbor | null
  next: PokemonNeighbor | null
  source: 'pokeapi' | 'manual'
  source_label: string
  is_demo: boolean
  synced_at: string | null
}

export interface PokemonListParams {
  page?: number
  page_size?: number
  q?: string
  type?: string
  generation?: number
  /** 排序：编号升 / 降序，种族值合计升 / 降序（后端在筛选之后排序）。 */
  sort?: DexSort
}

export function fetchPokemonList(
  params: PokemonListParams,
  signal?: AbortSignal,
): Promise<PokemonListResponse> {
  const search = new URLSearchParams()
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  if (params.q) search.set('q', params.q)
  if (params.type) search.set('type', params.type)
  if (params.generation) search.set('generation', String(params.generation))
  if (params.sort) search.set('sort', params.sort)
  const qs = search.toString()
  return apiRequest<PokemonListResponse>(`/pokemon${qs ? `?${qs}` : ''}`, { signal })
}

export function fetchPokemonDetail(
  dexNumber: number,
  signal?: AbortSignal,
): Promise<PokemonDetail> {
  return apiRequest<PokemonDetail>(`/pokemon/${dexNumber}`, { signal })
}

/**
 * 图片是相对路径（/media/...）时补上 API 服务的源；绝对地址原样返回。
 *
 * 注意只取 API 基址的 **origin**：VITE_API_BASE_URL 通常带 `/api/v1` 前缀，
 * 而 /media 挂在服务根路径下，直接拼接会得到 `/api/v1/media/...` 这种错误地址。
 */
export function resolveMediaUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined
  if (/^https?:\/\//.test(url)) return url
  const base = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
  if (!base) return url
  try {
    // 绝对地址 → 相对地址；`new URL` 需要 base，用当前站点兜底。
    const origin = new URL(base, 'http://localhost').origin
    return `${origin}${url.startsWith('/') ? url : `/${url}`}`
  } catch {
    return url
  }
}
