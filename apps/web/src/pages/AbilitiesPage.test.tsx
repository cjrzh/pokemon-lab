import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { AbilityDetail, AbilityListResponse } from '@/features/abilities/api'

const intimidate: AbilityDetail = {
  name: 'intimidate',
  zh: '威吓',
  effect_zh: '出场时降低对手的攻击。',
  effect_en: 'Lowers the foe Attack stat.',
  tier: 's',
  rating_source: 'llm',
  rating_note: '登场即降低对手攻击，是使用率最高的特性之一。',
  holders: [
    {
      dex_number: 130,
      name_zh: '暴鲤龙',
      name_en: 'gyarados',
      types: ['water', 'flying'],
      is_hidden: false,
      is_legendary: false,
      is_mythical: false,
      sprite_url: '/media/sprites/130.png',
    },
  ],
}

const list: AbilityListResponse = {
  items: [
    {
      name: 'intimidate',
      zh: '威吓',
      effect_zh: '出场时降低对手的攻击。',
      tier: 's',
      rating_source: 'llm',
      rating_note: intimidate.rating_note,
      holder_count: 35,
    },
    {
      name: 'run-away',
      zh: '逃跑',
      effect_zh: '从野生宝可梦那里逃走。',
      tier: 'normal',
      rating_source: 'llm',
      rating_note: '对战中没有实际效果。',
      holder_count: 30,
    },
  ],
  meta: { page: 1, page_size: 30, total: 2, total_pages: 1, s_tier_total: 1 },
}

vi.mock('@/features/abilities/hooks', () => ({
  useAbilityList: (params: { q?: string }) => ({
    isPending: false,
    isError: false,
    data: params.q
      ? { ...list, items: list.items.filter((item) => item.name === params.q) }
      : list,
    refetch: vi.fn(),
  }),
  useAbilityDetail: () => ({ isPending: false, isError: false, data: intimidate }),
  useUpdateAbilityRating: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}))

vi.mock('@/features/dex/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/dex/hooks')>()
  return { ...actual, useDebouncedValue: (value: string) => value }
})

const { AbilitiesPage } = await import('@/pages/AbilitiesPage')

describe('AbilitiesPage', () => {
  it('列出特性并标出 S 级', () => {
    render(
      <MemoryRouter>
        <AbilitiesPage />
      </MemoryRouter>,
    )
    expect(screen.getByText('威吓')).toBeInTheDocument()
    expect(screen.getByText('逃跑')).toBeInTheDocument()
    expect(screen.getAllByText('S 级').length).toBeGreaterThan(0)
  })

  it('从图鉴带 ?q=&expand= 跳转时定位并展开目标特性', () => {
    // jsdom 没有实现 scrollIntoView
    Element.prototype.scrollIntoView = vi.fn()
    render(
      <MemoryRouter initialEntries={['/abilities?q=intimidate&expand=intimidate']}>
        <AbilitiesPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('威吓')).toBeInTheDocument()
    expect(screen.getByText('登场即降低对手攻击，是使用率最高的特性之一。')).toBeInTheDocument()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })

  it('展开特性后显示评级理由与拥有者链接', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <AbilitiesPage />
      </MemoryRouter>,
    )
    await user.click(screen.getAllByRole('button', { expanded: false })[0])

    expect(screen.getByText('登场即降低对手攻击，是使用率最高的特性之一。')).toBeInTheDocument()
    const holderLink = screen.getByRole('link', { name: /暴鲤龙/ })
    expect(holderLink).toHaveAttribute('href', '/dex/130')
    // 拥有者行内带 96×96 小图标
    expect(within(holderLink).getByRole('img', { name: '暴鲤龙' })).toHaveAttribute(
      'src',
      '/media/sprites/130.png',
    )
  })
})
