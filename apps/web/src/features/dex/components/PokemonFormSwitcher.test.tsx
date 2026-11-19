/**
 * 形态切换菜单测试：渲染默认 + 其它形态、点击切换、属性徽章与图标。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PokemonFormSwitcher } from './PokemonFormSwitcher'
import type { PokemonFormSummary } from '../api'

const forms: PokemonFormSummary[] = [
  {
    name: 'urshifu-single-strike',
    label: '武道熊师',
    zh: null,
    name_en: null,
    types: ['fighting', 'dark'],
    is_default: true,
    sprite_url: '/media/sprites/892.png',
  },
  {
    name: 'urshifu-rapid-strike',
    label: '连击流',
    zh: '连击流',
    name_en: 'Rapid Strike Urshifu',
    types: ['fighting', 'water'],
    is_default: false,
    sprite_url: '/media/forms/sprites/urshifu-rapid-strike.png',
  },
]

describe('PokemonFormSwitcher', () => {
  it('列出全部形态并标出当前形态', () => {
    render(
      <PokemonFormSwitcher
        forms={forms}
        active="urshifu-single-strike"
        onSelect={vi.fn()}
        spriteUrl={(path) => path ?? undefined}
      />,
    )

    expect(screen.getByText('形态（2）')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /武道熊师/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: /连击流/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    // 每个形态都带自己的小图标
    expect(screen.getByRole('img', { name: '连击流' })).toHaveAttribute(
      'src',
      '/media/forms/sprites/urshifu-rapid-strike.png',
    )
  })

  it('点击形态时回调对应 slug', async () => {
    const onSelect = vi.fn()
    render(
      <PokemonFormSwitcher
        forms={forms}
        active="urshifu-single-strike"
        onSelect={onSelect}
        spriteUrl={(path) => path ?? undefined}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: /连击流/ }))
    expect(onSelect).toHaveBeenCalledWith('urshifu-rapid-strike')
  })

  it('只有一个形态时不渲染菜单', () => {
    const { container } = render(
      <PokemonFormSwitcher forms={[forms[0]]} active={forms[0].name} onSelect={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
