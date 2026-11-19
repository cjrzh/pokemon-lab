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
  /** 对战分类键：normal / pseudo_legendary / restricted / sub_legendary / mythical / paradox。 */
  battle_class: BattleClass
  battle_class_zh: string
  abilities: PokemonListAbility[]
  is_demo: boolean
}

/** 对战分类（与后端 `domain/battle_class.py` 一致）。 */
export const BATTLE_CLASSES = [
  'normal',
  'pseudo_legendary',
  'restricted',
  'sub_legendary',
  'mythical',
  'paradox',
] as const
export type BattleClass = (typeof BATTLE_CLASSES)[number]

export const BATTLE_CLASS_LABEL: Record<BattleClass, string> = {
  normal: '普通',
  pseudo_legendary: '准神',
  restricted: '一级神',
  sub_legendary: '二级神',
  mythical: '幻兽',
  paradox: '悖谬',
}

/** 分类的简称（卡片徽章用，避免过长）。 */
export const BATTLE_CLASS_SHORT: Record<BattleClass, string> = {
  normal: '普通',
  pseudo_legendary: '准神',
  restricted: '一级神',
  sub_legendary: '二级神',
  mythical: '幻兽',
  paradox: '悖谬',
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
  /** 各分类数量（不受其它筛选条件影响）。 */
  battle_class_counts?: Partial<Record<BattleClass, number>>
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

/** 形态切换菜单项（默认形态与其它形态都在里面）。 */
export interface PokemonFormSummary {
  name: string
  label: string
  zh: string | null
  name_en: string | null
  types: string[]
  is_default: boolean
  sprite_url: string | null
}

/** 单个形态的完整信息（属性 / 种族值 / 特性 / 身高体重 / 立绘）。 */
export interface PokemonFormDetail {
  dex_number: number
  name: string
  label: string
  zh: string | null
  name_en: string | null
  types: string[]
  stats: Record<string, number>
  total_stats: number | null
  abilities: PokemonAbility[]
  height_dm: number | null
  weight_hg: number | null
  artwork_url: string | null
  artwork_fallback_url: string | null
  sprite_url: string | null
  is_default: boolean
}

/** 默认形态在 URL 里使用的伪 slug。 */
export const DEFAULT_FORM_NAME = 'default'

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

  /** 形态切换菜单；只有一个形态时为空数组。 */
  forms?: PokemonFormSummary[]

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
  /** 对战分类（与列表同一套规则）。 */
  battle_class: BattleClass
  battle_class_zh: string
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
  /** `true` 时 `q` 按前缀匹配（建队选择器用）；默认子串匹配。 */
  prefix?: boolean
  type?: string
  generation?: number
  /** 对战分类筛选。 */
  battle_class?: BattleClass
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
  if (params.prefix) search.set('prefix', 'true')
  if (params.type) search.set('type', params.type)
  if (params.generation) search.set('generation', String(params.generation))
  if (params.battle_class) search.set('battle_class', params.battle_class)
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

/** 某个形态的详情；默认形态传 `DEFAULT_FORM_NAME`。 */
export function fetchPokemonForm(
  dexNumber: number,
  formName: string,
  signal?: AbortSignal,
): Promise<PokemonFormDetail> {
  return apiRequest<PokemonFormDetail>(`/pokemon/${dexNumber}/forms/${formName}`, { signal })
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
