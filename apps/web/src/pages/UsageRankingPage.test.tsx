/**
 * 使用率排行页测试：格式切换、搜索、分页、跳转与统计快照信息。
 *
 * 数据通过 mock hooks 注入，测试不依赖后端。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { UsageFormatInfo, UsageRankingItem, UsageRankingResponse } from '@/features/usage/api'

const formats: UsageFormatInfo[] = [
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
    note: 'BDSP 双打活跃期较早。',
    source_url: 'https://www.smogon.com/stats/2021-12/gen8bdspdoublesou-1500.txt',
    entries: 400,
    imported: true,
  },
  {
    key: 'swsh',
    label: '剑盾 · VGC 2022',
    short_label: '剑盾',
    game: 'Sword & Shield',
    ruleset: 'VGC 2022',
    month: '2022-11',
    cutoff: 1630,
    points_kind: 'ev',
    battles: 278032,
    note: null,
    source_url: null,
    entries: 631,
    imported: true,
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
    note: null,
    source_url: null,
    entries: 757,
    imported: true,
  },
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
    note: null,
    source_url: null,
    entries: 0,
    imported: false,
  },
]

const incineroar: UsageRankingItem = {
  showdown_name: 'Incineroar',
  dex_number: 727,
  name_zh: '炽焰咆哮虎',
  name_en: 'incineroar',
  types: ['fire', 'dark'],
  artwork_url: '/media/artwork/727.png',
  artwork_fallback_url: null,
  sprite_url: '/media/sprites/727.png',
  is_legendary: false,
  is_mythical: false,
  rank: 1,
  usage: 42.44392,
  raw_count: 307430,
  abilities: [{ slug: 'intimidate', name: '威吓', name_en: 'Intimidate', type: null, pct: 99.6 }],
  items: [
    {
      slug: 'sitrus-berry',
      name: '文柚果',
      name_en: 'Sitrus Berry',
      type: null,
      icon_url: '/media/items/sitrus-berry.png',
      pct: 62.7,
    },
  ],
  moves: [
    { slug: 'fake-out', name: '击掌奇袭', name_en: 'Fake Out', type: 'normal', pct: 98.6 },
    { slug: 'flare-blitz', name: '闪焰冲锋', name_en: 'Flare Blitz', type: 'fire', pct: 90.9 },
  ],
  spread: { nature: 'careful', nature_label: '慎重', points: [32, 0, 14, 0, 20, 0], pct: 5.4 },
}

const mimikyu: UsageRankingItem = {
  ...incineroar,
  showdown_name: 'Mimikyu',
  dex_number: 778,
  name_zh: '谜拟丘',
  name_en: 'mimikyu',
  types: ['ghost', 'fairy'],
  rank: 2,
  usage: 18.2,
  raw_count: 100,
  moves: [
    { slug: 'play-rough', name: '嬉闹', name_en: 'Play Rough', type: 'fairy', pct: 90 },
  ],
}

/** 映射不到图鉴的条目：保留展示，但不生成链接。 */
const unmapped: UsageRankingItem = {
  ...incineroar,
  showdown_name: 'Missingno',
  dex_number: null,
  name_zh: null,
  name_en: null,
  types: [],
  rank: 3,
  usage: 0.5,
  abilities: [],
  items: [],
  moves: [],
  spread: null,
}

const state = vi.hoisted(() => ({
  params: {} as Record<string, unknown>,
}))

vi.mock('@/features/usage/hooks', () => ({
  useUsageRanking: (params: Record<string, unknown>) => {
    state.params = params
    const initialized = params.format === 'bdsp'
    const data: UsageRankingResponse = {
      formats,
      format_key: String(params.format),
      items: initialized ? [incineroar, mimikyu, unmapped] : [],
      meta: { page: Number(params.page ?? 1), page_size: 50, total: 3, total_pages: 1 },
      has_data: true,
    }
    return { isPending: false, isError: false, data, refetch: vi.fn() }
  },
}))

vi.mock('@/features/dex/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/dex/hooks')>()
  return { ...actual, useDebouncedValue: (value: string) => value }
})

const { UsageRankingPage } = await import('@/pages/UsageRankingPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <UsageRankingPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  // 每个用例重新初始化（URL 参数由 page 自己维护）
})

describe('UsageRankingPage', () => {
  it('展示四个格式标签与当前格式的统计快照', () => {
    renderPage()

    for (const label of ['BDSP', '剑盾', '朱紫', '冠军']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeInTheDocument()
    }
    expect(screen.getByText(/2021 年 12 月 · cutoff 1500/)).toBeInTheDocument()
    expect(screen.getByText(/86,394 场对战/)).toBeInTheDocument()
    // 默认 BDSP
    expect(state.params.format).toBe('bdsp')
  })

  it('排行行展示名次、使用率、属性与常见配装', () => {
    renderPage()

    expect(screen.getByText('炽焰咆哮虎')).toBeInTheDocument()
    expect(screen.getByText(/Incineroar/)).toBeInTheDocument()
    expect(screen.getByText('42.4%')).toBeInTheDocument()
    // 第二行是 Mimikyu 也带「威吓」（fixture 复用），取全部匹配
    expect(screen.getAllByText(/特性 威吓/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/文柚果/).length).toBeGreaterThan(0)
    // 道具带图标
    expect(screen.getAllByRole('img', { name: '文柚果' })[0]).toHaveAttribute(
      'src',
      '/media/items/sitrus-berry.png',
    )
    expect(
      screen.getAllByText(/慎重 · 32\/0\/14\/0\/20\/0 EV/).length,
    ).toBeGreaterThan(0)
    // 招式带属性徽章
    expect(screen.getAllByText('火').length).toBeGreaterThan(0)
  })

  it('可点击的行链接回图鉴，无法映射的条目不生成链接', () => {
    renderPage()

    expect(screen.getByRole('link', { name: /炽焰咆哮虎/ })).toHaveAttribute('href', '/dex/727')
    expect(screen.queryByRole('link', { name: /Missingno/ })).not.toBeInTheDocument()
    expect(screen.getAllByText(/Missingno/).length).toBeGreaterThan(0)
  })

  it('切换格式后重新请求', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /朱紫/ }))
    expect(state.params.format).toBe('sv')
    expect(state.params.page).toBe(1)
    expect(screen.getByText(/2026 年 4 月 · cutoff 1630/)).toBeInTheDocument()
  })

  it('搜索写入查询参数', async () => {
    renderPage()

    await userEvent.type(screen.getByRole('textbox', { name: '搜索宝可梦' }), '咆哮虎')
    expect(state.params.q).toBe('咆哮虎')
    expect(state.params.page).toBe(1)
  })

  it('每页条数传给接口', async () => {
    renderPage()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: '每页条数' }), '100')
    expect(state.params.page_size).toBe(100)
  })

  it('冠军格式用能力点单位', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /冠军/ }))
    // 接口在冠军格式下无数据 → 空态而不是报错
    expect(screen.getByText(/该格式还没有导入统计数据/)).toBeInTheDocument()
  })
})
