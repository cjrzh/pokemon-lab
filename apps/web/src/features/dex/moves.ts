/**
 * 招式数据的展示逻辑（纯函数）。
 *
 * 后端返回的结构是「版本组 → 学习方式 → 招式」，这里负责：
 *   - 选默认版本组（后端给的 default_version_group，缺失时回退第一个）；
 *   - 按学习方式筛选 / 按属性、分类、名称过滤；
 *   - 统计每个学习方式的招式数（用于标签上的计数）。
 *
 * 不在这里改倍率或补数值 —— 缺失字段保持 null，界面显示「—」。
 */

import type {
  PokemonMove,
  PokemonMoves,
  PokemonMoveVersionGroup,
} from './api'

/** 学习方式展示顺序（与后端 LEARN_METHOD_ORDER 一致）。 */
export const MOVE_METHOD_ORDER = [
  'level-up',
  'machine',
  'tutor',
  'egg',
  'train',
  'xd-purification',
  'stadium-surfing-pikachu',
] as const

/** 学习方式短标签（筛选按钮与「全部」视图的表格用）。 */
export const MOVE_METHOD_LABEL: Record<string, string> = {
  'level-up': '升级',
  machine: '学习器',
  tutor: '教学',
  egg: '蛋招式',
  train: '特殊',
  'xd-purification': '净化',
  'stadium-surfing-pikachu': '活动',
}

export const MOVE_METHOD_HINTS: Record<string, string> = {
  'level-up': '升级时自动学会',
  machine: '使用招式学习器（TM / HM）',
  tutor: '找招式教学者学习',
  egg: '通过孵蛋遗传',
  train: '特殊教学',
  'xd-purification': '《暗之旋风》净化后学会',
  'stadium-surfing-pikachu': '特殊活动',
}

/** 默认版本组：优先后端标注的 default，其次第一个有数据的版本组。 */
export function defaultVersionGroup(moves: PokemonMoves): string | null {
  if (moves.version_groups.length === 0) return null
  const preferred = moves.default_version_group
  if (preferred && moves.version_groups.some((g) => g.version_group === preferred)) {
    return preferred
  }
  return moves.version_groups[0].version_group
}

export function findVersionGroup(
  moves: PokemonMoves,
  key: string | null,
): PokemonMoveVersionGroup | null {
  if (!key) return moves.version_groups[0] ?? null
  return moves.version_groups.find((g) => g.version_group === key) ?? null
}

export function countByMethod(group: PokemonMoveVersionGroup | null): Record<string, number> {
  if (!group) return {}
  return Object.fromEntries(group.methods.map((m) => [m.method, m.moves.length]))
}

export interface MoveFilter {
  /** 学习方式；'all' 或空表示不筛选。 */
  method?: string
  /** 属性英文键；'all' 或空表示不筛选。 */
  type?: string
  /** 伤害类别：physical / special / status；'all' 或空表示不筛选。 */
  damageClass?: string
  /** 名称关键词（中/英文均可）。 */
  query?: string
}

/**
 * 在指定版本组内筛选招式。
 *
 * 返回值保留学习方式分组（选中单个方式时只返回该组），便于界面按方式分节展示。
 */
export function filterMoves(
  group: PokemonMoveVersionGroup | null,
  filter: MoveFilter = {},
): { method: string; label: string; moves: PokemonMove[] }[] {
  if (!group) return []
  const query = filter.query?.trim().toLowerCase() ?? ''
  const wantMethod = filter.method && filter.method !== 'all' ? filter.method : null
  const wantType = filter.type && filter.type !== 'all' ? filter.type : null
  const wantClass =
    filter.damageClass && filter.damageClass !== 'all' ? filter.damageClass : null

  return group.methods
    .filter((method) => !wantMethod || method.method === wantMethod)
    .map((method) => ({
      method: method.method,
      label: method.label,
      moves: method.moves.filter((move) => {
        if (wantType && move.type !== wantType) return false
        if (wantClass && move.damage_class !== wantClass) return false
        if (query) {
          const haystack = `${move.zh ?? ''} ${move.name}`.toLowerCase()
          if (!haystack.includes(query)) return false
        }
        return true
      }),
    }))
    .filter((section) => section.moves.length > 0)
}

/** 统计当前版本组的招式总数（去重前：同一招式可能同时是学习器和蛋招式）。 */
export function totalMoves(group: PokemonMoveVersionGroup | null): number {
  if (!group) return 0
  return group.methods.reduce((sum, m) => sum + m.moves.length, 0)
}

/** 唯一招式名数量（用于「共 N 个招式」文案，避免重复计数）。 */
export function uniqueMoveCount(group: PokemonMoveVersionGroup | null): number {
  if (!group) return 0
  const names = new Set<string>()
  for (const method of group.methods) {
    for (const move of method.moves) names.add(move.name)
  }
  return names.size
}

// ---------------------------------------------------------------------------
// 合并视图（选择「全部」时把各学习方式合成一张表）
// ---------------------------------------------------------------------------

