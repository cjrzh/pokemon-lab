/**
 * 草稿与「上次保存的快照」是否一致。
 *
 * 为什么要比对内容，而不是在每个 onChange 里 setDirty(true)：
 * 成员编辑器拿到 `/team-options` 后会自动套用推荐值并回调 onChange ——
 * 即使填完与原来的值**完全相同**（已保存的队伍本来就带着完整推荐配置），
 * 也会被标成「有未保存改动」，用户一打开页面就看到脏标记。
 *
 * 只比较可编辑字段：`updated_at` / `analysis` 这类服务端字段的变化不算改动。
 */

import type { TeamDetail, TeamMember, TeamMemberInput } from '@/features/teams/api'

function sameList(a: readonly number[] | null, b: readonly number[] | null): boolean {
  if (a === b) return true
  if (!a || !b || a.length !== b.length) return false
  return a.every((value, index) => value === b[index])
}

function sameStringList(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index])
}

function sameMember(a: TeamMember, b: TeamMember): boolean {
  // `position` 不参与比较：它就是列表顺序，增删成员后可能暂时与库里的序号不一致
  // （如删掉中间一只再补一只），但内容其实是同一套配置。
  return (
    a.dex_number === b.dex_number &&
    a.showdown_name === b.showdown_name &&
    (a.nickname ?? '') === (b.nickname ?? '') &&
    (a.item ?? '') === (b.item ?? '') &&
    (a.ability ?? '') === (b.ability ?? '') &&
    (a.nature ?? '') === (b.nature ?? '') &&
    sameList(a.evs, b.evs) &&
    sameList(a.ivs ?? null, b.ivs ?? null) &&
    sameStringList(a.moves, b.moves) &&
    (a.tera_type ?? '') === (b.tera_type ?? '') &&
    (a.gender ?? '') === (b.gender ?? '') &&
    Boolean(a.shiny) === Boolean(b.shiny) &&
    (a.level ?? null) === (b.level ?? null) &&
    // 没写 = Showdown 默认值 10，与显式 10 等价（避免打开旧队伍误报未保存）
    (a.dynamax_level ?? 10) === (b.dynamax_level ?? 10) &&
    Boolean(a.gigantamax) === Boolean(b.gigantamax) &&
    (a.language ?? 'CHS') === (b.language ?? 'CHS')
  )
}

/** 两份队伍草稿的可编辑内容是否相同。 */
export function sameTeamContent(a: TeamDetail | null, b: TeamDetail | null): boolean {
  if (a === b) return true
  if (!a || !b) return false
  if (a.id !== b.id || a.format_key !== b.format_key || a.name !== b.name) return false
  if ((a.note ?? '') !== (b.note ?? '')) return false
  if (a.members.length !== b.members.length) return false
  return a.members.every((member, index) => sameMember(member, b.members[index]))
}

/** 按列表顺序重排 `position`（后端落库时也是这么写的）。 */
export function withPositions(members: TeamMember[]): TeamMember[]
export function withPositions<T extends TeamMemberInput>(
  members: T[],
): (T & { position: number })[]
export function withPositions(
  members: (TeamMemberInput & { position?: number })[],
): (TeamMemberInput & { position: number })[] {
  return members.map((member, index) => ({ ...member, position: index }))
}
