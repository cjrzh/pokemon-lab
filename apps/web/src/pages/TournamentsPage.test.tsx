/**
 * 官方赛事页：列表、详情、同步与「一键建队」入口的交互测试。
 *
 * 不连真实网络：fetch 全部用 vi.mock 替换成固定响应。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { TournamentsPage } from '@/pages/TournamentsPage'

const event = {
  id: 1,
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
  standings_count: 1,
  team_count: 1,
  has_teamlists: true,
  source_url: 'https://limitlessvgc.com/tournaments/448',
}

const detail = {
  tournament: event,
  standings: [
    { rank: 1, player: 'Javier Varela', country: 'ES', species: ['Gholdengo'], team_id: 7472 },
  ],
  teams: [
    {
      id: 11,
      rank: 1,
      player: 'Javier Varela',
      country: 'ES',
      showdown_text: 'Garchomp @ Rocky Helmet  \nAbility: Rough Skin  ',
      problems: [],
      members: [
        {
          position: 0,
          dex_number: 445,
          showdown_name: 'Garchomp',
          species_slug: 'garchomp',
          item: 'Rocky Helmet',
          ability: 'Rough Skin',
          nature: 'jolly',
          tera_type: null,
          moves: ['Earthquake', 'Rock Slide', 'Dragon Claw', 'Protect'],
        },
      ],
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
      if (url.startsWith('/tournaments/sync/latest')) return null
      if (url.startsWith('/tournaments/sync')) return null
      if (url.startsWith('/tournaments?') || url === '/tournaments') {
        return {
          items: [event],
          total: 1,
          page: 1,
          page_size: 20,
          total_pages: 1,
          years: [2026],
          rulesets: [
            { identifier: 'm-c', label: '宝可梦冠军 Reg M-C（官方赛事）', game: '宝可梦冠军', format_key: 'champions' },
          ],
        }
      }
      if (url.startsWith('/tournaments/1/teams/')) return { members: [] }
      if (url.startsWith('/tournaments/1')) return detail
      throw new Error(`unexpected ${url}`)
    }),
  }
})

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TournamentsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TournamentsPage', () => {
  it('lists events and links each one to its detail page', async () => {
    renderPage()

    expect(await screen.findByText('Regional Gdańsk')).toBeInTheDocument()
    expect(screen.getByText('758 人')).toBeInTheDocument()
    expect(screen.getByText('冠军 Javier Varela')).toBeInTheDocument()

    // 赛事名是链接（详情在独立页面，不再在列表下方展开）
    const link = screen.getByRole('link', { name: /Regional Gdańsk/ })
    expect(link).toHaveAttribute('href', '/tournaments/1')
  })

  it('renders the empty state with a sync hint', async () => {
    const { apiRequest } = await import('@/lib/apiClient')
    vi.mocked(apiRequest).mockImplementationOnce(async () => ({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 1,
      years: [],
      rulesets: [],
    }) as never)
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('还没有赛事数据。')).toBeInTheDocument(),
    )
  })
})
