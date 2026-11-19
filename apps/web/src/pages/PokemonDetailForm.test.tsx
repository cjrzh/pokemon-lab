/**
 * 详情页形态切换测试：菜单渲染、点击后属性 / 种族值 / 立绘随之更新。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PokemonDetail, PokemonFormDetail } from '@/features/dex/api'

const detail: PokemonDetail = {
  dex_number: 892,
  name_en: 'urshifu-single-strike',
  name_zh: '武道熊师',
  name_ja: null,
  types: ['fighting', 'dark'],
  stats: {
    hp: 100,
    attack: 130,
    defense: 100,
    'special-attack': 63,
    'special-defense': 60,
    speed: 97,
  },
  total_stats: 550,
  abilities: [
    {
      name: 'unseen-fist',
      zh: '无形拳',
      is_hidden: false,
      effect_zh: '可以无视守护效果进行攻击。',
      effect_en: null,
      tier: 'normal',
      is_s_tier: false,
    },
  ],
  evolution: {},
  moves: { default_version_group: null, version_groups: [] },
  forms: [
    {
      name: 'urshifu-single-strike',
      label: '武道熊师',
      zh: null,
      name_en: null,
      types: ['fighting', 'dark'],
      is_default: true,
      sprite_url: '/media/sprites/892.png',
    },
    {
      name: 'urshifu-rapid-strike',
      label: '连击流',
      zh: '连击流',
      name_en: 'Rapid Strike Urshifu',
      types: ['fighting', 'water'],
      is_default: false,
      sprite_url: '/media/forms/sprites/urshifu-rapid-strike.png',
    },
  ],
  genus_zh: '拳法宝可梦',
  genus_en: null,
  flavor_zh: null,
  flavor_en: null,
  flavor_zh_source: null,
  genus_zh_source: 'pokeapi',
  artwork_url: '/media/artwork/892.png',
  artwork_fallback_url: null,
  sprite_url: '/media/sprites/892.png',
  is_legendary: false,
  is_mythical: false,
  is_baby: false,
  battle_class: 'normal',
  battle_class_zh: '普通',
  gender_rate: 0,
  capture_rate: 3,
  base_happiness: 50,
  hatch_counter: 120,
  growth_rate: 'slow',
  habitat: null,
  color: 'gray',
  shape: 'upright',
  egg_groups: ['undiscovered'],
  generation_introduced: 8,
  height_dm: 19,
  weight_hg: 1050,
  prev: null,
  next: null,
  source: 'pokeapi',
  source_label: 'PokéAPI 同步',
  is_demo: false,
  synced_at: null,
}

const rapidForm: PokemonFormDetail = {
  dex_number: 892,
  name: 'urshifu-rapid-strike',
  label: '连击流',
  zh: '连击流',
  name_en: 'Rapid Strike Urshifu',
  types: ['fighting', 'water'],
  stats: {
    hp: 100,
    attack: 130,
    defense: 100,
    'special-attack': 63,
    'special-defense': 60,
    speed: 97,
  },
  total_stats: 550,
  abilities: [
    {
      name: 'unseen-fist',
      zh: '无形拳',
      is_hidden: false,
      effect_zh: null,
      effect_en: null,
      tier: 'normal',
      is_s_tier: false,
    },
  ],
  height_dm: 19,
  weight_hg: 1050,
  artwork_url: '/media/forms/artwork/urshifu-rapid-strike.png',
  artwork_fallback_url: null,
  sprite_url: '/media/forms/sprites/urshifu-rapid-strike.png',
  is_default: false,
}

let activeForm = 'default'

vi.mock('@/features/dex/hooks', () => ({
  usePokemonDetail: () => ({ isPending: false, isError: false, data: detail, refetch: vi.fn() }),
  usePokemonForm: (_dex: number, formName: string | null) => {
    activeForm = formName ?? 'default'
    return {
      isPending: false,
      isError: false,
      data: formName === 'urshifu-rapid-strike' ? rapidForm : null,
    }
  },
  useDebouncedValue: (value: string) => value,
  usePokemonList: () => ({
    isPending: false,
    isError: false,
    data: { items: [], meta: { page: 1, page_size: 8, total: 0, total_pages: 1 } },
    refetch: vi.fn(),
  }),
}))

vi.mock('@/features/abilities/hooks', () => ({
  useSTierAbilityNames: () => ({ data: new Set<string>() }),
}))

vi.mock('@/features/doubles/hooks', () => ({
  useDoubles: () => ({
    isPending: false,
    isError: false,
    data: { dex_number: 892, formats: [], has_data: false },
    refetch: vi.fn(),
  }),
}))

const { PokemonDetailPage } = await import('@/pages/PokemonDetailPage')

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/dex/892']}>
      <Routes>
        <Route path="/dex/:dexNumber" element={<PokemonDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PokemonDetailPage 形态切换', () => {
  it('渲染形态菜单，默认形态高亮', () => {
    renderPage()

    expect(screen.getByText('形态（2）')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /武道熊师/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /连击流/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('点击「连击流」后属性与立绘切换，标题带形态名', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /连击流/ }))

    expect(activeForm).toBe('urshifu-rapid-strike')
    // 标题旁出现形态名
    expect(screen.getByRole('heading', { name: /武道熊师/ })).toHaveTextContent('连击流')
    // 属性徽章从「格斗/恶」变「格斗/水」
    expect(screen.getAllByText('水').length).toBeGreaterThan(0)
    // 立绘换成形态立绘（页面里还有形态菜单的小图标，同名，取第一张立绘）
    expect(screen.getAllByRole('img', { name: '武道熊师' })[0]).toHaveAttribute(
      'src',
      '/media/forms/artwork/urshifu-rapid-strike.png',
    )
  })

  it('可以切回默认形态', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /连击流/ }))
    await userEvent.click(screen.getByRole('button', { name: /^武道熊师/ }))

    expect(activeForm).toBe('urshifu-single-strike')
    expect(screen.getAllByRole('img', { name: '武道熊师' })[0]).toHaveAttribute(
      'src',
      '/media/artwork/892.png',
    )
  })
})
