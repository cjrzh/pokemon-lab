/**
 * 队伍评价面板测试：流式渲染、AI 不可用时的降级、按需触发，
 * 以及「已保存队伍 → 落库更新」与「草稿 → 不落库」两条路径的分流。
 *
 * 面板现在消费 `useStreamTeamAnalysis`（SSE 边收边显示），所以这里用可控的假流：
 * 把 `state.events` 依次喂进去，断言中间态与最终态。
 */

import { useCallback, useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { TeamAnalysis, TeamAnalysisEvent, TeamMemberInput } from '@/features/teams/api'

const state = vi.hoisted(() => ({
  calls: [] as unknown[],
  events: [] as unknown[],
}))

/** 可控的假流：`start` 记录调用参数，并把 `state.events` 依次派发。 */
function useStreamMock() {
  const [running, setRunning] = useState(false)
  const [coverage, setCoverage] = useState<TeamAnalysis | null>(null)
  const [text, setText] = useState('')
  const [model, setModel] = useState<string | null>(null)
  const [llmError, setLlmError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(async (params: { teamId?: number | null; useLlm: boolean }) => {
    state.calls.push(params)
    setRunning(true)
    setCoverage(null)
    setText('')
    setModel(null)
    setLlmError(null)
    setError(null)
    for (const raw of state.events as TeamAnalysisEvent[]) {
      switch (raw.event) {
        case 'coverage':
          setCoverage(raw.data)
          break
        case 'delta':
          setText((prev) => prev + raw.text)
          if (raw.model) setModel(raw.model)
          break
        case 'done':
          if (raw.text) setText(raw.text)
          if (raw.model) setModel(raw.model)
          break
        case 'error':
          setLlmError(raw.text)
          break
      }
    }
    setRunning(false)
  }, [])

  const stop = useCallback(() => setRunning(false), [])
  return { start, stop, running, coverage, text, model, llmError, error }
}

vi.mock('@/features/teams/hooks', () => ({
  useStreamTeamAnalysis: () => useStreamMock(),
}))

const { TeamAnalysisPanel } = await import('@/features/teams/TeamAnalysisPanel')

const members: TeamMemberInput[] = [
  { dex_number: 6, showdown_name: 'Charizard', evs: [0, 0, 0, 0, 0, 0], moves: [] },
]

/** 计算部分（coverage 事件与落库评价共用）。 */
const coverage: TeamAnalysis = {
  members: [{ dex_number: 6, name: '喷火龙', types: ['fire', 'flying'] }],
  attack: [
    {
      type: 'fire',
      type_zh: '火',
      hits: ['grass', 'bug'],
      hits_zh: ['草', '虫'],
      member_count: 1,
    },
  ],
  gaps: ['water', 'dragon'],
  gaps_zh: ['水', '龙'],
  hotspots: [{ type: 'electric', type_zh: '电', members: [6, 9] }],
  llm: null,
  llm_error: null,
}

const aiText = '## 队伍评价\n偏特攻。\n## 改进建议\n- 补一个水系\n- 加地面系控电'

function setup(
  events: TeamAnalysisEvent[],
  props: Partial<React.ComponentProps<typeof TeamAnalysisPanel>> = {},
) {
  state.events = events
  state.calls.length = 0
  render(<TeamAnalysisPanel formatKey="sv" memberInputs={members} disabled={false} {...props} />)
}

/** 带 AI 建议的落库评价。 */
function stored(overrides: Partial<{ stale: boolean; generated_at: string }> = {}) {
  return {
    analysis: { ...coverage, llm: { text: aiText, model: 'test-model' } },
    generated_at: '2026-11-04T10:30:00',
    stale: false,
    ...overrides,
  }
}

describe('TeamAnalysisPanel（草稿）', () => {
  it('不自动请求，点按钮才分析', async () => {
    setup([
      { event: 'coverage', data: coverage },
      { event: 'done', text: aiText, model: 'test-model' },
    ])
    expect(state.calls).toHaveLength(0)

    await userEvent.click(screen.getByRole('button', { name: /生成评价/ }))
    expect(state.calls[0]).toMatchObject({ useLlm: true })
  })

  it('「只看数据」不调用 LLM', async () => {
    setup([{ event: 'coverage', data: coverage }, { event: 'done', text: '', model: null }])
    await userEvent.click(screen.getByRole('button', { name: '只看数据' }))
    expect(state.calls.at(-1)).toMatchObject({ useLlm: false })
  })

  it('流式渲染打击面 / 缺失面 / 共同弱点与 AI 正文', async () => {
    setup([
      { event: 'coverage', data: coverage },
      { event: 'delta', text: '## 队伍评价\n偏特攻。\n', model: 'test-model' },
      { event: 'delta', text: '## 改进建议\n- 补一个水系\n- 加地面系控电', model: 'test-model' },
      { event: 'done', text: aiText, model: 'test-model' },
    ])
    await userEvent.click(screen.getByRole('button', { name: /生成评价/ }))

    expect(await screen.findByText('打击面')).toBeInTheDocument()
    expect(screen.getByText('缺失面')).toBeInTheDocument()
    expect(screen.getByText('#6、#9')).toBeInTheDocument()
    expect(screen.getByText('补一个水系')).toBeInTheDocument()
    expect(screen.getByText('加地面系控电')).toBeInTheDocument()
    expect(screen.getByText('test-model')).toBeInTheDocument()
  })

  it('AI 不可用时提示原因，但保留计算结果', async () => {
    setup([
      { event: 'coverage', data: coverage },
      { event: 'error', text: 'HTTP 503' },
    ])
    await userEvent.click(screen.getByRole('button', { name: /生成评价/ }))

    expect(await screen.findByText(/AI 建议暂不可用/)).toBeInTheDocument()
    expect(screen.getByText(/HTTP 503/)).toBeInTheDocument()
    // 计算部分照常展示
    expect(screen.getByText('打击面')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重试/ })).toBeInTheDocument()
  })
})

describe('TeamAnalysisPanel（已保存队伍）', () => {
  it('已存评价直接显示，按钮是「更新评价」', () => {
    setup([], { teamId: 7, storedAnalysis: stored() })

    expect(screen.getByText('打击面')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /更新评价/ })).toBeInTheDocument()
  })

  it('点「更新评价」走落库路径（带 teamId）', async () => {
    setup(
      [
        { event: 'coverage', data: coverage },
        { event: 'done', text: aiText, model: 'test-model' },
      ],
      { teamId: 7, storedAnalysis: stored() },
    )

    await userEvent.click(screen.getByRole('button', { name: /更新评价/ }))
    await waitFor(() => expect(state.calls[0]).toMatchObject({ teamId: 7, useLlm: true }))
  })

  it('队伍改动过时提示评价已过期', () => {
    setup([], { teamId: 7, storedAnalysis: stored({ stale: true }) })
    expect(screen.getByText(/评价已过期/)).toBeInTheDocument()
  })

  it('有未保存改动时不显示旧评价', () => {
    setup([], { teamId: 7, dirty: true, storedAnalysis: stored() })

    expect(screen.queryByText('打击面')).not.toBeInTheDocument()
    expect(screen.getByText(/先点「保存」/)).toBeInTheDocument()
  })
})

describe('TeamAnalysisPanel 空队伍', () => {
  it('没有成员时按钮禁用', () => {
    render(<TeamAnalysisPanel formatKey="sv" memberInputs={[]} disabled />)
    expect(screen.getByRole('button', { name: /生成评价/ })).toBeDisabled()
    expect(screen.getByText('先加入宝可梦')).toBeInTheDocument()
  })
})
