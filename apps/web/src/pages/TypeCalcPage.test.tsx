/**
 * 属性克制页测试：倍率计算、谁克我、进攻速查与属性筛选。
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { TypeCalcPage } from './TypeCalcPage'

describe('TypeCalcPage', () => {
  it('选择进攻与防守属性后显示最终倍率', async () => {
    render(<TypeCalcPage />)

    const attackGroup = screen.getByRole('group', { name: '进攻属性（1 个）' })
    await userEvent.click(within(attackGroup).getByRole('button', { name: '火' }))

    const defenseGroup = screen.getByRole('group', { name: '防守属性（1–2 个）' })
    await userEvent.click(within(defenseGroup).getByRole('button', { name: '草' }))
    await userEvent.click(within(defenseGroup).getByRole('button', { name: '冰' }))

    expect(screen.getByLabelText('最终倍率')).toHaveTextContent('4×')
  })

  it('免疫时显示「无效（免疫）」', async () => {
    render(<TypeCalcPage />)

    await userEvent.click(
      within(screen.getByRole('group', { name: '进攻属性（1 个）' })).getByRole('button', {
        name: '一般',
      }),
    )
    await userEvent.click(
      within(screen.getByRole('group', { name: '防守属性（1–2 个）' })).getByRole('button', {
        name: '幽灵',
      }),
    )

    expect(screen.getByLabelText('最终倍率')).toHaveTextContent('无效（免疫）')
  })

  it('防守属性最多两个：第三次点击替换最早的一个', async () => {
    render(<TypeCalcPage />)

    const defenseGroup = screen.getByRole('group', { name: '防守属性（1–2 个）' })
    await userEvent.click(within(defenseGroup).getByRole('button', { name: '草' }))
    await userEvent.click(within(defenseGroup).getByRole('button', { name: '火' }))
    await userEvent.click(within(defenseGroup).getByRole('button', { name: '水' }))

    // 草被替换：草、火按钮回到未选中
    expect(within(defenseGroup).getByRole('button', { name: '草' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(within(defenseGroup).getByRole('button', { name: '火' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(within(defenseGroup).getByRole('button', { name: '水' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('谁克我：选择防守属性后按倍率分组显示攻击属性', async () => {
    render(<TypeCalcPage />)

    const picker = screen.getByRole('group', { name: '受击属性（1–2 个）' })
    await userEvent.click(within(picker).getByRole('button', { name: '火' }))

    // 火属性受击：地面 2×、水 2×、岩石 2×，且有抗性分组
    expect(screen.getByText('谁克我（受击查询）')).toBeInTheDocument()
    expect(screen.getAllByText('2×').length).toBeGreaterThan(0)
    expect(screen.getAllByText('地面').length).toBeGreaterThan(0)
  })

  it('进攻速查可筛选属性', async () => {
    render(<TypeCalcPage />)

    expect(screen.getByText('进攻速查')).toBeInTheDocument()
    expect(screen.getByTestId('offense-fire')).toBeInTheDocument()
    expect(screen.getByTestId('offense-fairy')).toBeInTheDocument()

    await userEvent.type(screen.getByRole('textbox', { name: '筛选属性' }), '火')

    expect(screen.getByTestId('offense-fire')).toBeInTheDocument()
    expect(screen.queryByTestId('offense-fairy')).not.toBeInTheDocument()
  })
})
