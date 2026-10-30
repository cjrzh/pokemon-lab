import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { TypeMatchup } from '@/features/dex/components/TypeMatchup'
import { typeChart } from '@/features/type-chart/data'
import { attackProfile } from '@/features/type-chart/engine'

describe('attackProfile', () => {
  it('火属性攻击草属性是 2×，攻击水/火属性是 1/2×', () => {
    const profile = attackProfile('fire', typeChart)
    expect(profile.get('grass')).toBe(2)
    expect(profile.get('water')).toBe(0.5)
    expect(profile.get('fire')).toBe(0.5)
  })

  it('一般属性攻击幽灵属性无效（0×）', () => {
    expect(attackProfile('normal', typeChart).get('ghost')).toBe(0)
  })

  it('返回全部 18 种防守属性（含中性项）', () => {
    expect(attackProfile('water', typeChart).size).toBe(18)
  })

  it('未知属性抛错（配置错误）', () => {
    expect(() => attackProfile('shadow', typeChart)).toThrow('不在克制表中')
  })
})

describe('TypeMatchup 双视角', () => {
  it('默认显示受击视角', () => {
    render(<TypeMatchup types={['grass', 'poison']} />)
    expect(screen.getByRole('button', { name: '受击' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('2× 弱点')).toBeInTheDocument()
    expect(screen.getByText('1/2× 抗性')).toBeInTheDocument()
  })

  it('切换到出击视角后显示攻击倍率，双属性各一行', async () => {
    const user = userEvent.setup()
    render(<TypeMatchup types={['grass', 'poison']} />)

    await user.click(screen.getByRole('button', { name: '出击' }))

    const panel = screen.getByRole('group', { name: '切换属性相性视角' })
    expect(within(panel).getByRole('button', { name: '出击' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    // 草、毒两种自身属性各一个分组
    expect(screen.getAllByText('属性招式对以下属性的倍率')).toHaveLength(2)
    // 两种属性都可能有相同档位，用 getAllByText 验证存在性
    expect(screen.getAllByText('2× 效果绝佳').length).toBeGreaterThan(0)
    expect(screen.getAllByText('1/2× 效果不佳').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0× 无效').length).toBeGreaterThan(0)
  })

  it('可以切回受击视角', async () => {
    const user = userEvent.setup()
    render(<TypeMatchup types={['fire']} />)

    await user.click(screen.getByRole('button', { name: '出击' }))
    await user.click(screen.getByRole('button', { name: '受击' }))

    expect(screen.getByText('2× 弱点')).toBeInTheDocument()
  })

  it('单属性的进攻面只渲染一个分组', async () => {
    const user = userEvent.setup()
    render(<TypeMatchup types={['electric']} />)
    await user.click(screen.getByRole('button', { name: '出击' }))

    expect(screen.getAllByText('属性招式对以下属性的倍率')).toHaveLength(1)
    // 电打地面无效
    expect(screen.getAllByText('0× 无效').length).toBeGreaterThan(0)
  })
})
