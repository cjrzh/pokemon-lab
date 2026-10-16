/**
 * 图鉴 API：类型定义与请求函数（公开只读接口）。
 *
 * 后端契约见 services/api/app/schemas/pokemon.py。
 */

import { apiRequest } from '@/lib/apiClient'

export interface PokemonSummary {
  dex_number: number
  name_en: string
  name_zh: string | null
  types: string[]
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
}

export interface PokemonDetail {
  dex_number: number
  name_en: string
  name_zh: string | null
  types: string[]
  stats: Record<string, number>
  abilities: PokemonAbility[]
  evolution: {
    chain_id?: string
    chain?: EvolutionNode
  }
  generation_introduced: number | null
  height_dm: number | null
  weight_hg: number | null
  source: 'pokeapi' | 'manual'
  source_label: string
  is_demo: boolean
  synced_at: string | null
}

export interface EvolutionNode {
  name: string
  dex: number
  evolves_to: EvolutionNode[]
}

export interface PokemonListParams {
  page?: number
  page_size?: number
  q?: string
  type?: string
  generation?: number
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
  const qs = search.toString()
  return apiRequest<PokemonListResponse>(`/pokemon${qs ? `?${qs}` : ''}`, { signal })
}

export function fetchPokemonDetail(
  dexNumber: number,
  signal?: AbortSignal,
): Promise<PokemonDetail> {
  return apiRequest<PokemonDetail>(`/pokemon/${dexNumber}`, { signal })
}
