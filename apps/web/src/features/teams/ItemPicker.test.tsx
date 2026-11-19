/**
 * 道具下拉框测试：候选合并（统计推荐 + 百科全量）、搜索、手输与重复高亮。
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/features/teams/catalog', () => ({
  useItemCatalog: () => ({
    isPending: false,
    isError: false,
    data: [
      {
        name: 'leftovers',
        zh: '吃剩的东西',
        name_en: 'Leftovers',
        category: 'held-items',
        category_zh: '携带道具',
        effect_en: null,
        cost: null,
        icon_url: '/media/items/leftovers.png',
      },
      {
        name: 'sitrus-berry',
        zh: '文柚果',
        name_en: 'Sitrus Berry',
        category: 'medicine',
        category_zh: '药品 / 树果',
        effect_en: null,
        cost: null,
        icon_url: null,
      },
    ],
  }),
  itemMatchesQuery: (
    item: { name: string; name_en?: string | null; zh?: string | null },
    term: string,
  ) => {
    const needle = term.trim().toLowerCase()
    if (!needle) return true
    return [item.zh, item.name_en, item.name]
      .filter((value): value is string => Boolean(value))
      .some((value) => value.toLowerCase().includes(needle))
  },
}))

const { ItemPicker } = await import('@/features/teams/ItemPicker')

const suggestions = [
  {
    slug: 'life-orb',
    name: '生命宝珠',
    name_en: 'Life Orb',
    pct: 12.9,
    icon_url: '/media/items/life-orb.png',
  },
]

describe('ItemPicker', () => {
  it('合并统计推荐与百科全量，统计条目带使用率', async () => {
    render(<ItemPicker value={null} onChange={() => {}} suggestions={suggestions} />)

    await userEvent.click(screen.getByRole('button', { name: '道具' }))
    const list = screen.getByRole('listbox', { name: '道具候选' })

    expect(within(list).getByText('生命宝珠')).toBeInTheDocument()
    expect(within(list).getByText('12.9%')).toBeInTheDocument()
    expect(within(list).getByText('吃剩的东西')).toBeInTheDocument()
    expect(within(list).getByText('文柚果')).toBeInTheDocument()
  })

  it('输入中文名筛选，点击后回传 Showdown 英文名', async () => {
    const onChange = vi.fn()
    render(<ItemPicker value={null} onChange={onChange} suggestions={suggestions} />)

    await userEvent.click(screen.getByRole('button', { name: '道具' }))
    await userEvent.type(screen.getByRole('textbox', { name: '搜索道具' }), '文柚')
    await userEvent.click(screen.getByRole('button', { name: /文柚果/ }))

    expect(onChange).toHaveBeenCalledWith('Sitrus Berry')
  })

  it('已选道具显示中文名，可一键取消携带', async () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <ItemPicker value="Life Orb" onChange={onChange} suggestions={suggestions} />,
    )
    expect(screen.getByRole('button', { name: '道具' })).toHaveTextContent('生命宝珠')

    await userEvent.click(screen.getByRole('button', { name: '道具' }))
    await userEvent.click(screen.getByRole('button', { name: /不携带道具/ }))

    expect(onChange).toHaveBeenCalledWith(null)
    rerender(<ItemPicker value={null} onChange={onChange} suggestions={suggestions} />)
    expect(screen.getByRole('button', { name: '道具' })).toHaveTextContent('（不携带）')
  })

  it('找不到的道具可直接回车手输英文名', async () => {
    const onChange = vi.fn()
    render(<ItemPicker value={null} onChange={onChange} suggestions={suggestions} />)

    await userEvent.click(screen.getByRole('button', { name: '道具' }))
    await userEvent.type(
      screen.getByRole('textbox', { name: '搜索道具' }),
      'Weakness Policy{Enter}',
    )

    expect(onChange).toHaveBeenCalledWith('Weakness Policy')
  })

  it('与队友重复时输入框描红（aria 无关，靠样式类）', () => {
    render(
      <ItemPicker value="Life Orb" onChange={() => {}} suggestions={suggestions} conflict />,
    )

    expect(screen.getByRole('button', { name: '道具' }).className).toContain('border-destructive')
  })
})
