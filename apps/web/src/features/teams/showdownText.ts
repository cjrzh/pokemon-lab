/**
 * 建队页「一键复制」用的 Showdown 代码。
 *
 * 复用 `features/doubles/showdown.ts:renderShowdown` —— 与导出页的代码同一套规则
 * （行尾两个空格、省略 0 EV / 31 IV），避免建队页与导出页各写一份、慢慢走样。
 *
 * 与导出页的区别：建队页只复制**队伍本体**，不带交易机器人前缀
 * （`!tradeSV` / `!tradeSWSH` / `!tradeBDSP`）。要发给交换机器人时，
 * 用队伍导出页或双打页的代码。
 */

import type { TeamLanguage, TeamMember } from '@/features/teams/api'
import { renderShowdown, type ShowdownDraft } from '@/features/doubles/showdown'

/** 队伍成员 → Showdown 草稿。 */
export function memberToDraft(member: TeamMember, defaultLevel: number): ShowdownDraft {
  return {
    species: member.showdown_name,
    nickname: member.nickname ?? null,
    gender: member.gender ?? null,
    shiny: Boolean(member.shiny),
    language: (member.language ?? 'CHS') as TeamLanguage,
    level: member.level ?? defaultLevel,
    dynamaxLevel: member.dynamax_level ?? 10,
    gigantamax: Boolean(member.gigantamax),
    ability: member.ability ?? '',
    item: member.item ?? '',
    nature: member.nature ?? 'hardy',
    evs: member.evs,
    ivs: member.ivs ?? null,
    moves: member.moves.filter(Boolean),
    teraType: member.tera_type ?? null,
  }
}

/**
 * 整队的 Showdown 文本：每只之间空一行，**不含**交易前缀。
 *
 * 与单只复制使用同一套渲染规则，因此「整队复制」与逐只复制拼起来的结果一致。
 */
export function renderTeamShowdown(
  members: TeamMember[],
  options: {
    formatKey: string
    defaultLevel: number
  },
): string {
  return members
    .map((member) => renderMemberShowdown(member, options))
    .filter(Boolean)
    .join('\n\n')
}

/**
 * 单只的 Showdown 文本，**不含**交易前缀（建队页粘贴到 Showdown 里就是纯队伍）。
 */
export function renderMemberShowdown(
  member: TeamMember,
  options: {
    formatKey: string
    defaultLevel: number
  },
): string {
  return renderShowdown(memberToDraft(member, options.defaultLevel), {
    tradePrefix: null,
    includeTera: options.formatKey === 'sv',
    // 极巨化等级只在剑盾有意义（朱紫没有极巨化、冠军不输出）
    includeDynamax: options.formatKey === 'swsh',
    // 剑盾复制的代码不带语言标记
    includeLanguage: options.formatKey !== 'swsh',
  })
}
