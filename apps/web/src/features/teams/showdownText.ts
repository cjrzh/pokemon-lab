/**
 * 单只成员的 Showdown 代码（建队页「一键复制」用）。
 *
 * 复用 `features/doubles/showdown.ts:renderShowdown` —— 与详情页的导出代码
 * 同一套规则（行尾两个空格、省略 0 EV / 31 IV、交易前缀在第一行），
 * 避免建队页与导出页各写一份、慢慢走样。
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
 * 整队的 Showdown 文本：每只之间空一行，交易前缀只出现一次（首行）。
 *
 * 与单只复制使用同一套渲染规则，因此「整队复制」与逐只复制拼起来的结果一致。
 * 冠军格式没有交易前缀（传 null）。
 */
export function renderTeamShowdown(
  members: TeamMember[],
  options: {
    formatKey: string
    defaultLevel: number
    tradePrefix: string | null
  },
): string {
  const body = members
    .map((member) =>
      // 单只的渲染带前缀；整队只在最前面加一次，所以先按无前缀渲染
      renderMemberShowdown(member, { ...options, tradePrefix: null }),
    )
    .filter(Boolean)
    .join('\n\n')
  if (!body) return ''
  return options.tradePrefix ? `${options.tradePrefix}\n${body}` : body
}

/**
 * 单只的 Showdown 文本。
 *
 * `tradePrefix` 为 BDSP / 剑盾 / 朱紫的交易命令（如 `!tradeSV`）。带上它就可以
 * 直接把这一只发给交换机器人；冠军格式没有前缀，传 null。
 */
export function renderMemberShowdown(
  member: TeamMember,
  options: {
    formatKey: string
    defaultLevel: number
    tradePrefix: string | null
  },
): string {
  return renderShowdown(memberToDraft(member, options.defaultLevel), {
    tradePrefix: options.tradePrefix,
    includeTera: options.formatKey === 'sv',
    // 极巨化等级只在剑盾有意义（朱紫没有极巨化、冠军不输出）
    includeDynamax: options.formatKey === 'swsh',
    // 剑盾复制的代码不带语言标记
    includeLanguage: options.formatKey !== 'swsh',
  })
}
