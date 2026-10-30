/**
 * 招式详情页测试：数值、学习者链接与版本筛选。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { MoveDetail } from '@/features/moves/api'

const detail: MoveDetail = {
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
  learner_count: 2,
  is_machine: true,
  learners: [
    {
      dex_number: 1,
      name_zh: '妙蛙种子',
      name_en: 'bulbasaur',
      types: ['grass', 'poison'],
      is_legendary: false,
      is_mythical: false,
      version_groups: {
        'scarlet-violet': [{ method: 'machine', method_label: '招式学习器', level: 0 }],
        'sword-shield': [{ method: 'machine', method_label: '招式学习器', level: 0 }],
      },
      latest_methods: ['machine'],
    },
    {
      dex_number: 150,
      name_zh: '超梦',
      name_en: 'mewtwo',
      types: ['psychic'],
      is_legendary: true,
      is_mythical: false,
      version_groups: {
        'sword-shield': [{ method: 'tutor', method_label: '教学', level: 0 }],
      },
      latest_methods: ['tutor'],
    },
  ],
  learners_by_version: { 'scarlet-violet': 1, 'sword-shield': 2 },
  method_counts: { machine: 2, tutor: 1 },
  version_labels: { 'scarlet-violet': '朱／紫', 'sword-shield': '剑／盾' },
  method_labels: { machine: '招式学习器', tutor: '教学' },
}

vi.mock('@/features/moves/hooks', () => ({
  useMoveDetail: () => ({ isPending: false, isError: false, data: detail, refetch: vi.fn() }),
}))

const { MoveDetailPage } = await import('@/pages/MoveDetailPage')

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/moves/protect']}>
      <Routes>
        <Route path="/moves/:moveName" element={<MoveDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('MoveDetailPage', () => {
  it('展示数值、说明与学习器数量', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: '守住' })).toBeInTheDocument()
    expect(screen.getByText('完全挡住对手的攻击。')).toBeInTheDocument()
    expect(screen.getByText('2 只可学')).toBeInTheDocument()
    // 「招式学习器」出现在徽章与筛选按钮中
    expect(screen.getAllByText('招式学习器').length).toBeGreaterThan(0)
  })

  it('默认展示最新版本，学习者链接回图鉴', () => {
    renderPage()

    const link = screen.getByRole('link', { name: /妙蛙种子/ })
    expect(link).toHaveAttribute('href', '/dex/1')
    // 最新版本（朱紫）只有妙蛙种子会，超梦不在列表里
    expect(screen.queryByRole('link', { name: /超梦/ })).not.toBeInTheDocument()
  })

  it('切换到剑盾后展示该版本的学习者与方式', async () => {
    renderPage()

    // 版本标签在「谁会这招」与「各版本可学数量」各出现一次，取第一个
    await userEvent.click(screen.getAllByRole('button', { name: /剑／盾/ })[0])

    expect(screen.getByRole('link', { name: /超梦/ })).toHaveAttribute('href', '/dex/150')
    expect(screen.getAllByText(/教学/).length).toBeGreaterThan(0)
  })

  it('按名称筛选学习者', async () => {
    renderPage()

    await userEvent.type(screen.getByRole('textbox', { name: '筛选宝可梦' }), '超梦')
    expect(screen.queryByRole('link', { name: /妙蛙种子/ })).not.toBeInTheDocument()
  })
})
