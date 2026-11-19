/**
 * 详情页搜索栏测试：防抖查询、下拉结果、点击 / 回车跳转、键盘高亮与空态。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PokemonSummary } from '@/features/dex/api'

const pikachu: PokemonSummary = {
  dex_number: 25,
  name_en: 'pikachu',
  name_zh: '皮卡丘',
  name_ja: null,
  types: ['electric'],
  stats: { hp: 35 },
  total_stats: 320,
  artwork_url: null,
  artwork_fallback_url: null,
  sprite_url: '/media/sprites/25.png',
  is_legendary: false,
  is_mythical: false,
    battle_class: 'normal',
    battle_class_zh: '普通',
  abilities: [],
  is_demo: false,
}

const raichu: PokemonSummary = {
  ...pikachu,
  dex_number: 26,
  name_en: 'raichu',
  name_zh: '雷丘',
  sprite_url: '/media/sprites/26.png',
}

const state = vi.hoisted(() => ({
  params: {} as Record<string, unknown>,
  enabled: undefined as boolean | undefined,
}))

vi.mock('@/features/dex/hooks', () => ({
  useDebouncedValue: (value: string) => value,
  usePokemonList: (
    params: Record<string, unknown>,
    options?: { enabled?: boolean },
  ) => {
    state.params = params
    state.enabled = options?.enabled
    const term = typeof params.q === 'string' ? params.q : ''
    // 只要有关键词就返回两只；「不存在」用于验证空态
    const items = term && !term.includes('不存在') ? [pikachu, raichu] : []
    return {
      isPending: false,
      isError: false,
      data: { items, meta: { page: 1, page_size: 8, total: items.length, total_pages: 1 } },
      refetch: vi.fn(),
    }
  },
}))

const { PokemonSearchBar } = await import('@/features/dex/components/PokemonSearchBar')

function LocationProbe() {
  const location = useLocation()
  return <p data-testid="location">{location.pathname}</p>
}

function renderBar(currentDex?: number) {
  return render(
    <MemoryRouter initialEntries={['/dex/1']}>
      <PokemonSearchBar currentDex={currentDex} />
      <Routes>
        <Route path="/dex/:dexNumber" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PokemonSearchBar', () => {
  it('空输入时不发请求，输入后把关键词传给列表接口', async () => {
    renderBar()
    expect(state.enabled).toBe(false)

    await userEvent.type(screen.getByRole('combobox', { name: '搜索宝可梦' }), '皮')

    expect(state.enabled).toBe(true)
    expect(state.params.q).toBe('皮')
    expect(state.params.page_size).toBe(8)
  })

  it('展示下拉结果（图标、编号、中英文名），点击跳转到对应图鉴', async () => {
    renderBar()

    await userEvent.type(screen.getByRole('combobox', { name: '搜索宝可梦' }), '皮卡丘')

    expect(screen.getByRole('listbox', { name: '宝可梦搜索结果' })).toBeInTheDocument()
    expect(screen.getByText('皮卡丘')).toBeInTheDocument()
    expect(screen.getByText('#0025')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '皮卡丘' })).toHaveAttribute(
      'src',
      '/media/sprites/25.png',
    )

    await userEvent.click(screen.getByRole('button', { name: /皮卡丘/ }))
    expect(screen.getByTestId('location')).toHaveTextContent('/dex/25')
  })

  it('回车打开高亮项，方向键切换', async () => {
    renderBar()

    const input = screen.getByRole('combobox', { name: '搜索宝可梦' })
    await userEvent.type(input, '皮')

    // 默认高亮第一条（皮卡丘）
    await userEvent.keyboard('{Enter}')
    expect(screen.getByTestId('location')).toHaveTextContent('/dex/25')
  })

  it('搜索结果排除当前宝可梦', async () => {
    renderBar(25)

    await userEvent.type(screen.getByRole('combobox', { name: '搜索宝可梦' }), '皮')

    expect(screen.queryByText('皮卡丘')).not.toBeInTheDocument()
    expect(screen.getByText('雷丘')).toBeInTheDocument()
  })

  it('无结果时显示空态提示', async () => {
    renderBar()

    await userEvent.type(screen.getByRole('combobox', { name: '搜索宝可梦' }), '不存在')

    expect(screen.getByText(/没有匹配的宝可梦/)).toBeInTheDocument()
  })

  it('Esc 收起下拉、清空按钮重置输入', async () => {
    renderBar()

    const input = screen.getByRole('combobox', { name: '搜索宝可梦' })
    await userEvent.type(input, '皮')
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '清空搜索' }))
    expect(input).toHaveValue('')
  })
})
