/**
 * 官方赛事详情页测试：三个视图（队伍 / 使用率 / 名次）与「一键建队」入口。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { TournamentDetailPage } from '@/pages/TournamentDetailPage'

const tournament = {
  id: 6,
  source_id: 448,
  name: 'Regional Gdańsk',
  date: '2026-10-31',
  ruleset: 'm-c',
  ruleset_label: '宝可梦冠军 Reg M-C（官方赛事）',
  event_type: 'regional',
  event_type_label: '地区赛',
  country: 'PL',
  players: 758,
  winner: 'Javier Varela',
  winner_country: 'ES',
  format_key: 'champions',
  standings_count: 2,
  team_count: 1,
  has_teamlists: true,
  source_url: 'https://limitlessvgc.com/tournaments/448',
}

const members = Array.from({ length: 6 }, (_, index) => ({
  position: index,
  dex_number: index === 0 ? 445 : 25 + index,
  showdown_name: index === 0 ? 'Garchomp' : `Mon-${index}`,
  species_slug: index === 0 ? 'garchomp' : `mon-${index}`,
  item: 'Rocky Helmet',
  ability: 'Rough Skin',
  nature: 'jolly',
  tera_type: null,
  moves: ['Earthquake', 'Rock Slide', 'Dragon Claw', 'Protect'],
}))

const detail = {
  tournament,
  standings: [
    { rank: 1, player: 'Javier Varela', country: 'ES', species: ['Gholdengo'], team_id: 7472 },
    { rank: 2, player: 'Kyle Livinghouse', country: 'US', species: ['Garchomp'], team_id: null },
  ],
  teams: [
    {
      id: 11,
      rank: 1,
      player: 'Javier Varela',
      country: 'ES',
      showdown_text: 'Garchomp @ Rocky Helmet  \nAbility: Rough Skin  ',
      problems: [],
      validation: { ok: true, issues: [] },
      members,
    },
  ],
  usage: [
    {
      rank: 1,
      species_slug: 'garchomp',
      showdown_name: 'Garchomp',
      dex_number: 445,
      count: 1,
      share: 100,
    },
  ],
}

vi.mock('@/lib/apiClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/apiClient')>()
  return {
    ...actual,
    apiRequest: vi.fn(async (url: string) => {
      if (url.startsWith('/tournaments/6/teams/')) return { members: [] }
      if (url.startsWith('/tournaments/6')) return detail
      throw new Error(`unexpected ${url}`)
    }),
  }
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/tournaments/6']}>
        <Routes>
          <Route path="/tournaments/:tournamentId" element={<TournamentDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TournamentDetailPage', () => {
  it('shows header, team list with build link, usage and standings', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Regional Gdańsk' })).toBeInTheDocument()
    expect(screen.getByText(/758 人/)).toBeInTheDocument()

    // 队伍：第一名默认展开，一键建队是链接
    expect(await screen.findByText('Garchomp')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '一键建队' })).toHaveAttribute(
      'href',
      '/teams?fromTournament=6&eventTeam=11',
    )

    // 使用率
    await user.click(screen.getByRole('tab', { name: /使用率/ }))
    expect(await screen.findByText('100.00%')).toBeInTheDocument()

    // 名次
    await user.click(screen.getByRole('tab', { name: /名次/ }))
    expect(await screen.findByText('Kyle Livinghouse')).toBeInTheDocument()
    expect(screen.getByText('有队表')).toBeInTheDocument()
  })

  it('links back to the list', async () => {
    renderPage()
    expect(await screen.findByRole('link', { name: /返回赛事列表/ })).toHaveAttribute(
      'href',
      '/tournaments',
    )
  })
})
