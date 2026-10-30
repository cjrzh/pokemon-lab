/**
 * 双打配置展示逻辑的单测（纯函数）。
 */

import { describe, expect, it } from 'vitest'

import type { DoublesProfile } from './api'
import {
  pointsScale,
  recommendedBuild,
  spreadSummary,
  splitPoints,
  teammateLabel,
} from './recommendation'

const profile: DoublesProfile = {
  showdown_name: 'Incineroar',
  rank: 3,
  usage: 31.7,
  raw_count: 1005513,
  abilities: [
    { slug: 'intimidate', name: '威吓', name_en: null, pct: 99.6 },
    { slug: 'blaze', name: '猛火', name_en: null, pct: 0.4 },
  ],
  items: [{ slug: 'sitrus-berry', name: '文柚果', name_en: null, pct: 62.7 }],
  moves: [
    { slug: 'fake-out', name: '击掌奇袭', name_en: null, pct: 98.6 },
    { slug: 'parting-shot', name: '抛下狠话', name_en: null, pct: 95.8 },
  ],
  teammates: [],
  tera_types: [],
  spreads: [
    { nature: 'careful', nature_label: '慎重', points: [32, 0, 14, 0, 20, 0], pct: 5.4 },
    { nature: 'adamant', nature_label: '固执', points: [32, 32, 0, 0, 2, 0], pct: 3.0 },
  ],
  ivs: null,
}

describe('recommendedBuild', () => {
  it('取每类第一条（后端已按使用率降序）', () => {
    const build = recommendedBuild(profile)

    expect(build.nature?.nature).toBe('careful')
    expect(build.ability?.slug).toBe('intimidate')
    expect(build.item?.slug).toBe('sitrus-berry')
    expect(build.moves.map((move) => move.slug)).toEqual(['fake-out', 'parting-shot'])
  })

  it('招式最多取 6 个', () => {
    const many = {
      ...profile,
      moves: Array.from({ length: 9 }, (_, index) => ({
        slug: `move-${index}`,
        name: `招式${index}`,
        name_en: null,
        pct: 90 - index,
      })),
    }
    expect(recommendedBuild(many).moves).toHaveLength(6)
  })
})

describe('splitPoints', () => {
  it('按 HP / 攻击 / 防御 / 特攻 / 特防 / 速度补全六项', () => {
    expect(splitPoints([32, 0, 14])).toEqual([
      { label: 'HP', value: 32 },
      { label: '攻击', value: 0 },
      { label: '防御', value: 14 },
      { label: '特攻', value: 0 },
      { label: '特防', value: 0 },
      { label: '速度', value: 0 },
    ])
  })
})

describe('pointsScale / spreadSummary', () => {
  it('Champions 能力点满量程 32，旧世代 EV 满量程 252', () => {
    expect(pointsScale('stat_points')).toBe(32)
    expect(pointsScale('ev')).toBe(252)
  })

  it('摘要包含性格、六项配点与单位', () => {
    expect(spreadSummary(profile.spreads[0], 'stat_points')).toBe(
      '慎重 · 32/0/14/0/20/0 点',
    )
    expect(spreadSummary(profile.spreads[1], 'ev')).toBe('固执 · 32/32/0/0/2/0 EV')
  })
})

describe('teammateLabel', () => {
  it('优先中文名，缺失时把显示名转成可读形式', () => {
    expect(teammateLabel({ name_zh: '轰擂金刚猩', showdown_name: 'rillaboom' })).toBe(
      '轰擂金刚猩',
    )
    expect(teammateLabel({ name_zh: null, showdown_name: 'charizard-mega-y' })).toBe(
      'Charizard Mega Y',
    )
  })
})
