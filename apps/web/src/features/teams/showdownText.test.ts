/**
 * 单只成员 Showdown 代码：与导出页共用 renderShowdown，这里只验证映射与交易前缀。
 */

import { describe, expect, it } from 'vitest'

import type { TeamMember } from '@/features/teams/api'
import { memberToDraft, renderMemberShowdown, renderTeamShowdown } from '@/features/teams/showdownText'

const member: TeamMember = {
  position: 0,
  dex_number: 6,
  showdown_name: 'Charizard',
  nickname: null,
  item: 'Life Orb',
  ability: 'Blaze',
  nature: 'timid',
  evs: [4, 0, 0, 252, 0, 252],
  ivs: [31, 31, 31, 31, 31, 31],
  moves: ['Flamethrower', 'Air Slash', 'Protect', 'Roost'],
  tera_type: 'Fire',
  gender: 'F',
  shiny: true,
  level: null,
  language: 'CHS',
}

describe('renderMemberShowdown', () => {
  it('输出完整配置，交易前缀在第一行', () => {
    const text = renderMemberShowdown(member, {
      formatKey: 'sv',
      defaultLevel: 50,
      tradePrefix: '!tradeSV',
    })

    const lines = text.split('\n')
    expect(lines[0]).toBe('!tradeSV')
    expect(lines[1]).toContain('Charizard (F) @ Life Orb')
    expect(text).toContain('Ability: Blaze')
    expect(text).toContain('EVs: 4 HP / 252 SpA / 252 Spe')
    expect(text).toContain('Timid Nature')
    expect(text).toContain('- Flamethrower')
    expect(text).toContain('Tera Type: Fire')
    // 默认等级来自队伍（50）
    expect(text).toContain('Level: 50')
  })

  it('冠军格式：无前缀，无太晶', () => {
    const text = renderMemberShowdown(member, {
      formatKey: 'champions',
      defaultLevel: 50,
      tradePrefix: null,
    })

    expect(text.startsWith('Charizard')).toBe(true)
    expect(text).not.toContain('!trade')
    expect(text).not.toContain('Tera Type')
  })

  it('昵称写在头部：昵称 (物种)', () => {
    const text = renderMemberShowdown(
      { ...member, nickname: '火龙' },
      { formatKey: 'sv', defaultLevel: 50, tradePrefix: null },
    )
    expect(text.startsWith('火龙 (Charizard) (F) @ Life Orb')).toBe(true)
  })

  it('默认等级来自队伍；等级 100 时省略 Level 行', () => {
    const draft = memberToDraft({ ...member, level: null }, 100)
    expect(draft.level).toBe(100)
    const text = renderMemberShowdown(
      { ...member, level: 100 },
      { formatKey: 'sv', defaultLevel: 50, tradePrefix: null },
    )
    expect(text).not.toContain('Level:')
  })

  it('剑盾始终输出极巨化等级（未设置按 10）', () => {
    const swsh = (patch: Partial<TeamMember>) =>
      renderMemberShowdown(
        { ...member, ...patch },
        { formatKey: 'swsh', defaultLevel: 50, tradePrefix: null },
      )

    expect(swsh({ dynamax_level: 7 })).toContain('Dynamax Level: 7')
    expect(swsh({ dynamax_level: null })).toContain('Dynamax Level: 10')
    expect(swsh({ dynamax_level: 10 })).toContain('Dynamax Level: 10')
    // 朱紫没有极巨化
    expect(
      renderMemberShowdown(
        { ...member, dynamax_level: 7 },
        { formatKey: 'sv', defaultLevel: 50, tradePrefix: null },
      ),
    ).not.toContain('Dynamax Level')
  })

  it('剑盾输出超极巨化（Gigantamax: Yes），朱紫不输出', () => {
    expect(
      renderMemberShowdown(
        { ...member, gigantamax: true, dynamax_level: 10 },
        { formatKey: 'swsh', defaultLevel: 50, tradePrefix: '!tradeSWSH' },
      ),
    ).toContain('Gigantamax: Yes')
    expect(
      renderMemberShowdown(
        { ...member, gigantamax: true },
        { formatKey: 'sv', defaultLevel: 50, tradePrefix: null },
      ),
    ).not.toContain('Gigantamax')
  })

  it('剑盾不输出 Language 行，其余格式保留', () => {
    const swsh = renderMemberShowdown(member, {
      formatKey: 'swsh',
      defaultLevel: 50,
      tradePrefix: '!tradeSWSH',
    })
    expect(swsh).not.toContain('Language:')

    const sv = renderMemberShowdown(member, {
      formatKey: 'sv',
      defaultLevel: 50,
      tradePrefix: '!tradeSV',
    })
    expect(sv).toContain('Language: CHS')
  })
})

describe('renderTeamShowdown', () => {
  const second: TeamMember = {
    ...member,
    position: 1,
    dex_number: 9,
    showdown_name: 'Blastoise',
    item: 'Leftovers',
    ability: 'Torrent',
    moves: ['Surf'],
    nickname: null,
    gender: null,
    shiny: false,
    language: 'ENG',
  }

  it('整队代码：交易前缀只在首行，成员之间空一行', () => {
    const text = renderTeamShowdown([member, second], {
      formatKey: 'sv',
      defaultLevel: 50,
      tradePrefix: '!tradeSV',
    })

    const lines = text.split('\n')
    expect(lines[0]).toBe('!tradeSV')
    expect(text.match(/!tradeSV/g)).toHaveLength(1)
    // 两只之间恰好一个空行
    expect(text).toContain('- Roost  \n\nBlastoise @ Leftovers  ')
    // 每只的 Language 行仍各自保留（朱紫）
    expect(text.match(/Language: /g)).toHaveLength(2)
  })

  it('空队伍返回空串；冠军无前缀', () => {
    expect(
      renderTeamShowdown([], { formatKey: 'swsh', defaultLevel: 50, tradePrefix: '!tradeSWSH' }),
    ).toBe('')

    const text = renderTeamShowdown([member], {
      formatKey: 'champions',
      defaultLevel: 50,
      tradePrefix: null,
    })
    expect(text.startsWith('Charizard')).toBe(true)
    expect(text).not.toContain('!trade')
  })

  it('剑盾整队：不输出 Language，但保留极巨化参数', () => {
    const text = renderTeamShowdown([{ ...member, dynamax_level: 7 }], {
      formatKey: 'swsh',
      defaultLevel: 50,
      tradePrefix: '!tradeSWSH',
    })
    expect(text).not.toContain('Language:')
    expect(text).toContain('Dynamax Level: 7')
  })
})
