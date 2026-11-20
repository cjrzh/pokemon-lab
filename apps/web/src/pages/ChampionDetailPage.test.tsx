/**
 * 冠军图鉴详情页测试：能力点配点、招式百分比、队友链接、空态与非法编号。
 *
 * 数据通过 mock hooks 注入，不依赖后端。
 */

import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PokemonDetail } from '@/features/dex/api'
import type { DoublesFormatBlock, DoublesProfile } from '@/features/doubles/api'

const pokemon = {
  dex_number: 812,
  name_en: 'rillaboom',
  name_zh: '轰擂金刚猩',
  name_ja: null,
  types: ['grass'],
  stats: {},
  total_stats: 530,
  abilities: [{ name: 'grassy-surge', zh: '青草制造者', is_hidden: false }],
  evolution: {},
  moves: { default_version_group: null, version_groups: [] },
  genus_zh: null,
  genus_en: null,
  flavor_zh: null,
  flavor_en: null,
  flavor_zh_source: null,
  genus_zh_source: null,
  artwork_url: '/media/artwork/812.png',
  artwork_fallback_url: null,
  sprite_url: '/media/sprites/812.png',
  is_legendary: false,
  is_mythical: false,
  is_baby: false,
  battle_class: 'normal',
  battle_class_zh: '普通',
  gender_rate: null,
  capture_rate: null,
  base_happiness: null,
  hatch_counter: null,
  growth_rate: null,
  habitat: null,
  color: null,
  shape: null,
  egg_groups: [],
  generation_introduced: 8,
  height_dm: null,
  weight_hg: null,
} as unknown as PokemonDetail

const profile: DoublesProfile = {
  showdown_name: 'Rillaboom',
  rank: 1,
  usage: 46.6,
  raw_count: 1410840,
  abilities: [{ slug: 'grassy-surge', name: '青草制造者', name_en: 'Grassy Surge', pct: 99.8 }],
  items: [
    {
      slug: 'miracle-seed',
      name: '奇迹种子',
      name_en: 'Miracle Seed',
      icon_url: '/media/items/miracle-seed.png',
      pct: 62.5,
    },
  ],
  moves: [{ slug: 'fake-out', name: '击掌奇袭', name_en: 'Fake Out', type: 'normal', pct: 98.6 }],
  teammates: [{ showdown_name: 'Incineroar', dex_number: 727, name_zh: '炽焰咆哮虎', pct: 41.2 }],
  tera_types: [{ type: 'grass', pct: 55.1 }],
  spreads: [
    { nature: 'adamant', nature_label: '固执', points: [2, 32, 0, 0, 0, 32], pct: 33.6 },
  ],
  ivs: null,
}

const block: DoublesFormatBlock = {
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
  profiles: [profile],
}

const state = vi.hoisted(() => ({ hasBlock: true }))

vi.mock('@/features/champions/hooks', () => ({
  useChampionsProfile: () => ({
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    block: state.hasBlock ? block : undefined,
  }),
}))

vi.mock('@/features/dex/hooks', () => ({
  usePokemonDetail: () => ({ isPending: false, isError: false, data: pokemon }),
}))

const { ChampionDetailPage } = await import('@/pages/ChampionDetailPage')

function renderPage(dex = '812') {
  return render(
    <MemoryRouter initialEntries={[`/champions/${dex}`]}>
      <Routes>
        <Route path="/champions/:dexNumber" element={<ChampionDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ChampionDetailPage', () => {
  it('展示排名、使用率、能力点配点与招式百分比', () => {
    state.hasBlock = true
    renderPage()

    expect(screen.getByRole('heading', { name: /轰擂金刚猩/ })).toBeInTheDocument()
    expect(screen.getByText(/第 1 名/)).toBeInTheDocument()
    expect(screen.getByText(/使用率 46\.6%/)).toBeInTheDocument()
    // 能力点：2 HP / 32 攻击 / 32 速度（点）
    expect(screen.getByText(/2 HP \/ 32 攻击 \/ 32 速度（点）/)).toBeInTheDocument()
    expect(screen.getByText(/VGC 2026 Reg M-C · 2026 年 9 月统计/)).toBeInTheDocument()
    expect(screen.getByText(/98\.6%/)).toBeInTheDocument()
  })

  it('队友链接到对方的冠军详情页', () => {
    state.hasBlock = true
    renderPage()

    expect(screen.getByRole('link', { name: /炽焰咆哮虎/ })).toHaveAttribute(
      'href',
      '/champions/727',
    )
  })

  it('特性与道具链到已有页面（特性页 / 道具页）', async () => {
    state.hasBlock = true
    renderPage()

    // 特性：用 slug 精确定位并展开那一行
    expect(screen.getByRole('link', { name: '青草制造者' })).toHaveAttribute(
      'href',
      `/abilities?${new URLSearchParams({ q: 'grassy-surge', expand: 'grassy-surge' }).toString()}`,
    )
    // 道具：道具页没有独立详情页，用 q 回填搜索框定位
    expect(screen.getByRole('link', { name: /奇迹种子/ })).toHaveAttribute(
      'href',
      `/items?${new URLSearchParams({ q: '奇迹种子' }).toString()}`,
    )
  })

  it('性格标注增减效果（固执 → ▲攻击 ▼特攻）', () => {
    state.hasBlock = true
    renderPage()

    expect(screen.getByText('固执')).toBeInTheDocument()
    expect(screen.getByText('▲ 攻击')).toBeInTheDocument()
    expect(screen.getByText('▼ 特攻')).toBeInTheDocument()
  })

  it('没有冠军统计时给出空态而不是报错', () => {
    state.hasBlock = false
    renderPage()

    expect(screen.getByText(/在冠军双打里没有统计记录/)).toBeInTheDocument()
  })

  it('非法编号给出提示并引导返回榜单', () => {
    state.hasBlock = true
    renderPage('abc')

    expect(screen.getByText(/图鉴编号无效/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /返回冠军图鉴/ })).toHaveAttribute(
      'href',
      '/champions',
    )
  })
})
