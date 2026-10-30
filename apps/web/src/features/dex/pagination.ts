/**
 * 分页页码的纯函数（便于单测）。
 *
 * 规则：总页数不多时全部显示；较多时固定「首页 / 末页」，
 * 中间围绕当前页展开 5 个页码，缺口用省略号表示。
 */

export type PageItem = number | 'ellipsis'

export function pageItems(current: number, total: number): PageItem[] {
  if (total <= 1) return [1]
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)

  const left = Math.max(2, current - 2)
  const right = Math.min(total - 1, current + 2)
  const items: PageItem[] = [1]
  if (left > 2) items.push('ellipsis')
  for (let page = left; page <= right; page += 1) items.push(page)
  if (right < total - 1) items.push('ellipsis')
  items.push(total)
  return items
}

/** 当前页对应的条目区间，如第 2 页、每页 24 条 → `25–48`。 */
export function pageRange(current: number, pageSize: number, total: number): [number, number] {
  if (total === 0) return [0, 0]
  const start = (current - 1) * pageSize + 1
  const end = Math.min(total, current * pageSize)
  return [start, end]
}
