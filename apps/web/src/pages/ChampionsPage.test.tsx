/**
 * 冠军图鉴列表页测试：快照信息、卡片内容、搜索/分页参数、空态与无链接条目。
 *
 * 数据通过 mock hooks 注入（与「使用率」页同一套写法），不依赖后端。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { UsageFormatInfo, UsageRankingItem, UsageRankingResponse } from '@/features/usage/api'

const championsFormat: UsageFormatInfo = {
  key: 'champions',
  label: '宝可梦冠军 · VGC 2026 Reg M-C',
  short_label: '冠军',
  game: 'Pokémon Champions',
  ruleset: 'VGC 2026 Reg M-C',
  month: '2026-09',
  cutoff: 1760,
  points_kind: 'stat_points',
  battles: 1631943,
  note: 'Champions 使用能力点（单项上限 32），无个体值系统。',
  source_url: 'https://www.smogon.com/stats/2026-09/gen9championsvgc2026regmc-1760.txt',
  entries: 341,
  imported: true,
}

const rillaboom: UsageRankingItem = {
  showdown_name: 'Rillaboom',
  dex_number: 812,
  name_zh: '轰擂金刚猩',
  name_en: 'rillaboom',
  types: ['grass'],
  artwork_url: null,
  artwork_fallback_url: null,
  sprite_url: '/media/sprites/812.png',
  is_legendary: false,
  is_mythical: false,
  rank: 1,
  usage: 46.6,
  raw_count: 1410840,
  abilities: [{ slug: 'grassy-surge', name: '青草制造者', name_en: 'Grassy Surge', pct: 99.8 }],
  items: [{ slug: 'miracle-seed', name: '奇迹种子', name_en: 'Miracle Seed', icon_url: '/media/items/miracle-seed.png', pct: 62.5 }],
  moves: [
    { slug: 'fake-out', name: '击掌奇袭', name_en: 'Fake Out', type: 'normal', pct: 98.6 },
    { slug: 'wood-hammer', name: '木槌', name_en: 'Wood Hammer', type: 'grass', pct: 71.2 },
  ],
  spread: { nature: 'adamant', nature_label: '固执', points: [2, 32, 0, 0, 0, 32], pct: 33.6 },
}

const unmapped: UsageRankingItem = {
  ...rillaboom,
  showdown_name: 'Rillaboom-Mystery',
  dex_number: null,
  name_zh: null,
  name_en: null,
  types: [],
  rank: 2,
  usage: 0.4,
  abilities: [],
  items: [],
  moves: [],
  spread: null,
}

const state = vi.hoisted(() => ({ params: {} as Record<string, unknown> }))

vi.mock('@/features/champions/hooks', () => ({
  useChampionsRanking: (params: Record<string, unknown>) => {
    state.params = params
    const data: UsageRankingResponse = {
      formats: [championsFormat],
      format_key: 'champions',
      items: [rillaboom, unmapped],
      meta: { page: Number(params.page ?? 1), page_size: Number(params.page_size ?? 24), total: 2, total_pages: 1 },
      has_data: true,
    }
    return { isPending: false, isError: false, data, refetch: vi.fn() }
  },
}))

// 搜索防抖在页面里依赖 dex/hooks；测试里直接透传，保证输入立即反映到参数
vi.mock('@/features/dex/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/dex/hooks')>()
  return { ...actual, useDebouncedValue: (value: string) => value }
})

const { ChampionsPage } = await import('@/pages/ChampionsPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <ChampionsPage />
    </MemoryRouter>,
  )
}

describe('ChampionsPage', () => {
  it('顶部展示规则、统计月份、等级线、对战数与收录数', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: '冠军图鉴' })).toBeInTheDocument()
    expect(screen.getByText(/2026 年 9 月 · cutoff 1760/)).toBeInTheDocument()
    expect(screen.getByText(/1,631,943 场对战/)).toBeInTheDocument()
    expect(screen.getAllByText(/收录 341 只/).length).toBeGreaterThan(0)
    expect(screen.getByText(/数据原文/)).toHaveAttribute('href', championsFormat.source_url)
  })

  it('卡片展示排名、中文名、使用率、招式与能力点配点', () => {
    renderPage()

    expect(screen.getByText('轰擂金刚猩')).toBeInTheDocument()
    expect(screen.getByText(/46\.6%/)).toBeInTheDocument()
    expect(screen.getByText(/木槌/)).toBeInTheDocument()
    // 能力点口径：不是 EV
    expect(screen.getByText(/固执 · 2 HP \/ 32 攻击 \/ 32 速度（点）/)).toBeInTheDocument()
  })

  it('卡片链接到冠军详情页；映射不到图鉴的条目不生成链接', () => {
    renderPage()

    expect(screen.getByRole('link', { name: /轰擂金刚猩/ })).toHaveAttribute(
      'href',
      '/champions/812',
    )
    expect(screen.queryByRole('link', { name: /Rillaboom-Mystery/ })).not.toBeInTheDocument()
  })

  it('搜索写入查询参数并回到第一页', async () => {
    renderPage()

    await userEvent.type(screen.getByRole('textbox', { name: '搜索冠军图鉴' }), '金刚猩')

    expect(state.params.q).toBe('金刚猩')
    expect(state.params.page).toBe(1)
  })

  it('每页条数传给接口', async () => {
    renderPage()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: '每页条数' }), '96')

    expect(state.params.page_size).toBe(96)
    expect(state.params.page).toBe(1)
  })
})
