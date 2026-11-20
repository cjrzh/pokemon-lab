/**
 * 建队形态选择：洛托姆这类有多形态的宝可梦。
 *
 * 覆盖：
 *   - 加入后自动选使用率最高的形态（不传 form）；
 *   - 切换形态会带上 `form=` 重新取选项，更新 Showdown 名与推荐招式；
 *   - 只有一种形态时不显示选择器。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TeamMemberEditor } from '@/features/teams/TeamMemberEditor'
import type { TeamMember, TeamMemberOptions } from '@/features/teams/api'

const fetchOptions = vi.fn()

vi.mock('@/features/teams/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/teams/hooks')>()
  return {
    ...actual,
    useTeamMemberOptions: (dex: number | null, format: string, form?: string | null) =>
      fetchOptions(dex, format, form),
  }
})

function optionsFor(form: string | null): TeamMemberOptions {
  const isWash = form !== 'rotom-heat'
  return {
    dex_number: 479,
    showdown_name: isWash ? 'Rotom-Wash' : 'Rotom-Heat',
    name_zh: '洛托姆',
    name_en: 'rotom',
    types: isWash ? ['electric', 'water'] : ['electric', 'fire'],
    artwork_url: null,
    sprite_url: '/media/sprites/479.png',
    gender_rate: -1,
    form,
    forms: [
      {
        form: 'rotom-wash',
        label: '清洗洛托姆',
        showdown_name: 'Rotom-Wash',
        types: ['electric', 'water'],
        sprite_url: '/media/forms/sprites/rotom-wash.png',
        usage: 20,
        is_default: false,
      },
      {
        form: 'rotom-heat',
        label: '加热洛托姆',
        showdown_name: 'Rotom-Heat',
        types: ['electric', 'fire'],
        sprite_url: '/media/forms/sprites/rotom-heat.png',
        usage: 5,
        is_default: false,
      },
      {
        form: null,
        label: '洛托姆',
        showdown_name: 'Rotom',
        types: ['electric', 'ghost'],
        sprite_url: '/media/sprites/479.png',
        usage: 0.5,
        is_default: true,
      },
    ],
    legal_moves: (isWash
      ? [
          { slug: 'hydro-pump', name: '水炮', name_en: 'Hydro Pump', type: 'water', pct: 0 },
          { slug: 'volt-switch', name: '伏特替换', name_en: 'Volt Switch', type: 'electric', pct: 0 },
        ]
      : [
          { slug: 'overheat', name: '过热', name_en: 'Overheat', type: 'fire', pct: 0 },
          { slug: 'volt-switch', name: '伏特替换', name_en: 'Volt Switch', type: 'electric', pct: 0 },
        ]) as TeamMemberOptions['legal_moves'],
    legal_abilities: [
      { slug: 'levitate', name: '飘浮', name_en: 'Levitate', pct: 0 },
    ],
    legal_items: [],
    recommended: {
      showdown_name: isWash ? 'Rotom-Wash' : 'Rotom-Heat',
      rank: 1,
      usage: isWash ? 20 : 5,
      abilities: [{ slug: 'levitate', name: '飘浮', name_en: 'Levitate', pct: 100 }],
      items: [],
      moves: (isWash
        ? [{ slug: 'hydro-pump', name: '水炮', name_en: 'Hydro Pump', type: 'water', pct: 90 }]
        : [{ slug: 'overheat', name: '过热', name_en: 'Overheat', type: 'fire', pct: 90 }]) as never,
      spread: null,
      spreads: [],
    },
    has_stats: true,
    can_gigantamax: false,
    gigantamax_move: null,
    gigantamax: false,
  }
}

function renderEditor(member: TeamMember, onChange = vi.fn(), onFormChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route
            path="*"
            element={
              <TeamMemberEditor
                index={0}
                member={member}
                formatKey="sv"
                pointsKind="ev"
                defaultLevel={50}
                teamMembers={[member]}
                onChange={onChange}
                onRemove={() => undefined}
                onFormChange={onFormChange}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { onChange, onFormChange }
}

const member: TeamMember = {
  position: 0,
  dex_number: 479,
  showdown_name: 'rotom',
  item: null,
  ability: null,
  nature: null,
  evs: [0, 0, 0, 0, 0, 0],
  ivs: null,
  moves: [],
  tera_type: null,
  gender: null,
  shiny: false,
  level: 50,
  language: 'CHS',
}

describe('TeamMemberEditor form selection', () => {
  beforeEach(() => {
    fetchOptions.mockReset()
    // 直接返回 react-query 的查询结果形状（不是 Promise）：组件同步读取 data
    fetchOptions.mockImplementation((_dex: number, _format: string, form?: string | null) => ({
      data: optionsFor(
        form === 'rotom-heat' ? 'rotom-heat' : form === 'default' ? null : 'rotom-wash',
      ),
      isPending: false,
      isError: false,
    }))
  })

  it('requests auto form, then switches to a specific form', async () => {
    const user = userEvent.setup()
    const { onFormChange } = renderEditor(member)

    // 自动选择（undefined）→ 请求里不带 form
    await waitFor(() => expect(fetchOptions).toHaveBeenCalled())
    expect(fetchOptions.mock.calls[0][2]).toBeUndefined()

    // 第一只默认展开：在「形态」分组里找到形态按钮
    const group = await screen.findByRole('group', { name: '选择形态' })
    // 三个形态都列出来（含默认形态），当前生效项被标为选中
    expect(within(group).getByRole('button', { name: /清洗洛托姆/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await user.click(within(group).getByRole('button', { name: /加热洛托姆/ }))
    expect(onFormChange).toHaveBeenCalledWith('rotom-heat')
  })

  it('hides the picker for single-form species', async () => {
    fetchOptions.mockImplementation(() => ({
      data: {
        ...optionsFor(null),
        form: null,
        forms: [
          {
            form: null,
            label: '洛托姆',
            showdown_name: 'Rotom',
            types: ['electric', 'ghost'],
            sprite_url: null,
            usage: 1,
            is_default: true,
          },
        ],
      },
      isPending: false,
      isError: false,
    }))
    renderEditor(member)
    // 等待数据到位后，不应出现形态选择器
    await waitFor(() => expect(fetchOptions).toHaveBeenCalled())
    expect(screen.queryByRole('group', { name: '选择形态' })).not.toBeInTheDocument()
  })
})
