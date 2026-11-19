/**
 * 草稿快照比对：决定是否显示「有未保存改动」。
 *
 * 回归点：成员编辑器挂载后会自动套用推荐值并回调 onChange；
 * 若结果与已保存配置相同，不能把队伍标成脏。
 */

import { describe, expect, it } from 'vitest'

import type { TeamDetail, TeamMember } from '@/features/teams/api'
import { sameTeamContent, withPositions } from '@/features/teams/draft'

function member(overrides: Partial<TeamMember> = {}): TeamMember {
  return {
    position: 0,
    dex_number: 6,
    showdown_name: 'Charizard',
    nickname: null,
    item: 'Life Orb',
    ability: 'Blaze',
    nature: 'timid',
    evs: [4, 0, 0, 252, 0, 252],
    ivs: [31, 31, 31, 31, 31, 31],
    moves: ['Flamethrower'],
    tera_type: 'Fire',
    gender: 'F',
    shiny: true,
    level: null,
    language: 'CHS',
    ...overrides,
  }
}

function team(overrides: Partial<TeamDetail> = {}): TeamDetail {
  return {
    id: 7,
    name: '雨天队',
    format_key: 'sv',
    format_label: '朱紫',
    note: null,
    member_count: 1,
    updated_at: '2026-11-04T00:00:00',
    members: [member()],
    trade_prefix: '!tradeSV',
    default_level: 50,
    points_kind: 'ev',
    analysis: null,
    ...overrides,
  }
}

describe('sameTeamContent', () => {
  it('内容相同即视为无改动（updated_at / analysis 变化不算）', () => {
    expect(
      sameTeamContent(team(), team({ updated_at: '2026-11-05T10:00:00' })),
    ).toBe(true)
  })

  it('自动补全推荐值后数值相同，不算改动', () => {
    // 模拟编辑器把 null 字段补成推荐值，但值本来就相等
    const filled = team({ members: [{ ...member(), item: 'Life Orb' }] })
    expect(sameTeamContent(filled, team())).toBe(true)
  })

  it('改名 / 换招式 / 换道具 / 改 EV 都算改动', () => {
    expect(sameTeamContent(team({ name: '新名字' }), team())).toBe(false)
    expect(
      sameTeamContent(team({ members: [member({ moves: ['Air Slash'] })] }), team()),
    ).toBe(false)
    expect(
      sameTeamContent(team({ members: [member({ item: 'Leftovers' })] }), team()),
    ).toBe(false)
    expect(
      sameTeamContent(team({ members: [member({ evs: [0, 0, 0, 252, 4, 252] })] }), team()),
    ).toBe(false)
  })

  it('增删成员算改动', () => {
    expect(sameTeamContent(team({ members: [] }), team())).toBe(false)
    expect(
      sameTeamContent(
        team({ members: [member(), member({ position: 1, dex_number: 9 })] }),
        team(),
      ),
    ).toBe(false)
  })

  it('空草稿与空快照视为一致', () => {
    expect(sameTeamContent(null, null)).toBe(true)
    expect(sameTeamContent(team(), null)).toBe(false)
  })

  it('极巨化等级：未设置与显式 10 等价，改成其它值才算改动', () => {
    expect(
      sameTeamContent(
        team({ members: [member({ dynamax_level: null })] }),
        team({ members: [member({ dynamax_level: 10 })] }),
      ),
    ).toBe(true)
    expect(
      sameTeamContent(
        team({ members: [member({ dynamax_level: 7 })] }),
        team({ members: [member({ dynamax_level: 10 })] }),
      ),
    ).toBe(false)
  })

  it('超极巨化开关的变化算改动', () => {
    expect(
      sameTeamContent(
        team({ members: [member({ gigantamax: true })] }),
        team({ members: [member({ gigantamax: false })] }),
      ),
    ).toBe(false)
    expect(
      sameTeamContent(
        team({ members: [member({ gigantamax: undefined })] }),
        team({ members: [member({ gigantamax: false })] }),
      ),
    ).toBe(true)
  })
})

describe('withPositions', () => {
  it('按列表顺序重排 position（删中间成员后不会重复）', () => {
    const members = [
      member({ position: 0 }),
      member({ position: 2, dex_number: 9 }),
      member({ position: 3, dex_number: 25 }),
    ]
    const next = withPositions([...members, member({ position: 2, dex_number: 150 })])

    expect(next.map((item) => item.position)).toEqual([0, 1, 2, 3])
  })
})
