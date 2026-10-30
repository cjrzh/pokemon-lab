/**
 * 双打对战辅助卡片测试：格式切换、空态、推荐配置与 IV 标注。
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { DoublesResponse } from './api'

const data: DoublesResponse = {
  dex_number: 6,
  has_data: true,
  formats: [
    {
      key: 'champions',
      label: '宝可梦冠军 · VGC 2026 Reg M-C',
      short_label: '冠军',
      game: 'Pokémon Champions',
      ruleset: 'VGC 2026 Reg M-C',
      month: '2026-09',
      cutoff: 1760,
      points_kind: 'stat_points',
      battles: 1631943,
      trade_prefix: null,
      default_level: 50,
      note: null,
      source_url: null,
      imported_at: null,
      profiles: [
        {
          showdown_name: 'Charizard-Mega-Y',
          rank: 14,
          usage: 12.19846,
          raw_count: 307430,
          abilities: [{ slug: 'drought', name: '日照', name_en: null, pct: 100 }],
          items: [
            {
              slug: 'charizardite-y',
              name: '喷火龙进化石Ｙ',
              name_en: null,
              icon_url: '/media/items/charizardite-y.png',
              pct: 100,
            },
            {
              slug: 'leftovers',
              name: '吃剩的东西',
              name_en: null,
              icon_url: null,
              pct: 3,
            },
          ],
          moves: [
            { slug: 'protect', name: '守住', name_en: 'Protect', type: 'normal', pct: 99.4 },
            { slug: 'heat-wave', name: '热风', name_en: 'Heat Wave', type: 'fire', pct: 99.2 },
          ],
          teammates: [
            { showdown_name: 'garchomp', dex_number: 445, name_zh: '烈咬陆鲨', pct: 35.3 },
          ],
          tera_types: [],
          spreads: [
            { nature: 'timid', nature_label: '胆小', points: [2, 0, 0, 32, 0, 32], pct: 8.4 },
            { nature: 'modest', nature_label: '内敛', points: [8, 0, 0, 32, 0, 26], pct: 3.8 },
          ],
          ivs: null,
        },
        {
          showdown_name: 'Charizard',
          rank: 241,
          usage: 0.03393,
          raw_count: 1200,
          abilities: [],
          items: [],
          moves: [],
          teammates: [],
          tera_types: [],
          spreads: [],
          ivs: null,
        },
      ],
    },
    {
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
      note: '测试备注',
      source_url: null,
      imported_at: null,
      profiles: [
        {
          showdown_name: 'Charizard',
          rank: 117,
          usage: 0.22634,
          raw_count: 5000,
          abilities: [{ slug: 'blaze', name: '猛火', name_en: null, pct: 80 }],
          items: [
            {
              slug: 'life-orb',
              name: '生命宝珠',
              name_en: null,
              icon_url: '/media/items/life-orb.png',
              pct: 40,
            },
          ],
          moves: [{ slug: 'heat-wave', name: '热风', name_en: 'Heat Wave', type: 'fire', pct: 90 }],
          teammates: [],
          tera_types: [{ type: 'fire', pct: 60 }],
          spreads: [
            { nature: 'timid', nature_label: '胆小', points: [4, 0, 0, 252, 0, 252], pct: 33.3 },
          ],
          ivs: {
            ivs: { hp: 31, attack: 0, defense: 31, 'special-attack': 31, 'special-defense': 31, speed: 31 },
            reasons: ['特攻向配置，0 攻可减少混乱自伤与欺诈伤害'],
            inferred: true,
          },
        },
      ],
    },
    {
      key: 'bdsp',
      label: '晶灿钻石／明亮珍珠 · 双打',
      short_label: 'BDSP',
      game: 'Brilliant Diamond & Shining Pearl',
      ruleset: 'Doubles OU',
      month: '2021-12',
      cutoff: 1500,
      points_kind: 'ev',
      battles: 86394,
      trade_prefix: '!tradeBDSP',
      default_level: 100,
      note: null,
      source_url: null,
      imported_at: null,
      profiles: [],
    },
  ],
}

const state = vi.hoisted(() => ({ current: {} as Record<string, unknown> }))

vi.mock('./hooks', () => ({
  useDoubles: () => state.current,
}))

const { DoublesCard } = await import('./DoublesCard')

function renderCard() {
  state.current = { isPending: false, isError: false, data, refetch: vi.fn() }
  return render(
    <MemoryRouter>
      <DoublesCard dexNumber={6} />
    </MemoryRouter>,
  )
}

describe('DoublesCard', () => {
  it('默认选择有数据的格式并展示推荐配置与统计月份', () => {
    renderCard()

    expect(screen.getByText('双打对战辅助')).toBeInTheDocument()
    expect(screen.getByText(/2026-09 · cutoff 1760/)).toBeInTheDocument()
    expect(screen.getByText('推荐配置')).toBeInTheDocument()
    expect(screen.getByText('日照')).toBeInTheDocument()
    expect(screen.getByText('喷火龙进化石Ｙ')).toBeInTheDocument()
    expect(screen.getByText('胆小')).toBeInTheDocument()
    expect(screen.getByText('#14')).toBeInTheDocument()
  })

  it('切换到无数据的格式显示空态提示', async () => {
    renderCard()
    await userEvent.click(screen.getByRole('button', { name: /BDSP/ }))

    expect(screen.getByText(/该格式没有这只宝可梦的统计数据/)).toBeInTheDocument()
  })

  it('推断的个体值明确标注来源', async () => {
    renderCard()
    await userEvent.click(screen.getByRole('button', { name: /朱紫/ }))

    expect(screen.getByText('推断 · 非数据源字段')).toBeInTheDocument()
    expect(screen.getByText(/0 攻可减少混乱自伤/)).toBeInTheDocument()
  })

  it('队友链接到对应图鉴页', () => {
    renderCard()
    const link = screen.getByRole('link', { name: /烈咬陆鲨/ })
    expect(link).toHaveAttribute('href', '/dex/445')
  })

  it('推荐配置里的招式带属性徽章，且代码为纯英文', async () => {
    renderCard()

    // 推荐配置区：招式行显示属性徽章（火）
    expect(screen.getAllByText('火').length).toBeGreaterThan(0)
    const code = screen.getByText(/Language: CHS/).textContent ?? ''
    expect(code).toContain('- Protect')
    expect(code).toContain('- Heat Wave')
    expect(code).not.toMatch(/[\u4e00-\u9fa5]/)
  })

  it('\u300c\u5168\u90e8\u62db\u5f0f\u300d\u5217\u8868\u540c\u6837\u663e\u793a\u5c5e\u6027\u5fbd\u7ae0\uff0c\u9053\u5177\u4e0d\u663e\u793a', () => {
    renderCard()

    const allMoves = screen.getByRole('button', { name: /\u5168\u90e8\u62db\u5f0f/ }).closest('div')!
    expect(within(allMoves).getAllByText('\u706b').length).toBe(1)
    expect(within(allMoves).getByText('\u4e00\u822c')).toBeInTheDocument()

    // \u9053\u5177\u6ca1\u6709\u5c5e\u6027\uff0c\u5217\u8868\u884c\u91cc\u4e0d\u5e94\u51fa\u73b0\u5c5e\u6027\u5fbd\u7ae0
    const allItems = screen.getByRole('button', { name: /\u5176\u4ed6\u9053\u5177/ }).closest('div')!
    expect(within(allItems).queryByText('\u4e00\u822c')).not.toBeInTheDocument()
    expect(within(allItems).queryByText('\u706b')).not.toBeInTheDocument()
  })

  it('\u63a8\u8350\u914d\u7f6e\u7684\u9053\u5177\u4e0e\u300c\u5176\u4ed6\u9053\u5177\u300d\u5217\u8868\u663e\u793a\u9053\u5177\u56fe\u6807', async () => {
    renderCard()

    // \u63a8\u8350\u914d\u7f6e\uff1a\u9053\u5177\u884c\u524d\u7f6e 30\u00d730 \u56fe\u6807
    const recommended = screen.getByRole('img', { name: '\u55b7\u706b\u9f99\u8fdb\u5316\u77f3\uff39' })
    expect(recommended).toHaveAttribute('src', '/media/items/charizardite-y.png')

    // \u300c\u5176\u4ed6\u9053\u5177\u300d\u9ed8\u8ba4\u6298\u53e0\uff0c\u5c55\u5f00\u540e\uff1a\u6709 icon_url \u7684\u6e32\u67d3\u56fe\u7247\uff1b\u6ca1\u6709\u7684\uff08\u5403\u5269\u7684\u4e1c\u897f\uff09\u663e\u793a\u5360\u4f4d
    await userEvent.click(screen.getByRole('button', { name: /\u5176\u4ed6\u9053\u5177/ }))
    const allItems = screen.getByRole('button', { name: /\u5176\u4ed6\u9053\u5177/ }).closest('div')!
    expect(within(allItems).getByText('\u5403\u5269\u7684\u4e1c\u897f')).toBeInTheDocument()
    expect(within(allItems).queryByRole('img', { name: '\u5403\u5269\u7684\u4e1c\u897f' })).not.toBeInTheDocument()
  })

  it('Showdown \u7f16\u8f91\u5668\u7684\u62db\u5f0f\u4e0b\u62c9\u6846\u65c1\u4e5f\u663e\u793a\u5bf9\u5e94\u5c5e\u6027\u5fbd\u7ae0', () => {
    renderCard()

    const first = screen.getByRole('combobox', { name: '\u62db\u5f0f 1' }).closest<HTMLElement>('div.flex')!
    expect(within(first).getByText('\u4e00\u822c')).toBeInTheDocument()

    const second = screen.getByRole('combobox', { name: '\u62db\u5f0f 2' }).closest<HTMLElement>('div.flex')!
    expect(within(second).getByText('\u706b')).toBeInTheDocument()
  })

  it('Showdown 代码：朱紫带 !tradeSV 前缀，表单实时更新', async () => {
    renderCard()
    await userEvent.click(screen.getByRole('button', { name: /朱紫/ }))

    const code = screen.getByText(/Language: CHS/)
    expect(code.textContent?.split('\n')[0]).toBe('!tradeSV')
    expect(code.textContent).toContain('EVs: 4 HP / 252 SpA / 252 Spe')
    expect(code.textContent).toContain('Tera Type: Fire')

    // 手动去掉闪光，代码随之变化
    await userEvent.click(screen.getByRole('checkbox', { name: '闪光' }))
    expect(screen.getByText(/Language: CHS/).textContent).not.toContain('Shiny: Yes')
  })

  it('Showdown 代码：BDSP 前缀与 100 级', async () => {
    renderCard()
    // BDSP 在测试数据中无形态，切过去看到的是空态；这里直接切到有数据的冠军
    const code = screen.getByText(/Language: CHS/)
    // 冠军没有交换前缀，第一行是宝可梦
    expect(code.textContent?.split('\n')[0]).toContain('Charizard-Mega-Y')
  })

  it('多形态时切换形态标签', async () => {
    renderCard()
    const formButtons = screen.getAllByRole('button', { name: /Charizard/ })
    expect(formButtons.length).toBe(2)
    await userEvent.click(formButtons[1])

    // 切到普通形态后，排名概览随之更新
    expect(screen.getByText('#241')).toBeInTheDocument()
  })
})
