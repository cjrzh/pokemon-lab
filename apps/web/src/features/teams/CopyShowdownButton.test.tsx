/**
 * 复制按钮：成功反馈、剪贴板不可用时的降级文本框。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CopyShowdownButton } from '@/features/teams/CopyShowdownButton'

const TEXT = '!tradeSV\nCharizard @ Life Orb  \nAbility: Blaze  '

describe('CopyShowdownButton', () => {
  it('点击写入剪贴板并显示已复制', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    render(<CopyShowdownButton text={TEXT} label="复制喷火龙的 Showdown 代码" />)
    await userEvent.click(screen.getByRole('button', { name: '复制喷火龙的 Showdown 代码' }))

    expect(writeText).toHaveBeenCalledWith(TEXT)
  })

  it('剪贴板失败时显示可手动复制的文本框（内容含交易前缀）', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })

    render(<CopyShowdownButton text={TEXT} label="复制喷火龙" />)
    await userEvent.click(screen.getByRole('button', { name: '复制喷火龙' }))

    const area = await screen.findByRole('textbox', { name: /手动复制/ })
    expect(area).toHaveValue(TEXT)
    expect(screen.getByText(/已带上交易前缀/)).toBeInTheDocument()
  })
})
