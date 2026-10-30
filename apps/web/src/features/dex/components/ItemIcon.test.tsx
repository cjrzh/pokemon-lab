/**
 * 道具图标组件测试：正常渲染、加载失败回落占位、无地址时显示占位。
 */

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ItemIcon } from './ItemIcon'

describe('ItemIcon', () => {
  it('有地址时渲染图片', () => {
    render(<ItemIcon src="/media/items/sitrus-berry.png" alt="文柚果" />)

    expect(screen.getByRole('img', { name: '文柚果' })).toHaveAttribute(
      'src',
      '/media/items/sitrus-berry.png',
    )
  })

  it('加载失败后移除图片，保留占位', () => {
    render(<ItemIcon src="/media/items/sitrus-berry.png" alt="文柚果" />)

    fireEvent.error(screen.getByRole('img', { name: '文柚果' }))

    expect(screen.queryByRole('img', { name: '文柚果' })).not.toBeInTheDocument()
  })

  it('没有地址时不渲染图片', () => {
    render(<ItemIcon src={null} alt="文柚果" />)

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
