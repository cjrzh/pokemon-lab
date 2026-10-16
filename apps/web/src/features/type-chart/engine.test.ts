import { describe, expect, it } from 'vitest'

import { typeChartCases } from './data'
import { evaluate, formatMultiplier, multiplierTone, reverse } from './engine'
import { typeChart } from './data'

describe('type_engine evaluate（共享向量）', () => {
  // 只取 evaluate 类用例
  const evaluateCases = typeChartCases.filter((c) => c.kind === 'evaluate')

  it.each(evaluateCases.map((c) => [c.id, c] as const))(
    '%s',
    (_id, c) => {
      if (c.kind !== 'evaluate') return
      const actual = evaluate(c.attack, c.defense, typeChart)
      expect(actual).toBeCloseTo(c.expected, 9)
    },
  )
})

describe('type_engine reverse（共享向量）', () => {
  const reverseCases = typeChartCases.filter((c) => c.kind === 'reverse')

  it.each(reverseCases.map((c) => [c.id, c] as const))(
    '%s',
    (_id, c) => {
      if (c.kind !== 'reverse') return
      const actual = reverse(c.defense, typeChart)
      const expectedKeys = Object.keys(c.expected)
      // 非中性项必须恰好等于期望（多列少列都算错）
      expect([...actual.keys()].sort()).toEqual([...expectedKeys].sort())
      for (const [attack, multiplier] of Object.entries(c.expected)) {
        expect(actual.get(attack)).toBeCloseTo(multiplier, 9)
      }
    },
  )
})

describe('type_engine 单元', () => {
  it('单属性中性', () => {
    expect(evaluate('normal', ['grass'], typeChart)).toBe(1)
  })

  it('单属性免疫为 0', () => {
    expect(evaluate('normal', ['ghost'], typeChart)).toBe(0)
  })

  it('双属性 4 倍', () => {
    expect(evaluate('fire', ['grass', 'ice'], typeChart)).toBe(4)
  })

  it('双属性相消为中性', () => {
    expect(evaluate('fire', ['water', 'grass'], typeChart)).toBe(1)
  })

  it('免疫主导双属性（格斗→幽灵/一般）', () => {
    expect(evaluate('fighting', ['ghost', 'normal'], typeChart)).toBe(0)
  })

  it('未知进攻属性抛错', () => {
    expect(() => evaluate('shadow', ['normal'], typeChart)).toThrow('不在克制表中')
  })

  it('未知防守属性视为中性', () => {
    expect(evaluate('fire', ['normal'], typeChart)).toBe(1)
  })

  it('reverse 默认排除中性项', () => {
    const result = reverse(['fire'], typeChart)
    expect(result.has('fire')).toBe(true) // 0.5
    expect(result.has('normal')).toBe(false) // 1.0 被排除
  })

  it('reverse includeNeutral 返回全部 18 项', () => {
    const result = reverse(['fire'], typeChart, { includeNeutral: true })
    expect(result.size).toBe(18)
  })
})

describe('formatMultiplier', () => {
  it.each([
    [0, '无效（免疫）'],
    [0.25, '1/4×'],
    [0.5, '1/2×'],
    [1, '1×'],
    [2, '2×'],
    [4, '4×'],
  ])('倍率 %d → %s', (multiplier, label) => {
    expect(formatMultiplier(multiplier)).toBe(label)
  })
})

describe('multiplierTone', () => {
  it.each([
    [0, 'immune'],
    [0.25, 'resist'],
    [0.5, 'resist'],
    [1, 'neutral'],
    [2, 'effective'],
    [4, 'super'],
  ])('倍率 %d → %s', (multiplier, tone) => {
    expect(multiplierTone(multiplier)).toBe(tone)
  })
})
