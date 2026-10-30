/**
 * 招式列表页测试：筛选、排序、链接与分页。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { MoveListResponse } from '@/features/moves/api'

const list: MoveListResponse = {
  items: [
    {
      name: 'protect',
      zh: '守住',
      name_en: 'Protect',
      type: 'normal',
      damage_class: 'status',
      damage_class_zh: '变化',
      power: null,
      accuracy: null,
      pp: 10,
      description_zh: '完全挡住对手的攻击。',
      learner_count: 1003,
      is_machine: true,
    },
    {
      name: 'vine-whip',
      zh: '藤鞭',
      name_en: 'Vine Whip',
      type: 'grass',
      damage_class: 'physical',
      damage_class_zh: '物理',
      power: 45,
      accuracy: 100,
      pp: 25,
      description_zh: null,
      learner_count: 12,
      is_machine: false,
    },
  ],
  meta: { page: 1, page_size: 50, total: 2, total_pages: 1 },
}

const state = vi.hoisted(() => ({
  params: {} as Record<string, unknown>,
}))

vi.mock('@/features/moves/hooks', () => ({
  useMoveList: (params: Record<string, unknown>) => {
    state.params = params
    return { isPending: false, isError: false, data: list, refetch: vi.fn() }
  },
}))

vi.mock('@/features/dex/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/dex/hooks')>()
  return { ...actual, useDebouncedValue: (value: string) => value }
})

const { MovesPage } = await import('@/pages/MovesPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <MovesPage />
    </MemoryRouter>,
  )
}

describe('MovesPage', () => {
  it('列出招式并链接到详情页', () => {
    renderPage()

    expect(screen.getByText('守住')).toBeInTheDocument()
    expect(screen.getByText('藤鞭')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /守住/ })).toHaveAttribute('href', '/moves/protect')
    // 变化招式没有威力显示为 —
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    expect(screen.getByText('1003')).toBeInTheDocument()
  })

  it('属性筛选写入查询参数', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: '草' }))

    expect(state.params.type).toBe('grass')
    expect(state.params.page).toBe(1)
  })

  it('伤害分类与仅学习器筛选', async () => {
    renderPage()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: '伤害分类' }), 'physical')
    expect(state.params.damage_class).toBe('physical')

    await userEvent.click(screen.getByRole('checkbox', { name: '仅学习器' }))
    expect(state.params.machine_only).toBe(true)
  })

  it('排序字段传给接口', async () => {
    renderPage()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: '排序' }), 'learners')
    expect(state.params.sort).toBe('learners')
  })
})
