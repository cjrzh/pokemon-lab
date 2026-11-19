/**
 * Showdown 导入对话框测试：解析 → 预览 → 确认；错误与 Esc 关闭。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ calls: [] as unknown[] }))

vi.mock('@/features/teams/hooks', () => ({
  useImportTeam: () => ({
    mutateAsync: async (payload: unknown) => {
      state.calls.push(payload)
      return {
        format_key: 'sv',
        members: [
          {
            dex_number: 6,
            showdown_name: 'Charizard',
            item: 'Life Orb',
            ability: 'Blaze',
            nature: 'timid',
            evs: [4, 0, 0, 252, 0, 252],
            ivs: [31, 31, 31, 31, 31, 31],
            moves: ['Flamethrower'],
            tera_type: 'Fire',
            gender: 'F',
            shiny: true,
            level: null,
          },
        ],
        problems: ['无法识别「Foo」对应的图鉴编号，已跳过'],
        warnings: [],
      }
    },
    isPending: false,
  }),
}))

const { ShowdownImportDialog } = await import('@/features/teams/ShowdownImportDialog')

function setup({ usedDex = [] }: { usedDex?: number[] } = {}) {
  const onImported = vi.fn()
  const onClose = vi.fn()
  render(
    <ShowdownImportDialog
      formatKey="sv"
      usedDex={usedDex}
      teamSize={6}
      onImported={onImported}
      onClose={onClose}
    />,
  )
  return { onImported, onClose }
}

describe('ShowdownImportDialog', () => {
  it('解析后展示成员与跳过原因，确认才回调', async () => {
    const { onImported, onClose } = setup()

    await userEvent.type(screen.getByRole('textbox', { name: 'Showdown 队伍代码' }), 'Charizard')
    expect(onImported).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))

    expect(state.calls[0]).toEqual({ format_key: 'sv', text: 'Charizard' })
    expect(await screen.findByText(/识别到 1 只，可加入 1 只/)).toBeInTheDocument()
    expect(screen.getByText('#6 Charizard @ Life Orb')).toBeInTheDocument()
    expect(screen.getByText(/Foo/)).toBeInTheDocument()

    // 解析阶段还没导入
    expect(onImported).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /加入队伍（1 只）/ }))
    expect(onImported).toHaveBeenCalledWith([
      expect.objectContaining({ dex_number: 6, showdown_name: 'Charizard' }),
    ])
    expect(onClose).toHaveBeenCalled()
  })

  it('已在队伍里的宝可梦会被跳过，只加入新的', async () => {
    const { onImported } = setup({ usedDex: [6] })

    await userEvent.type(screen.getByRole('textbox', { name: 'Showdown 队伍代码' }), 'Charizard')
    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))

    expect(await screen.findByText(/已经在队伍里，跳过/)).toBeInTheDocument()
    expect(screen.getByText(/没有可加入的成员/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /加入队伍（0 只）/ })).toBeDisabled()
    expect(onImported).not.toHaveBeenCalled()
  })

  it('未输入内容时解析按钮不可点', () => {
    setup()
    expect(screen.getByRole('button', { name: /^解析$/ })).toBeDisabled()
  })

  it('按 Esc 关闭对话框', async () => {
    const { onClose } = setup()
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })

  it('点关闭按钮回调 onClose', async () => {
    const { onClose } = setup()
    await userEvent.click(screen.getByRole('button', { name: '关闭' }))
    expect(onClose).toHaveBeenCalled()
  })
})
