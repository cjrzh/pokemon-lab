/**
 * 小图标组件测试：正常渲染、加载失败回落占位、无地址时显示色点。
 */

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PokemonSprite } from './PokemonSprite'

describe('PokemonSprite', () => {
  it('有地址时渲染图片并带上 alt', () => {
    render(<PokemonSprite src="/media/sprites/25.png" alt="皮卡丘" type="electric" />)

    const image = screen.getByRole('img', { name: '皮卡丘' })
    expect(image).toHaveAttribute('src', '/media/sprites/25.png')
  })

  it('图片加载失败后显示属性色占位点，不再重复加载', () => {
    render(<PokemonSprite src="/media/sprites/25.png" alt="皮卡丘" type="electric" />)

    fireEvent.error(screen.getByRole('img', { name: '皮卡丘' }))

    expect(screen.queryByRole('img', { name: '皮卡丘' })).not.toBeInTheDocument()
  })

  it('没有地址时直接显示占位点', () => {
    render(<PokemonSprite src={null} alt="皮卡丘" type="electric" />)

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
