import { describe, expect, it } from 'vitest'

import type { PokemonMove } from '@/features/dex/api'
import {
  countByMethod,
  defaultVersionGroup,
  filterMoves,
  nextSort,
  sortMoves,
  totalMoves,
  uniqueMoveCount,
} from '@/features/dex/moves'

describe('moves helpers', () => {
  const group = {
    version_group: 'scarlet-violet',
    label: '朱／紫',
    methods: [
      {
        method: 'level-up',
        label: '升级',
        moves: [
          { name: 'tackle', zh: '撞击', level: 1, type: 'normal', damage_class: 'physical', damage_class_zh: '物理', power: 40, accuracy: 100, pp: 35, description_zh: null },
          { name: 'growl', zh: '叫声', level: 1, type: 'normal', damage_class: 'status', damage_class_zh: '变化', power: null, accuracy: 100, pp: 40, description_zh: null },
        ],
      },
      {
        method: 'machine',
        label: '招式学习器',
        moves: [
          { name: 'protect', zh: '守住', level: 0, type: 'normal', damage_class: 'status', damage_class_zh: '变化', power: null, accuracy: null, pp: 10, description_zh: null },
        ],
      },
      {
        method: 'egg',
        label: '蛋招式',
        moves: [
          { name: 'petal-dance', zh: null, level: 0, type: 'grass', damage_class: 'special', damage_class_zh: '特殊', power: 120, accuracy: 100, pp: 10, description_zh: null },
        ],
      },
    ],
  }

  it('默认版本组优先使用后端标注', async () => {
    expect(
      defaultVersionGroup({
        default_version_group: 'scarlet-violet',
        version_groups: [group],
      }),
    ).toBe('scarlet-violet')
    expect(defaultVersionGroup({ default_version_group: null, version_groups: [] })).toBeNull()
  })

  it('按学习方式筛选', async () => {
    const sections = filterMoves(group, { method: 'machine' })
    expect(sections).toHaveLength(1)
    expect(sections[0].moves[0].name).toBe('protect')
  })

  it('按属性与名称筛选（中英文都能命中）', async () => {
    expect(filterMoves(group, { type: 'grass' })[0].moves[0].name).toBe('petal-dance')
    expect(filterMoves(group, { query: '撞' })[0].moves.map((m) => m.name)).toEqual(['tackle'])
    expect(filterMoves(group, { query: 'GROWL' })[0].moves.map((m) => m.name)).toEqual(['growl'])
  })

  it('统计：总数与去重数', async () => {
    expect(totalMoves(group)).toBe(4)
    expect(uniqueMoveCount(group)).toBe(4)
    expect(countByMethod(group)).toEqual({ 'level-up': 2, machine: 1, egg: 1 })
    expect(uniqueMoveCount(null)).toBe(0)
  })
})

describe('sortMoves / nextSort', () => {
  const mk = (over: Partial<PokemonMove>): PokemonMove => ({
    name: 'tackle',
    zh: '撞击',
    level: 1,
    type: 'normal',
    damage_class: 'physical',
    damage_class_zh: '物理',
    power: 40,
    accuracy: 100,
    pp: 35,
    description_zh: null,
    ...over,
  })

  const moves = [
    mk({ name: 'growl', zh: '叫声', level: 1, type: 'normal', damage_class: 'status', damage_class_zh: '变化', power: null, accuracy: 100, pp: 40 }),
    mk({ name: 'tackle', zh: '撞击', level: 1, power: 40, pp: 35 }),
    mk({ name: 'vine-whip', zh: '藤鞭', level: 3, type: 'grass', power: 45, accuracy: 100, pp: 25 }),
    mk({ name: 'solar-beam', zh: '日光束', level: 36, type: 'grass', damage_class: 'special', damage_class_zh: '特殊', power: 120, accuracy: 100, pp: 10 }),
  ]

  it('点击表头：升序 → 降序 → 取消', async () => {
    const asc = nextSort(null, 'power')
    expect(asc).toEqual({ key: 'power', direction: 'asc' })
    const desc = nextSort(asc, 'power')
    expect(desc).toEqual({ key: 'power', direction: 'desc' })
    expect(nextSort(desc, 'power')).toBeNull()
  })

  it('切换到另一列时从升序开始', async () => {
    expect(nextSort({ key: 'power', direction: 'desc' }, 'pp')).toEqual({
      key: 'pp',
      direction: 'asc',
    })
  })

  it('按威力升序/降序：空值（变化招式）始终排在最后', async () => {
    const asc = sortMoves(moves, { key: 'power', direction: 'asc' })
    expect(asc.map((m) => m.name)).toEqual(['tackle', 'vine-whip', 'solar-beam', 'growl'])

    const desc = sortMoves(moves, { key: 'power', direction: 'desc' })
    expect(desc.map((m) => m.name)).toEqual(['solar-beam', 'vine-whip', 'tackle', 'growl'])
  })

  it('按等级排序', async () => {
    const desc = sortMoves(moves, { key: 'level', direction: 'desc' })
    expect(desc.map((m) => m.level)).toEqual([36, 3, 1, 1])
  })

  it('按招式中文名排序，同值时保持稳定', async () => {
    const sorted = sortMoves(moves, { key: 'name', direction: 'asc' })
    expect(sorted.map((m) => m.zh)).toEqual(['叫声', '日光束', '藤鞭', '撞击'])
  })

  it('按属性 / 分类排序', async () => {
    const byType = sortMoves(moves, { key: 'type', direction: 'asc' })
    expect(byType[0].type).toBe('grass')
    expect(byType.at(-1)?.type).toBe('normal')

    const byClass = sortMoves(moves, { key: 'damageClass', direction: 'asc' })
    // 中文按拼音排序：变化(bian) < 特殊(te) < 物理(wu)
    expect(byClass.map((m) => m.damage_class_zh)).toEqual([
      '变化', '特殊', '物理', '物理',
    ])
  })

  it('sort 为 null 时保持默认顺序且不修改入参', async () => {
    const original = moves.map((m) => m.name)
    const result = sortMoves(moves, null)
    expect(result.map((m) => m.name)).toEqual(original)
    expect(moves.map((m) => m.name)).toEqual(original)
    expect(result).not.toBe(moves)
  })
})

