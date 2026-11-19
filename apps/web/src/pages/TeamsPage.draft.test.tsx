/**
 * 建队页「建到一半跳走再回来」的回归测试。
 *
 * 两个缺陷：
 *   1. 已保存队伍的详情接口把**默认形态**也回传成 `form=<slug>`，前端拿它请求
 *      `?form=clefable` → 422 → 编辑器显示「无法加载该宝可梦的建队选项」；
 *   2. 未保存的新队伍草稿只存在组件 state 里，离开页面即丢失。
 *
 * 这里只测前端行为：草稿从 sessionStorage 恢复、形态映射正确。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TeamsPage } from '@/pages/TeamsPage'
import type { TeamDetail, TeamMemberOptions } from '@/features/teams/api'

const fetchOptions = vi.fn()
const DRAFT_KEY = 'pokemon-lab:team-draft'

vi.mock('@/features/teams/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/teams/hooks')>()
  return {
    ...actual,
    useTeams: () => ({
      data: {
        items: [],
        formats: [
          {
            key: 'swsh',
            label: '剑盾 · VGC',
            short_label: '剑盾',
            points_kind: 'ev' as const,
            trade_prefix: '!tradeSWSH',
            default_level: 50,
            month: '2026-04',
            cutoff: 1630,
          },
        ],
      },
      isPending: false,
      isError: false,
    }),
    useTeamMemberOptions: (dex: number | null, format: string, form?: string | null) =>
      fetchOptions(dex, format, form),
  }
})

function options(): TeamMemberOptions {
  return {
    dex_number: 6,
    showdown_name: 'Charizard',
    name_zh: '喷火龙',
    name_en: 'charizard',
    types: ['fire', 'flying'],
    artwork_url: null,
    sprite_url: '/media/sprites/6.png',
    gender_rate: 1,
    form: null,
    forms: [],
    legal_moves: [
      { slug: 'flamethrower', name: '喷射火焰', name_en: 'Flamethrower', type: 'fire', pct: 0 },
    ],
    legal_abilities: [{ slug: 'blaze', name: '猛火', name_en: 'Blaze', pct: 0 }],
    legal_items: [],
    recommended: null,
    has_stats: false,
    can_gigantamax: false,
    gigantamax_move: null,
    gigantamax: false,
  }
}

function draftTeam(): TeamDetail {
  return {
    id: 0,
    name: '未保存的草稿',
    format_key: 'swsh',
    format_label: '剑盾 · VGC',
    note: null,
    member_count: 1,
    updated_at: null,
    members: [
      {
        position: 0,
        dex_number: 6,
        showdown_name: 'Charizard',
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
      },
    ],
    trade_prefix: '!tradeSWSH',
    default_level: 50,
    points_kind: 'ev',
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/teams']}>
        <Routes>
          <Route path="/teams" element={<TeamsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TeamsPage draft persistence', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    fetchOptions.mockReset()
    fetchOptions.mockImplementation(() => ({
      data: options(),
      isPending: false,
      isError: false,
    }))
  })

  afterEach(() => {
    window.sessionStorage.clear()
  })

  it('restores an unsaved draft after navigating away and back', async () => {
    window.sessionStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({ draft: draftTeam(), forms: {} }),
    )
    renderPage()

    // 草稿被恢复：队伍名与成员都在，而不是空白 / 无法加载
    expect(await screen.findByDisplayValue('未保存的草稿')).toBeInTheDocument()
    expect(await screen.findByText('喷火龙')).toBeInTheDocument()
    // 形态请求走默认（不带 form），不会请求一个不存在的形态
    expect(fetchOptions).toHaveBeenCalled()
    expect(fetchOptions.mock.calls.every((call) => call[2] === undefined)).toBe(true)
  })

  it('ignores corrupt stored drafts', async () => {
    window.sessionStorage.setItem(DRAFT_KEY, '{not json')
    renderPage()
    expect(
      await screen.findByText('从左侧选一支队伍，或新建一支开始。'),
    ).toBeInTheDocument()
  })
})
