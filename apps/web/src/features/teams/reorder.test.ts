/**
 * 队伍排序纯函数测试：拖动 / 上移 / 下移的边界。
 */

import { describe, expect, it } from 'vitest'

import type { TeamMember } from '@/features/teams/api'
import {
  mergeSubsetOrder,
  moveItem,
  moveMember,
  moveMemberDown,
  moveMemberUp,
} from '@/features/teams/reorder'

function member(dex: number, position: number): TeamMember {
  return {
    position,
    dex_number: dex,
    showdown_name: `P${dex}`,
    evs: [0, 0, 0, 0, 0, 0],
    moves: [],
  }
}

const team = [member(1, 0), member(4, 1), member(7, 2), member(25, 3)]
const dexes = (members: TeamMember[]) => members.map((item) => item.dex_number)

describe('moveMember', () => {
  it('向前移动（后面的挪到前面）', () => {
    expect(dexes(moveMember(team, 3, 0))).toEqual([25, 1, 4, 7])
  })

  it('向后移动（前面的挪到后面）', () => {
    expect(dexes(moveMember(team, 0, 2))).toEqual([4, 7, 1, 25])
  })

  it('移动后重排 position', () => {
    expect(moveMember(team, 0, 2).map((item) => item.position)).toEqual([0, 1, 2, 3])
  })

  it('原位 / 越界时返回原数组引用', () => {
    expect(moveMember(team, 1, 1)).toBe(team)
    expect(moveMember(team, -1, 0)).toBe(team)
    expect(moveMember(team, 0, 4)).toBe(team)
    expect(moveMember(team, 4, 0)).toBe(team)
  })

  it('不改动原数组', () => {
    const before = dexes(team)
    moveMember(team, 0, 3)
    expect(dexes(team)).toEqual(before)
  })
})

describe('moveMemberUp / moveMemberDown', () => {
  it('上移一位；在顶部时原样返回', () => {
    expect(dexes(moveMemberUp(team, 2))).toEqual([1, 7, 4, 25])
    expect(moveMemberUp(team, 0)).toBe(team)
  })

  it('下移一位；在底部时原样返回', () => {
    expect(dexes(moveMemberDown(team, 1))).toEqual([1, 7, 4, 25])
    expect(moveMemberDown(team, 3)).toBe(team)
  })
})

describe('moveItem（队伍列表用）', () => {
  const items = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }]
  const ids = (list: { id: number }[]) => list.map((item) => item.id)

  it('向前 / 向后移动', () => {
    expect(ids(moveItem(items, 3, 0))).toEqual([4, 1, 2, 3])
    expect(ids(moveItem(items, 0, 2))).toEqual([2, 3, 1, 4])
  })

  it('原位 / 越界返回原引用', () => {
    expect(moveItem(items, 1, 1)).toBe(items)
    expect(moveItem(items, 0, 9)).toBe(items)
  })
})

describe('mergeSubsetOrder（筛选状态下排序）', () => {
  const all = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }]

  it('全量顺序时与原列表一致', () => {
    const reordered = [all[1], all[0], all[3], all[2]]
    expect(mergeSubsetOrder(all, reordered).map((i) => i.id)).toEqual([2, 1, 4, 3])
  })

  it('只重排子集：其它元素原地不动', () => {
    // 可见子集是 [2, 4]，调换后为 [4, 2]
    const subset = [all[3], all[1]]
    expect(mergeSubsetOrder(all, subset).map((i) => i.id)).toEqual([1, 4, 3, 2])
  })

  it('子集为空时原样返回', () => {
    expect(mergeSubsetOrder(all, []).map((i) => i.id)).toEqual([1, 2, 3, 4])
  })
})
