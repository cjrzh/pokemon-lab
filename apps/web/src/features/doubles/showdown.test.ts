/**
 * Showdown 导出纯函数测试：默认值、格式、前缀与边界修正。
 */

import { describe, expect, it } from 'vitest'

import type { DoublesFormatBlock, DoublesProfile } from './api'
import {
  defaultDraft,
  normalizeDraft,
  renderShowdown,
  type ShowdownDraft,
} from './showdown'

function format(patch: Partial<DoublesFormatBlock> = {}): DoublesFormatBlock {
  return {
    key: 'sv',
    label: '朱紫 · VGC 2026 Reg I',
    short_label: '朱紫',
    game: 'Scarlet & Violet',
    ruleset: 'VGC 2026 Reg I',
    month: '2026-04',
    cutoff: 1630,
    points_kind: 'ev',
    battles: 623088,
    trade_prefix: '!tradeSV',
    default_level: 50,
    note: null,
    source_url: null,
    imported_at: null,
    profiles: [],
    ...patch,
  }
}

const profile: DoublesProfile = {
  showdown_name: 'Urshifu-Rapid-Strike',
  rank: 5,
  usage: 27.0,
  raw_count: 31258,
  abilities: [{ slug: 'unseen-fist', name: '无形拳', name_en: 'Unseen Fist', pct: 100 }],
  items: [{ slug: 'choice-band', name: '讲究头带', name_en: 'Choice Band', pct: 51 }],
  moves: [
    { slug: 'surging-strikes', name: '水流连打', name_en: 'Surging Strikes', pct: 99.9 },
    { slug: 'close-combat', name: '近身战', name_en: 'Close Combat', pct: 97.6 },
    { slug: 'aqua-jet', name: '水流喷射', name_en: 'Aqua Jet', pct: 86.4 },
    { slug: 'u-turn', name: '急速折返', name_en: 'U-turn', pct: 83.0 },
    { slug: 'detect', name: '看穿', name_en: 'Detect', pct: 12.7 },
  ],
  teammates: [],
  tera_types: [{ type: 'ghost', pct: 60.4 }],
  spreads: [
    { nature: 'adamant', nature_label: '固执', points: [68, 236, 20, 0, 4, 180], pct: 37.6 },
  ],
  ivs: null,
}

describe('defaultDraft', () => {
  it('采用推荐配装，IV 全 31，闪光 / CHS / 雌性', () => {
    const draft = defaultDraft(format(), profile, 4)

    expect(draft.species).toBe('Urshifu-Rapid-Strike')
    expect(draft.ability).toBe('Unseen Fist')
    expect(draft.item).toBe('Choice Band')
    expect(draft.nature).toBe('adamant')
    expect(draft.evs).toEqual([68, 236, 20, 0, 4, 180])
    expect(draft.ivs).toEqual([31, 31, 31, 31, 31, 31])
    expect(draft.moves).toEqual([
      'Surging Strikes',
      'Close Combat',
      'Aqua Jet',
      'U-turn',
    ])
    expect(draft.shiny).toBe(true)
    expect(draft.language).toBe('CHS')
    expect(draft.gender).toBe('F')
    expect(draft.level).toBe(50)
    expect(draft.teraType).toBe('Ghost')
  })

  it('按性别比例决定标记：无性别 / 仅雄性 / 仅雌性', () => {
    expect(defaultDraft(format(), profile, -1).gender).toBeNull()
    expect(defaultDraft(format(), profile, 0).gender).toBe('M')
    expect(defaultDraft(format(), profile, 8).gender).toBe('F')
  })

  it('Champions 没有 IV 与太晶属性，等级沿用格式默认值', () => {
    const draft = defaultDraft(
      format({ key: 'champions', points_kind: 'stat_points', trade_prefix: null, default_level: 50 }),
      profile,
      -1,
    )
    expect(draft.ivs).toBeNull()
    expect(draft.teraType).toBeNull()
    expect(draft.gender).toBeNull()
  })

  it('BDSP 默认等级 100', () => {
    const draft = defaultDraft(
      format({ key: 'bdsp', trade_prefix: '!tradeBDSP', default_level: 100 }),
      profile,
      4,
    )
    expect(draft.level).toBe(100)
  })
})

