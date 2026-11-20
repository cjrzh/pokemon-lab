/**
 * 道具列表页测试：列表渲染、图标、搜索、分类筛选与分页。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { ItemListResponse } from '@/features/items/api'

const list: ItemListResponse = {
  items: [
    {
      name: 'sitrus-berry',
      zh: '文柚果',
      name_en: 'Sitrus Berry',
      category: 'medicine',
      category_zh: '药品 / 树果',
      effect_en: 'Consumed at 1/2 max HP to recover 1/4 max HP.',
      effect_zh: 'HP 降到 1/2 以下时消耗，回复最大 HP 的 1/4。',
      effect_zh_source: 'project',
      cost: 20,
      icon_url: '/media/items/sitrus-berry.png',
    },
    {
      name: 'leftovers',
      zh: '吃剩的东西',
      name_en: 'Leftovers',
      category: 'held-items',
      category_zh: '携带道具',
      effect_en: 'Restores 1/16 of max HP each turn.',
      effect_zh: '每回合回复最大 HP 的 1/16。',
      effect_zh_source: 'project',
      cost: 0,
      icon_url: '/media/items/leftovers.png',
    },
    {
      name: 'pretty-feather',
      zh: '美丽之羽',
      name_en: 'Pretty Feather',
      category: 'collectibles',
      category_zh: '收集品',
      effect_en: null,
      effect_zh: null,
      effect_zh_source: null,
      cost: 0,
      icon_url: null,
    },
  ],
  meta: { page: 1, page_size: 50, total: 3, total_pages: 1 },
  categories: [
    { value: 'medicine', label: '药品 / 树果', count: 1 },
    { value: 'held-items', label: '携带道具', count: 1 },
    { value: 'collectibles', label: '收集品', count: 1 },
  ],
}

const state = vi.hoisted(() => ({ params: {} as Record<string, unknown> }))

vi.mock('@/features/items/hooks', () => ({
  useItemList: (params: Record<string, unknown>) => {
    state.params = params
    return { isPending: false, isError: false, data: list, refetch: vi.fn() }
  },
}))

vi.mock('@/features/dex/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/dex/hooks')>()
  return { ...actual, useDebouncedValue: (value: string) => value }
})

const { ItemsPage } = await import('@/pages/ItemsPage')

function renderPage(entry = '/items') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <ItemsPage />
    </MemoryRouter>,
  )
}

describe('ItemsPage', () => {
  it('列出道具，带中文名、英文名、分类与说明', () => {
    renderPage()

    expect(screen.getByText('文柚果')).toBeInTheDocument()
    expect(screen.getByText('Sitrus Berry')).toBeInTheDocument()
    expect(screen.getAllByText('携带道具').length).toBeGreaterThan(0)
    expect(screen.getByText(/Consumed at 1\/2 max HP/)).toBeInTheDocument()
    // 没有说明的道具显示占位
    expect(screen.getByText('暂无说明')).toBeInTheDocument()
  })

  it('有图标的道具渲染图标，缺失时显示占位', () => {
    renderPage()

    expect(screen.getByRole('img', { name: '文柚果' })).toHaveAttribute(
      'src',
      '/media/items/sitrus-berry.png',
    )
    expect(screen.queryByRole('img', { name: '美丽之羽' })).not.toBeInTheDocument()
  })

  it('搜索写入查询参数并重置页码', async () => {
    renderPage()

    await userEvent.type(screen.getByRole('textbox', { name: '搜索道具' }), '文柚')

    expect(state.params.q).toBe('文柚')
    expect(state.params.page).toBe(1)
  })

  it('分类筛选写入查询参数', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /携带道具/ }))
    expect(state.params.category).toBe('held-items')

    // 再次点击取消筛选
    await userEvent.click(screen.getByRole('button', { name: /携带道具/ }))
    expect(state.params.category).toBeUndefined()
  })

  it('每页条数传给接口', async () => {
    renderPage()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: '每页条数' }), '100')
    expect(state.params.page_size).toBe(100)
  })

  it('清除筛选恢复默认参数', async () => {
    renderPage()

    await userEvent.type(screen.getByRole('textbox', { name: '搜索道具' }), 'x')
    await userEvent.click(screen.getByRole('button', { name: /清除筛选/ }))

    expect(state.params.q).toBeUndefined()
    expect(state.params.category).toBeUndefined()
  })

  it('URL 带 q 时预填搜索框并按该关键词请求（冠军图鉴的道具链接靠它定位）', () => {
    renderPage('/items?q=文柚果')

    expect(screen.getByRole('textbox', { name: '搜索道具' })).toHaveValue('文柚果')
    expect(state.params.q).toBe('文柚果')
    expect(state.params.page).toBe(1)
  })

  it('清空搜索会从 URL 里去掉 q', async () => {
    renderPage('/items?q=文柚果')

    await userEvent.click(screen.getByRole('button', { name: '清空搜索' }))

    expect(state.params.q).toBeUndefined()
    expect(screen.getByRole('textbox', { name: '搜索道具' })).toHaveValue('')
  })
})

describe('ItemsPage 中文说明', () => {
  it('优先展示中文说明，英文可折叠查看', () => {
    renderPage()

    expect(screen.getByText('HP 降到 1/2 以下时消耗，回复最大 HP 的 1/4。')).toBeInTheDocument()
    expect(screen.getAllByText('项目自译 · 查看英文原文')).toHaveLength(2)
  })

  it('没有中文时回落到英文说明', () => {
    const item = list.items[2]
    item.effect_zh = null
    item.effect_zh_source = null
    item.effect_en = 'A pretty feather.'
    renderPage()

    expect(screen.getByText('A pretty feather.')).toBeInTheDocument()
    // 用例结束后恢复，避免影响其它用例
    item.effect_en = null
  })
})
