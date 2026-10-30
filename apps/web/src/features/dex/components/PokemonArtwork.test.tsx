import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PokemonArtwork } from '@/features/dex/components/PokemonArtwork'
import { TypeMatchup } from '@/features/dex/components/TypeMatchup'
import { statTotal } from '@/features/dex/components/stats'
import { resolveMediaUrl } from '@/features/dex/api'

describe('resolveMediaUrl', () => {
  it('保留绝对地址', () => {
    expect(resolveMediaUrl('https://example.com/a.png')).toBe('https://example.com/a.png')
  })

  it('相对路径保持同源（默认部署同源代理）', () => {
    expect(resolveMediaUrl('/media/artwork/1.png')).toBe('/media/artwork/1.png')
  })

  it('空值返回 undefined', () => {
    expect(resolveMediaUrl(null)).toBeUndefined()
    expect(resolveMediaUrl(undefined)).toBeUndefined()
    expect(resolveMediaUrl('')).toBeUndefined()
  })
})

describe('stat helpers', () => {
  it('合计只统计六项', () => {
    expect(
      statTotal({
        hp: 45,
        attack: 49,
        defense: 49,
        'special-attack': 65,
        'special-defense': 65,
        speed: 45,
        unrelated: 999,
      }),
    ).toBe(318)
  })
})

describe('PokemonArtwork', () => {
  it('渲染主图并带可访问名称', () => {
    render(
      <PokemonArtwork
        src="/media/artwork/1.png"
        fallbackSrc="https://example.com/1.png"
        alt="妙蛙种子"
      />,
    )
    const image = screen.getByRole('img', { name: '妙蛙种子' })
    expect(image).toHaveAttribute('src', '/media/artwork/1.png')
  })

  it('主图加载失败后回落到兜底地址', async () => {
    render(
      <PokemonArtwork
        src="/media/artwork/1.png"
        fallbackSrc="https://example.com/1.png"
        alt="妙蛙种子"
      />,
    )
    const image = screen.getByRole('img', { name: '妙蛙种子' })
    image.dispatchEvent(new Event('error'))
    await waitFor(() => {
      expect(image).toHaveAttribute('src', 'https://example.com/1.png')
    })
  })

  it('没有图片时显示占位而不是伪造图片', () => {
    render(<PokemonArtwork src={null} fallbackSrc={null} alt="妙蛙种子" variant="hero" />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('暂无立绘')).toBeInTheDocument()
  })
})

describe('TypeMatchup', () => {
  it('按倍率分组展示双属性的弱点', () => {
    render(<TypeMatchup types={['grass', 'poison']} />)

    // 妙蛙种子（草/毒）：火、冰、飞行、超能力为 2× 弱点。
    // 具体倍率由 engine.test.ts 的共享测试向量覆盖，这里只验证分组渲染。
    expect(screen.getByText('2× 弱点')).toBeInTheDocument()
    expect(screen.getByText('火')).toBeInTheDocument()
    expect(screen.getByText('1/2× 抗性')).toBeInTheDocument()
  })
})

describe('STAT_COLOR', () => {
  it('每个种族值项目都有独立的颜色类，且互不相同', async () => {
    const { STAT_COLOR, STAT_ORDER } = await import('@/features/dex/components/stats')
    const bars = STAT_ORDER.map((key) => STAT_COLOR[key].bar)
    expect(new Set(bars).size).toBe(6)
    for (const key of STAT_ORDER) {
      expect(STAT_COLOR[key].bar).toMatch(/^bg-stat-/)
      expect(STAT_COLOR[key].text).toMatch(/^text-stat-/)
    }
  })
})
