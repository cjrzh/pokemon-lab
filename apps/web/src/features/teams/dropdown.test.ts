/**
 * 下拉方向与高度的纯函数测试。
 */

import { describe, expect, it } from 'vitest'

import { PANEL_HEIGHT, panelMaxHeight, shouldDropUp } from '@/features/teams/dropdown'

const VIEWPORT = 800

describe('shouldDropUp', () => {
  it('下方空间充足时向下展开', () => {
    // 输入框在顶部：下方 760px
    expect(shouldDropUp(200, 160, VIEWPORT)).toBe(false)
  })

  it('下方放不下、上方更宽裕时向上展开', () => {
    // 输入框贴近底部：下方只有 40px，上方 700px
    expect(shouldDropUp(760, 720, VIEWPORT)).toBe(true)
  })

  it('上下都放不下时选空间更大的一侧', () => {
    // 中部：下方 150，上方 400
    expect(shouldDropUp(650, 610, VIEWPORT)).toBe(true)
    // 中部偏上：下方 400，上方 150
    expect(shouldDropUp(400, 360, VIEWPORT)).toBe(false)
  })
})

describe('panelMaxHeight', () => {
  it('空间充足时用标称高度', () => {
    expect(panelMaxHeight(200, 160, VIEWPORT, false)).toBe(PANEL_HEIGHT)
  })

  it('向下空间不足时收窄面板', () => {
    const height = panelMaxHeight(650, 610, VIEWPORT, false)
    expect(height).toBe(142)
  })

  it('向上展开时按上方空间计算', () => {
    expect(panelMaxHeight(760, 500, VIEWPORT, true)).toBe(PANEL_HEIGHT)
  })

  it('永远不小于可用下限', () => {
    expect(panelMaxHeight(795, 795, VIEWPORT, false)).toBe(96)
  })
})
