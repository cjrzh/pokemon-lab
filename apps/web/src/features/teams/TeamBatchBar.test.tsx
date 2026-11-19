/**
 * 批量设置条测试：闪光 / 等级 / 性别的请求体，以及「保持原样」提示。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ calls: [] as unknown[] }))

vi.mock('@/features/teams/hooks', () => ({
  useBatchTeamMembers: () => ({
    mutateAsync: async (payload: unknown) => {
      state.calls.push(payload)
      return {
        members: [],
        skipped: ['#32 Nidoran-M 只能为雄性，保持原样'],
      }
    },
    isPending: false,
  }),
}))

const { BatchSkippedNotice, TeamBatchBar } = await import('@/features/teams/TeamBatchBar')

const members = [
  {
    position: 0,
    dex_number: 6,
    showdown_name: 'Charizard',
    evs: [0, 0, 0, 0, 0, 0],
    moves: [],
  },
  {
    position: 1,
    dex_number: 32,
    showdown_name: 'Nidoran-M',
    evs: [0, 0, 0, 0, 0, 0],
    moves: [],
  },
]

function renderBar() {
  const onApplied = vi.fn()
  render(<TeamBatchBar members={members} onApplied={onApplied} />)
  return { onApplied }
}

describe('TeamBatchBar', () => {
  it('全部闪光只发 shine:true', async () => {
    const { onApplied } = renderBar()
    await userEvent.click(screen.getByRole('button', { name: '全部闪光' }))

    expect(state.calls[0]).toMatchObject({ shine: true })
    expect(state.calls[0]).toMatchObject({ members })
    expect(onApplied).toHaveBeenCalledWith([], expect.any(Array))
  })

  it('全部不闪发 shine:false', async () => {
    renderBar()
    await userEvent.click(screen.getByRole('button', { name: '全部不闪' }))
    expect(state.calls.at(-1)).toMatchObject({ shine: false })
  })

  it('性别按钮发对应值；「不指定」显式发 null', async () => {
    renderBar()
    await userEvent.click(screen.getByRole('button', { name: /全 ♂/ }))
    expect(state.calls.at(-1)).toMatchObject({ gender: 'M' })

    await userEvent.click(screen.getByRole('button', { name: /全 ♀/ }))
    expect(state.calls.at(-1)).toMatchObject({ gender: 'F' })

    await userEvent.click(screen.getByRole('button', { name: '性别不指定' }))
    expect(state.calls.at(-1)).toMatchObject({ gender: null })
  })

  it('等级默认 100，可直接套用', async () => {
    renderBar()
    const input = screen.getByRole('spinbutton', { name: '批量等级' })
    expect(input).toHaveValue(100)

    await userEvent.click(screen.getByRole('button', { name: '套用' }))
    expect(state.calls.at(-1)).toMatchObject({ level: 100 })
  })

  it('等级可改后套用与恢复默认', async () => {
    renderBar()
    const input = screen.getByRole('spinbutton', { name: '批量等级' })
    await userEvent.clear(input)
    await userEvent.type(input, '50')
    await userEvent.click(screen.getByRole('button', { name: '套用' }))
    expect(state.calls.at(-1)).toMatchObject({ level: 50 })

    await userEvent.click(screen.getByRole('button', { name: '恢复默认等级' }))
    expect(state.calls.at(-1)).toMatchObject({ level: null })
  })

  it('没有成员时按钮全部禁用', () => {
    render(<TeamBatchBar members={[]} onApplied={vi.fn()} />)
    expect(screen.getByRole('button', { name: '全部闪光' })).toBeDisabled()
  })
})

describe('BatchSkippedNotice', () => {
  it('列出保持原样的原因', () => {
    render(<BatchSkippedNotice skipped={['#32 Nidoran-M 只能为雄性，保持原样']} />)
    expect(screen.getByText(/按性别规则保持原样/)).toBeInTheDocument()
    expect(screen.getByText(/#32 Nidoran-M/)).toBeInTheDocument()
  })

  it('没有跳过项时不渲染', () => {
    const { container } = render(<BatchSkippedNotice skipped={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