describe('flattenMoveSections（「全部」合并视图）', () => {
  const mk = (over: Partial<PokemonMove>): PokemonMove => ({
    name: 'tackle',
    zh: '撞击',
    level: 0,
    type: 'normal',
    damage_class: 'physical',
    damage_class_zh: '物理',
    power: 40,
    accuracy: 100,
    pp: 35,
    description_zh: null,
    ...over,
  })

  const sections = [
    {
      method: 'level-up',
      label: '升级',
      moves: [mk({ name: 'tackle', level: 1 }), mk({ name: 'growl', zh: '叫声', level: 1 })],
    },
    {
      method: 'machine',
      label: '招式学习器',
      moves: [mk({ name: 'protect', zh: '守住', power: null }), mk({ name: 'tackle', level: 0 })],
    },
    {
      method: 'egg',
      label: '蛋招式',
      moves: [mk({ name: 'protect', zh: '守住', power: null })],
    },
  ]

  it('合并为单表并去重：同一招式只保留一行', async () => {
    const { flattenMoveSections } = await import('@/features/dex/moves')
    const rows = flattenMoveSections(sections)
    expect(rows.map((r) => r.name)).toEqual(['tackle', 'growl', 'protect'])
  })

  it('保留该招式的全部学习方式，按固定顺序排列', async () => {
    const { flattenMoveSections } = await import('@/features/dex/moves')
    const rows = flattenMoveSections(sections)
    const tackle = rows.find((r) => r.name === 'tackle')!
    expect(tackle.learn_methods).toEqual(['level-up', 'machine'])
    const protect = rows.find((r) => r.name === 'protect')!
    expect(protect.learn_methods).toEqual(['machine', 'egg'])
  })

  it('同一招式有升级形态时保留等级', async () => {
    const { flattenMoveSections } = await import('@/features/dex/moves')
    const tackle = flattenMoveSections(sections).find((r) => r.name === 'tackle')!
    expect(tackle.level).toBe(1)
  })

  it('合并后的行数等于「全部」按钮的去重计数', async () => {
    const { flattenMoveSections, uniqueMoveCount } = await import('@/features/dex/moves')
    const group = {
      version_group: 'scarlet-violet',
      label: '朱／紫',
      methods: sections,
    }
    expect(flattenMoveSections(sections)).toHaveLength(uniqueMoveCount(group))
  })

  it('合并视图可以按学习方式列排序', async () => {
    const { flattenMoveSections, sortMoves } = await import('@/features/dex/moves')
    const rows = flattenMoveSections(sections)

    // 按该行第一个学习方式的短标签拼音排序：升级(sheng) < 学习器(xue)
    const asc = sortMoves(rows, { key: 'method', direction: 'asc' })
    expect(asc.map((r) => r.name)).toEqual(['tackle', 'growl', 'protect'])

    const desc = sortMoves(rows, { key: 'method', direction: 'desc' })
    expect(desc.map((r) => r.name)).toEqual(['protect', 'tackle', 'growl'])
  })
})
