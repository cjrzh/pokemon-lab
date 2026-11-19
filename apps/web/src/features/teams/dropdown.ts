/**
 * 下拉面板的展开方向（纯函数，便于单测）。
 *
 * 搜索框靠近页面底部时，向下展开的面板会超出视口被浏览器裁掉。
 * 规则：下方容得下就向下；放不下且上方空间更大就向上。
 */

/** 面板的估算高度（与 `max-h-72` 对应：18rem = 288px）。 */
export const PANEL_HEIGHT = 288
/** 与视口边缘留出的最小间距。 */
const MARGIN = 8

export function shouldDropUp(
  inputBottom: number,
  inputTop: number,
  viewportHeight: number,
  panelHeight = PANEL_HEIGHT,
): boolean {
  const spaceBelow = viewportHeight - inputBottom - MARGIN
  const spaceAbove = inputTop - MARGIN
  if (spaceBelow >= panelHeight) return false
  return spaceAbove > spaceBelow
}

/** 面板的最大高度：取当前方向可用空间与标称高度的较小值。 */
export function panelMaxHeight(
  inputBottom: number,
  inputTop: number,
  viewportHeight: number,
  dropUp: boolean,
  panelHeight = PANEL_HEIGHT,
): number {
  const available = dropUp ? inputTop - MARGIN : viewportHeight - inputBottom - MARGIN
  return Math.max(96, Math.min(panelHeight, available))
}