describe('renderShowdown', () => {
  it('输出交换前缀 + Showdown 标准格式', () => {
    const draft = defaultDraft(format(), profile, 4)
    const text = renderShowdown(draft, { tradePrefix: '!tradeSV', includeTera: true })

    expect(text.split('\n')[0]).toBe('!tradeSV')
    expect(text).toContain('Urshifu-Rapid-Strike (F) @ Choice Band  ')
    expect(text).toContain('Ability: Unseen Fist  ')
    expect(text).toContain('Level: 50  ')
    expect(text).toContain('Shiny: Yes  ')
    expect(text).toContain('Language: CHS  ')
    expect(text).toContain('Tera Type: Ghost  ')
    expect(text).toContain('EVs: 68 HP / 236 Atk / 20 Def / 4 SpD / 180 Spe  ')
    expect(text).toContain('Adamant Nature  ')
    expect(text).toContain('- Surging Strikes  ')
    // IV 全 31 时不输出 IV 行
    expect(text).not.toContain('IVs:')
  })

  it('只输出非 31 的 IV 与非 0 的 EV', () => {
    const draft: ShowdownDraft = {
      ...defaultDraft(format(), profile, 4),
      ivs: [31, 0, 31, 31, 31, 31],
      evs: [0, 252, 0, 0, 0, 252],
    }
    const text = renderShowdown(draft, { tradePrefix: null, includeTera: false })

    expect(text).toContain('EVs: 252 Atk / 252 Spe  ')
    expect(text).toContain('IVs: 0 Atk  ')
    expect(text.startsWith('!tradeSV')).toBe(false)
  })

  it('没有前缀时第一行就是宝可梦', () => {
    const draft = defaultDraft(format(), profile, 4)
    const text = renderShowdown(draft, { tradePrefix: null, includeTera: true })
    expect(text.split('\n')[0]).toBe('Urshifu-Rapid-Strike (F) @ Choice Band  ')
  })

  it('等级 100 时不输出 Level 行（Showdown 默认值）', () => {
    const draft = { ...defaultDraft(format(), profile, 4), level: 100 }
    expect(renderShowdown(draft, { tradePrefix: null, includeTera: false })).not.toContain(
      'Level:',
    )
  })
})

describe('usageEnglish / usageOptionLabel', () => {
  it('永远回落到英文（slug 转可读形式），不输出中文', async () => {
    const { usageEnglish } = await import('./showdown')
    expect(usageEnglish({ slug: 'heat-wave', name: '热风', name_en: 'Heat Wave', pct: 90 })).toBe(
      'Heat Wave',
    )
    expect(usageEnglish({ slug: 'u-turn', name: '急速折返', name_en: null, pct: 80 })).toBe(
      'U Turn',
    )
  })

  it('下拉标签包含中文、英文与使用率', async () => {
    const { usageOptionLabel } = await import('./showdown')
    expect(
      usageOptionLabel({ slug: 'protect', name: '守住', name_en: 'Protect', pct: 99.42 }),
    ).toBe('守住（Protect） · 99.4%')
  })
})

describe('normalizeDraft', () => {
  it('EV 按 4 取整并限制在 0–252', () => {
    const draft = normalizeDraft(
      { ...defaultDraft(format(), profile, 4), evs: [-8, 253, 10, 0, 0, 999] },
      'ev',
    )
    expect(draft.evs).toEqual([0, 252, 12, 0, 0, 252])
  })

  it('Champions 能力点按 1 取整并限制在 0–32', () => {
    const draft = normalizeDraft(
      { ...defaultDraft(format(), profile, 4), evs: [33, -1, 2.6, 0, 0, 0] },
      'stat_points',
    )
    expect(draft.evs).toEqual([32, 0, 3, 0, 0, 0])
  })

  it('招式最多 4 个并去掉空行', () => {
    const draft = normalizeDraft(
      {
        ...defaultDraft(format(), profile, 4),
        moves: ['A', 'B', '', 'C', 'D', 'E'],
      },
      'ev',
    )
    expect(draft.moves).toEqual(['A', 'B', 'C', 'D'])
  })

  it('等级限制在 1–100', () => {
    expect(normalizeDraft({ ...defaultDraft(format(), profile, 4), level: 0 }, 'ev').level).toBe(1)
    expect(normalizeDraft({ ...defaultDraft(format(), profile, 4), level: 999 }, 'ev').level).toBe(
      100,
    )
  })
})
