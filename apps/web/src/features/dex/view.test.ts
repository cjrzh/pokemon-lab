/**
 * 视图偏好纯函数测试。
 */

import { describe, expect, it } from 'vitest'

import {
  DEFAULT_DENSITY,
  DEFAULT_SORT,
  DEFAULT_VIEW,
  GRID_CLASSES,
  nextSort,
  pageSizeFor,
  parsePrefs,
  shiftDensity,
} from './view'

describe('parsePrefs', () => {
  it('空值与损坏的 JSON 回落到默认值', () => {
    expect(parsePrefs(null)).toEqual({
      view: DEFAULT_VIEW,
      density: DEFAULT_DENSITY,
      listSize: 50,
      sort: DEFAULT_SORT,
    })
    expect(parsePrefs('{oops')).toEqual({
      view: DEFAULT_VIEW,
      density: DEFAULT_DENSITY,
      listSize: 50,
      sort: DEFAULT_SORT,
    })
    expect(parsePrefs('null')).toEqual({
      view: DEFAULT_VIEW,
      density: DEFAULT_DENSITY,
      listSize: 50,
      sort: DEFAULT_SORT,
    })
  })

  it('只接受合法枚举，其它值逐项回落', () => {
    expect(parsePrefs('{"view":"list","density":"compact"}')).toEqual({
      view: 'list',
      density: 'compact',
      listSize: 50,
      sort: DEFAULT_SORT,
    })
    expect(parsePrefs('{"view":"grid","density":"huge"}')).toEqual({
      view: DEFAULT_VIEW,
      density: DEFAULT_DENSITY,
      listSize: 50,
      sort: DEFAULT_SORT,
    })
  })

  it('保留合法的排序，非法排序回落编号升序', () => {
    expect(parsePrefs('{"sort":"total_stats"}').sort).toBe('total_stats')
    expect(parsePrefs('{"sort":"total_stats_asc"}').sort).toBe('total_stats_asc')
    expect(parsePrefs('{"sort":"random"}').sort).toBe(DEFAULT_SORT)
  })
})

describe('nextSort', () => {
  it('编号列在升 / 降序之间切换，从别的排序切过来先给升序', () => {
    expect(nextSort('dex', 'dex')).toBe('dex_desc')
    expect(nextSort('dex_desc', 'dex')).toBe('dex')
    expect(nextSort('total_stats', 'dex')).toBe('dex')
  })

  it('种族值列在降 / 升序之间切换，从别的排序切过来先给降序', () => {
    expect(nextSort('dex', 'total_stats')).toBe('total_stats')
    expect(nextSort('total_stats', 'total_stats')).toBe('total_stats_asc')
    expect(nextSort('total_stats_asc', 'total_stats')).toBe('total_stats')
  })
})

describe('shiftDensity', () => {
  it('在三档之间移动，到边界保持不变', () => {
    expect(shiftDensity('normal', -1)).toBe('compact')
    expect(shiftDensity('normal', 1)).toBe('large')
    expect(shiftDensity('compact', -1)).toBe('compact')
    expect(shiftDensity('large', 1)).toBe('large')
  })
})

describe('pageSizeFor', () => {
  it('列表模式用选定的 25 / 50 / 100 / 200', () => {
    expect(pageSizeFor('list', 'compact', 25)).toBe(25)
    expect(pageSizeFor('list', 'normal', 50)).toBe(50)
    expect(pageSizeFor('list', 'normal', 100)).toBe(100)
    expect(pageSizeFor('list', 'normal', 200)).toBe(200)
  })

  it('列表条数非法时回落到 50', () => {
    expect(pageSizeFor('list', 'normal', 33)).toBe(50)
  })

  it('卡片密度决定 48 / 24 / 18（列表条数不生效）', () => {
    expect(pageSizeFor('card', 'compact', 200)).toBe(48)
    expect(pageSizeFor('card', 'normal', 200)).toBe(24)
    expect(pageSizeFor('card', 'large', 200)).toBe(18)
  })
})

describe('parsePrefs listSize', () => {
  it('保留合法的列表条数，非法值回落 50', () => {
    expect(parsePrefs('{"listSize":200}').listSize).toBe(200)
    expect(parsePrefs('{"listSize":999}').listSize).toBe(50)
    expect(parsePrefs(null).listSize).toBe(50)
  })
})

describe('GRID_CLASSES', () => {
  it('紧凑模式在宽屏比标准模式列数更多', () => {
    expect(GRID_CLASSES.compact).toContain('xl:grid-cols-8')
    expect(GRID_CLASSES.normal).toContain('xl:grid-cols-5')
    expect(GRID_CLASSES.large).toContain('lg:grid-cols-3')
  })
})
