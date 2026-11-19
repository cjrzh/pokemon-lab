/**
 * 历史使用率页：单条目同步。
 *
 * 场景：选中的规则还没同步（`months === 0` / 当前快照 `has_snapshot === false`）
 * 时，页面要能只同步这个规则，而不是必须跑「全部格式」的同步。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { UsageFormatInfo, UsageHistoryQuery } from '@/features/usage-history/api'

const state = vi.hoisted(() => ({
  syncPayloads: [] as unknown[],
  /** 当前选中的格式是否已有数据 */
  formatMonths: 18,
  hasSnapshot: true,
  /** 「最近一次同步」记录（刷新页面后轮询用） */
  activeRun: null as null | {
    id: number
    status: string
    total: number
    done: number
    created: number
    skipped: number
    failed: number
    current: string | null
    message: string | null
    scope: Record<string, unknown>
    started_at: string | null
    finished_at: string | null
  },
}))

const formats: UsageFormatInfo[] = [
  {
    format_id: 'gen8vgc2022',
    label: '剑盾 VGC 2022',
    game: '剑盾',
    ruleset: 'VGC 2022',
    kind: 'vgc',
    months: 18,
  },
  {
    format_id: 'gen6vgc2014',
    label: 'XY VGC 2014',
    game: 'XY',
    ruleset: 'VGC 2014',
    kind: 'vgc',
    months: 0,
  },
]

function makeData(): UsageHistoryQuery {
  // 状态一：规则完全未同步（连可选月份都没有）
  if (state.formatMonths === 0) {
    return {
      format_id: 'gen6vgc2014',
      format_label: 'XY VGC 2014',
      game: 'XY',
      ruleset: 'VGC 2014',
      month: '',
      cutoff: 1630,
      battles: 0,
      has_snapshot: false,
      total: 0,
      page: 1,
      page_size: 50,
      total_pages: 1,
      items: [],
      months: [],
      formats: formats.map((fmt) =>
        fmt.format_id === 'gen6vgc2014' ? { ...fmt, months: state.formatMonths } : fmt,
      ),
      cutoffs: [1500, 1630, 1760],
    }
  }
  return {
    format_id: 'gen6vgc2014',
    format_label: 'XY VGC 2014',
    game: 'XY',
    ruleset: 'VGC 2014',
    month: '2014-11',
    cutoff: 1630,
    battles: 1200,
    has_snapshot: state.hasSnapshot,
    total: state.hasSnapshot ? 1 : 0,
    page: 1,
    page_size: 50,
    total_pages: 1,
    items: state.hasSnapshot
      ? [
          {
            rank: 1,
            showdown_name: 'Kangaskhan',
            dex_number: 115,
            name_zh: '袋兽',
            name_en: 'kangaskhan',
            types: ['normal'],
            sprite_url: null,
            usage: 40.2,
            raw_count: 500,
          },
        ]
      : [],
    months: ['2014-11'],
    formats: formats.map((fmt) =>
      fmt.format_id === 'gen6vgc2014' ? { ...fmt, months: state.formatMonths } : fmt,
    ),
    cutoffs: [1500, 1630, 1760],
  }
}

vi.mock('@/features/usage-history/hooks', () => ({
  useUsageHistory: () => ({
    isPending: false,
    isError: false,
    data: makeData(),
    refetch: vi.fn(),
  }),
  useActiveSyncRun: () => ({
    latest: { data: null, isPending: false },
    run: state.activeRun,
  }),
  useStartSync: () => ({
    mutate: (payload: unknown, options?: { onSuccess?: (run: unknown) => void }) => {
      state.syncPayloads.push(payload)
      options?.onSuccess?.({ id: 7, status: 'running', total: 0, done: 0 })
    },
    isPending: false,
    error: null,
  }),
  useCancelSync: () => ({ mutate: vi.fn(), isPending: false }),
  useRefreshUsageHistory: () => vi.fn(),
}))

vi.mock('@/features/dex/hooks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/dex/hooks')>()
  return { ...actual, useDebouncedValue: (value: string) => value }
})

const { UsageHistoryPage } = await import('@/pages/UsageHistoryPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <UsageHistoryPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  state.syncPayloads = []
  state.formatMonths = 0
  state.hasSnapshot = false
  state.activeRun = null
})

describe('UsageHistoryPage 单条目同步', () => {
  it('规则未同步时提供「同步本规则」，只提交该规则', async () => {
    renderPage()

    expect(screen.getByText('该规则还没同步')).toBeInTheDocument()
    // 未同步时连月份都没有，单快照按钮禁用
    expect(screen.getByRole('button', { name: /只同步这个快照/ })).toBeDisabled()

    // 顶部按钮与空态按钮都能触发（两个入口），取第一个
    await userEvent.click(screen.getAllByRole('button', { name: /同步本规则/ })[0])

    expect(state.syncPayloads).toEqual([{ format_ids: ['gen6vgc2014'] }])
  })

  it('已有部分月份时按钮变成「补齐本规则」，仍然只同步该规则', async () => {
    state.formatMonths = 3
    state.hasSnapshot = true
    renderPage()

    expect(screen.getByText('已同步 3 个月')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /补齐本规则/ }))

    expect(state.syncPayloads).toEqual([{ format_ids: ['gen6vgc2014'] }])
  })

  it('当前快照尚未同步时显示提示，并可只同步这一个快照', async () => {
    state.formatMonths = 18
    state.hasSnapshot = false
    renderPage()

    expect(screen.getByText(/该快照尚未同步/)).toBeInTheDocument()
    // 规则已有历史数据，但当前选中的月份 / 等级线还没抓 → 可以单独同步它
    expect(screen.getByRole('button', { name: /只同步这个快照/ })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: /只同步这个快照/ }))

    expect(state.syncPayloads).toEqual([
      { format_ids: ['gen6vgc2014'], months: ['2014-11'], cutoffs: [1630] },
    ])
  })
})
