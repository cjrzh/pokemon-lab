import { describe, expect, it } from 'vitest'

import { pageItems, pageRange } from './pagination'

describe('pageItems', () => {
  it('页数不多时全部列出', () => {
    expect(pageItems(1, 1)).toEqual([1])
    expect(pageItems(2, 5)).toEqual([1, 2, 3, 4, 5])
  })

  it('页数很多时保留首末页并用省略号收窄中间', () => {
    expect(pageItems(1, 20)).toEqual([1, 2, 3, 'ellipsis', 20])
    expect(pageItems(10, 20)).toEqual([1, 'ellipsis', 8, 9, 10, 11, 12, 'ellipsis', 20])
    expect(pageItems(20, 20)).toEqual([1, 'ellipsis', 18, 19, 20])
  })

  it('中间范围靠近首尾时不产生重复页码', () => {
    const items = pageItems(2, 20)
    expect(items).toEqual([1, 2, 3, 4, 'ellipsis', 20])
    expect(new Set(items.filter((item) => item !== 'ellipsis')).size).toBe(
      items.filter((item) => item !== 'ellipsis').length,
    )
  })
})

describe('pageRange', () => {
  it('计算当前页的条目区间', () => {
    expect(pageRange(1, 24, 100)).toEqual([1, 24])
    expect(pageRange(2, 24, 100)).toEqual([25, 48])
    expect(pageRange(5, 24, 100)).toEqual([97, 100])
  })

  it('空结果返回 0–0', () => {
    expect(pageRange(1, 24, 0)).toEqual([0, 0])
  })
})