/** 合并后的招式行：一条招式只出现一次，附带它所有的学习方式。 */
export interface MoveRow extends PokemonMove {
  /** 学习方式，按 MOVE_METHOD_ORDER 排序；同一招式可被多种方式学会。 */
  learn_methods: string[]
}

function methodRank(method: string): number {
  const index = MOVE_METHOD_ORDER.indexOf(method as (typeof MOVE_METHOD_ORDER)[number])
  return index === -1 ? MOVE_METHOD_ORDER.length : index
}

/**
 * 把按学习方式分组的招式合并为去重后的单表数据。
 *
 * 同一招式可能既是学习器又是蛋招式（数据里本来就重复列出），合并后只保留一行，
 * 并在 `learn_methods` 里列出全部方式 —— 行数与「全部 N」的去重计数一致。
 * 若同名招式同时存在升级招式与其他方式，保留升级招式那一条（带等级）。
 */
export function flattenMoveSections(
  sections: readonly { method: string; label: string; moves: readonly PokemonMove[] }[],
): MoveRow[] {
  const byName = new Map<string, MoveRow>()

  for (const section of sections) {
    for (const move of section.moves) {
      const existing = byName.get(move.name)
      if (!existing) {
        byName.set(move.name, { ...move, learn_methods: [section.method] })
        continue
      }
      if (!existing.learn_methods.includes(section.method)) {
        existing.learn_methods.push(section.method)
      }
      // 升级招式带有等级，优先展示它（同一名称理论上不会同时有多个等级）
      if (move.level > 0 && existing.level === 0) {
        const methods = existing.learn_methods
        Object.assign(existing, move, { learn_methods: methods })
      }
    }
  }

  return [...byName.values()].map((row) => ({
    ...row,
    learn_methods: [...row.learn_methods].sort((a, b) => methodRank(a) - methodRank(b)),
  }))
}

// ---------------------------------------------------------------------------
// 排序
// ---------------------------------------------------------------------------

/** 可排序的列。`level` / `method` 只在部分视图里可见。 */
export type MoveSortKey =
  | 'level'
  | 'name'
  | 'type'
  | 'damageClass'
  | 'power'
  | 'accuracy'
  | 'pp'
  | 'method'

export type SortDirection = 'asc' | 'desc'

export interface MoveSort {
  key: MoveSortKey
  direction: SortDirection
}

/**
 * 点击表头的状态迁移：同一列再点一次切换方向，换列则从升序开始。
 * 返回 null 表示取消排序（回到后端给的默认顺序），供「第三次点击」使用。
 */
export function nextSort(current: MoveSort | null, key: MoveSortKey): MoveSort | null {
  if (current?.key !== key) return { key, direction: 'asc' }
  return current.direction === 'asc' ? { key, direction: 'desc' } : null
}

/** 数值比较：空值（威力为「—」的变化招式等）无论升序降序都排在最后。 */
function compareNumbers(a: number | null, b: number | null, direction: SortDirection): number {
  if (a === null && b === null) return 0
  if (a === null) return 1
  if (b === null) return -1
  return direction === 'asc' ? a - b : b - a
}

/** 文本比较：空值排最后，中文按拼音/笔画习惯排序。 */
function compareText(
  a: string | null | undefined,
  b: string | null | undefined,
  direction: SortDirection,
): number {
  if (!a && !b) return 0
  if (!a) return 1
  if (!b) return -1
  const result = a.localeCompare(b, 'zh-Hans-CN')
  return direction === 'asc' ? result : -result
}

function textOf(move: PokemonMove, key: 'name' | 'type' | 'damageClass' | 'method'): string | null {
  switch (key) {
    case 'name':
      return move.zh ?? move.name
    case 'type':
      return move.type
    case 'damageClass':
      return move.damage_class_zh ?? move.damage_class
    case 'method': {
      // 同一招式可能同时是学习器与蛋招式；按第一种学习方式排序。
      const method = (move as MoveRow).learn_methods?.[0]
      return method ? (MOVE_METHOD_LABEL[method] ?? method) : null
    }
  }
}

function numberOf(move: PokemonMove, key: 'level' | 'power' | 'accuracy' | 'pp'): number | null {
  return move[key]
}

/**
 * 按指定列排序（不修改入参）。
 *
 * 排序是稳定的：同值时保留原始顺序（后端已按等级/名称排好），
 * 因此「按属性排序」时同一属性的招式仍保持等级顺序。
 */
export function sortMoves<T extends PokemonMove>(
  moves: readonly T[],
  sort: MoveSort | null,
): T[] {
  if (!sort) return [...moves]
  const { key, direction } = sort

  return [...moves].sort((a, b) => {
    if (key === 'name' || key === 'type' || key === 'damageClass' || key === 'method') {
      return compareText(textOf(a, key), textOf(b, key), direction)
    }
    return compareNumbers(numberOf(a, key), numberOf(b, key), direction)
  })
}

