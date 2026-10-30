/**
 * 图鉴列表页测试：卡片内容、筛选摘要与分页交互。
 *
 * 列表数据通过 mock hooks 注入，避免测试依赖后端。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PokemonListResponse, PokemonSummary } from '@/features/dex/api'

const bulbasaur: PokemonSummary = {
  dex_number: 1,
  name_en: 'bulbasaur',
  name_zh: '妙蛙种子',
  name_ja: null,
  types: ['grass', 'poison'],
  stats: {
    hp: 45,
    attack: 49,
    defense: 49,
    'special-attack': 65,
    'special-defense': 65,
    speed: 45,
  },
  total_stats: 318,
  artwork_url: '/media/artwork/1.png',
  artwork_fallback_url: null,
  sprite_url: '/media/sprites/1.png',
  is_legendary: false,
  is_mythical: false,
  abilities: [
    { name: 'overgrow', zh: '茂盛', is_hidden: false, is_s_tier: false },
    { name: 'chlorophyll', zh: '叶绿素', is_hidden: true, is_s_tier: true },
  ],
  is_demo: false,
}

const mewtwo: PokemonSummary = {
  ...bulbasaur,
  dex_number: 150,
  name_en: 'mewtwo',
  name_zh: '超梦',
  types: ['psychic'],
  stats: {
    hp: 106,
    attack: 110,
    defense: 90,
    'special-attack': 154,
    'special-defense': 90,
    speed: 130,
  },
  total_stats: 680,
  is_legendary: true,
  abilities: [],
}

const pages: Record<number, PokemonSummary[]> = {
  1: [bulbasaur, mewtwo],
  2: [{ ...bulbasaur, dex_number: 2, name_zh: '妙蛙草' }],
}

const state = vi.hoisted(() => ({
  page: 1,
  pageSize: 24,
  type: undefined as string | undefined,
  generation: undefined as number | undefined,
  q: undefined as string | undefined,
  sort: undefined as string | undefined,
}))

vi.mock('@/features/dex/hooks', () => ({
  useDebouncedValue: <T,>(value: T) => value,
  usePokemonList: (params: {
    page: number
    type?: string
    generation?: number
    q?: string
    sort?: string
  }) => {
    state.page = params.page
    state.pageSize = (params as { page_size?: number }).page_size ?? 24
    state.type = params.type
    state.generation = params.generation
    state.q = params.q
    state.sort = params.sort
    const data: PokemonListResponse = {
      items: pages[params.page] ?? [],
      meta: { page: params.page, page_size: 24, total: 49, total_pages: 3 },
    }
    return { isPending: false, isError: false, data, refetch: vi.fn() }
  },
}))

const { DexPage } = await import('@/pages/DexPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <DexPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  // 视图偏好会写入 localStorage，用例之间要清掉，避免相互影响
  window.localStorage.clear()
})

describe('DexPage', () => {
  it('卡片展示中文名、英文名、属性、特性与种族值合计', () => {
    renderPage()

    expect(screen.getByText('妙蛙种子')).toBeInTheDocument()
    expect(screen.getByText('bulbasaur')).toBeInTheDocument()
    // 「草」「毒」同时出现在属性筛选按钮与卡片徽章里
    expect(screen.getAllByText('草').length).toBeGreaterThan(1)
    expect(screen.getAllByText('毒').length).toBeGreaterThan(0)
    expect(screen.getByText('茂盛')).toBeInTheDocument()
    expect(screen.getByText('∑ 318')).toBeInTheDocument()
    // S 级特性标红加粗
    expect(screen.getByText('叶绿素')).toHaveClass('text-destructive')
  })

  it('卡片链接到详情页，传说宝可梦带标记', () => {
    renderPage()

    expect(screen.getByRole('link', { name: /妙蛙种子/ })).toHaveAttribute('href', '/dex/1')
    expect(screen.getByText('传说')).toBeInTheDocument()
  })

  it('点击页码切换页面并更新条目区间', async () => {
    renderPage()
    const nav = screen.getByRole('navigation', { name: '图鉴分页' })
    // 测试数据 total=49、page_size=24：第 1 页覆盖 1–24
    expect(nav.textContent).toMatch(/第 1–24 只/)
    expect(nav.textContent).toMatch(/共 49 只/)

    await userEvent.click(screen.getByRole('button', { name: '2' }))

    expect(state.page).toBe(2)
    expect(screen.getByText('妙蛙草')).toBeInTheDocument()
  })

  it('属性筛选写入查询参数并显示筛选摘要', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: '草' }))

    expect(state.type).toBe('grass')
    expect(state.page).toBe(1)
    expect(screen.getByText(/筛选结果/)).toBeInTheDocument()
  })

  it('切换到列表模式显示完整表格列', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /列表/ }))

    const table = screen.getByRole('table')
    expect(table).toBeInTheDocument()
    // 表头包含中英文名称、六项种族值与特性
    for (const header of ['编号', '名称', '属性', 'HP', '攻击', '防御', '特攻', '特防', '速度', '合计', '特性']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    // 行内展示六项数值：妙蛙种子特攻 65
    expect(screen.getByRole('link', { name: /妙蛙种子/ })).toBeInTheDocument()
    expect(screen.getAllByText('65').length).toBeGreaterThan(0)
  })

  it('列表模式的特性是链接，带 expand 参数定位到特性页', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /列表/ }))

    const abilityLink = screen.getByRole('link', { name: /茂盛/ })
    expect(abilityLink).toHaveAttribute('href', '/abilities?q=overgrow&expand=overgrow')
  })

  it('列表模式给传说宝可梦加图标', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /列表/ }))

    expect(screen.getByLabelText('传说的宝可梦')).toBeInTheDocument()
  })

  it('列表模式每行显示小图标', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /列表/ }))

    // 妙蛙种子的小图标；超梦的 fixture 复用了同一地址，因此用 alt 区分
    expect(screen.getByRole('img', { name: '妙蛙种子' })).toHaveAttribute(
      'src',
      '/media/sprites/1.png',
    )
    expect(screen.getByRole('img', { name: '超梦' })).toBeInTheDocument()
  })

  it('列表模式默认每页 50 条，可切换到 25 / 100 / 200', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /列表/ }))
    expect(state.pageSize).toBe(50)

    const select = screen.getByRole('combobox', { name: '列表每页条数' })
    await userEvent.selectOptions(select, '200')
    expect(state.pageSize).toBe(200)

    await userEvent.selectOptions(select, '25')
    expect(state.pageSize).toBe(25)
    // 换每页条数后回到第 1 页
    expect(state.page).toBe(1)
  })

  it('列表条数偏好写入 localStorage', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /列表/ }))
    await userEvent.selectOptions(screen.getByRole('combobox', { name: '列表每页条数' }), '100')

    const stored = JSON.parse(window.localStorage.getItem('pokemon-lab:dex-view') ?? '{}')
    expect(stored.listSize).toBe(100)
  })

  it('缩放按钮在紧凑 / 标准 / 大图之间切换并改变每页条数', async () => {
    renderPage()

    expect(state.pageSize).toBe(24)
    await userEvent.click(screen.getByRole('button', { name: '缩小卡片' }))
    expect(state.pageSize).toBe(48)
    expect(screen.getByText('紧凑')).toBeInTheDocument()
    // 列表条数选择器只在列表模式出现
    expect(screen.queryByRole('combobox', { name: '列表每页条数' })).not.toBeInTheDocument()
  })

  it('视角与密度偏好写入 localStorage', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /列表/ }))
    const stored = JSON.parse(window.localStorage.getItem('pokemon-lab:dex-view') ?? '{}')
    expect(stored.view).toBe('list')
  })

  it('世代筛选传给列表接口', async () => {
    renderPage()

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: '按登场世代筛选' }),
      '9',
    )

    expect(state.generation).toBe(9)
  })

  it('排序控件支持编号与种族值升降序，并重置到第 1 页', async () => {
    renderPage()

    // 默认编号升序
    expect(state.sort).toBe('dex')

    await userEvent.selectOptions(screen.getByRole('combobox', { name: '排序方式' }), 'total_stats')
    expect(state.sort).toBe('total_stats')
    expect(state.page).toBe(1)

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: '排序方式' }),
      'total_stats_asc',
    )
    expect(state.sort).toBe('total_stats_asc')

    await userEvent.selectOptions(screen.getByRole('combobox', { name: '排序方式' }), 'dex_desc')
    expect(state.sort).toBe('dex_desc')
  })

  it('排序偏好写入 localStorage', async () => {
    renderPage()

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: '排序方式' }),
      'total_stats',
    )

    const stored = JSON.parse(window.localStorage.getItem('pokemon-lab:dex-view') ?? '{}')
    expect(stored.sort).toBe('total_stats')
  })

  it('属性筛选后排序参数同时传给接口（在子列表内排序）', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: '火' }))
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: '排序方式' }),
      'total_stats',
    )

    expect(state.type).toBe('fire')
    expect(state.sort).toBe('total_stats')
    expect(state.page).toBe(1)
  })

  it('列表模式点击「合计」表头切换种族值排序方向', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /列表/ }))

    const totalHeader = screen.getByRole('columnheader', { name: /合计/ })
    expect(totalHeader).toHaveAttribute('aria-sort', 'none')

    await userEvent.click(screen.getByRole('button', { name: /合计/ }))
    expect(state.sort).toBe('total_stats')
    expect(screen.getByRole('columnheader', { name: /合计/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    )

    await userEvent.click(screen.getByRole('button', { name: /合计/ }))
    expect(state.sort).toBe('total_stats_asc')
    expect(screen.getByRole('columnheader', { name: /合计/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )
  })

  it('列表模式点击「编号」表头切换编号升 / 降序', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /列表/ }))

    expect(screen.getByRole('columnheader', { name: /编号/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )

    await userEvent.click(screen.getByRole('button', { name: /编号/ }))
    expect(state.sort).toBe('dex_desc')
    expect(screen.getByRole('columnheader', { name: /编号/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
  })
})
