/**
 * 队伍成员排序的纯函数（拖动排序用）。
 *
 * 位置即列表顺序：移动后统一用 `withPositions` 重排 `position`。
 * 抽出纯函数是为了单测边界（向前/向后移动、越界、同位置），
 * 也避免在组件里手写 splice 的 off-by-one。
 */

import type { TeamMember } from '@/features/teams/api'
import { withPositions } from '@/features/teams/draft'

/**
 * 把 `from` 位置的成员移动到 `to` 位置（`to` 是移动后它在列表里的下标）。
 *
 * 越界或原位移动返回原数组（引用不变，调用方可据此跳过 setState）。
 *
 * 例：`[A,B,C,D]`，move(0, 2) → `[B,C,A,D]`；move(3, 1) → `[A,D,B,C]`。
 */
export function moveMember(members: TeamMember[], from: number, to: number): TeamMember[] {
  if (from === to) return members
  if (from < 0 || from >= members.length) return members
  if (to < 0 || to >= members.length) return members

  const next = members.slice()
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return withPositions(next)
}

/** 上移一位（到顶时原样返回）。 */
export function moveMemberUp(members: TeamMember[], index: number): TeamMember[] {
  return moveMember(members, index, index - 1)
}

/** 下移一位（到底时原样返回）。 */
export function moveMemberDown(members: TeamMember[], index: number): TeamMember[] {
  return moveMember(members, index, index + 1)
}

/**
 * 通用版：移动任意列表的一项（队伍列表用它）。
 *
 * 与 `moveMember` 的区别是不重写 `position` —— 队伍的顺序由后端
 * `sort_order` 决定，前端只负责把新顺序交给接口。
 */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  if (from === to) return items
  if (from < 0 || from >= items.length) return items
  if (to < 0 || to >= items.length) return items
  const next = items.slice()
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}

/**
 * 只对列表的一个子集排序时，把子集的新顺序合并回完整列表。
 *
 * 建队页支持按版本筛选队伍：拖动发生在筛选后的子列表里，但保存需要完整顺序。
 * 做法：完整列表里属于子集的槽位，按子集的新顺序依次填充，其余元素原地不动。
 */
export function mergeSubsetOrder<T extends { id: number }>(
  all: T[],
  subsetOrder: T[],
): T[] {
  const subsetIds = new Set(subsetOrder.map((item) => item.id))
  let cursor = 0
  return all.map((item) => {
    if (!subsetIds.has(item.id)) return item
    const replacement = subsetOrder[cursor]
    cursor += 1
    return replacement
  })
}
