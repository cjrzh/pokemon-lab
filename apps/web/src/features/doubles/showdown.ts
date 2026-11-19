/**
 * Showdown 导出代码生成（纯函数）。
 *
 * 输入是「一个格式 + 一个形态的统计」以及用户的调整项，输出可直接粘贴到
 * Pokémon Showdown / 交换机器人聊天框的文本。格式细节：
 *   - 属性行以两个空格结尾（Showdown 自身的导出格式）；
 *   - 只输出非 0 的 EV、非 31 的 IV；
 *   - Champions 使用能力点（0–32），没有 IV 与太晶属性；
 *   - 交易机器人前缀（!tradeSV 等）放在**第一行**。
 *
 * 本模块不做 UI，便于单测；所有默认值都来自统计数据，用户可逐项覆盖。
 */

import type { DoublesFormatBlock, DoublesProfile, DoublesSpread, DoublesUsage } from './api'

/** Showdown 的六项短名（导出 EV/IV 行用）。 */
export const SHOWDOWN_STAT_SHORT = ['HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe'] as const

/** 性格 slug → Showdown 英文名。 */
export const NATURE_EN: Record<string, string> = {
  hardy: 'Hardy',
  lonely: 'Lonely',
  brave: 'Brave',
  adamant: 'Adamant',
  naughty: 'Naughty',
  bold: 'Bold',
  docile: 'Docile',
  relaxed: 'Relaxed',
  impish: 'Impish',
  lax: 'Lax',
  timid: 'Timid',
  hasty: 'Hasty',
  serious: 'Serious',
  jolly: 'Jolly',
  naive: 'Naive',
  modest: 'Modest',
  mild: 'Mild',
  quiet: 'Quiet',
  bashful: 'Bashful',
  rash: 'Rash',
  calm: 'Calm',
  gentle: 'Gentle',
  sassy: 'Sassy',
  careful: 'Careful',
  quirky: 'Quirky',
}

/** 性格的中文名（与后端 labels 一致，用于下拉框展示）。 */
export const NATURE_ZH: Record<string, string> = {
  hardy: '勤奋',
  lonely: '怕寂寞',
  brave: '勇敢',
  adamant: '固执',
  naughty: '顽皮',
  bold: '大胆',
  docile: '坦率',
  relaxed: '悠闲',
  impish: '淘气',
  lax: '乐天',
  timid: '胆小',
  hasty: '急躁',
  serious: '认真',
  jolly: '爽朗',
  naive: '天真',
  modest: '内敛',
  mild: '慢吞吞',
  quiet: '冷静',
  bashful: '害羞',
  rash: '马虎',
  calm: '温和',
  gentle: '温顺',
  sassy: '自大',
  careful: '慎重',
  quirky: '浮躁',
}

/** 交换机器人支持的语言代码；CHS 为默认。 */
export const LANGUAGES = ['CHS', 'CHT', 'ENG', 'JPN', 'KOR', 'FRA', 'GER', 'ITA', 'ESP'] as const
export type Language = (typeof LANGUAGES)[number]

export type Gender = 'M' | 'F'

export interface ShowdownDraft {
  species: string
  /** 昵称（可选）；有昵称时头部写作 `昵称 (物种)`。 */
  nickname?: string | null
  gender: Gender | null
  shiny: boolean
  language: Language
  level: number
  /** 极巨化等级 0–10（仅剑盾；null = 输出默认值 10，复制出去的代码带完整参数）。 */
  dynamaxLevel?: number | null
  /** 超极巨化（仅剑盾）：输出 `Gigantamax: Yes`。 */
  gigantamax?: boolean
  ability: string
  item: string
  nature: string
  /** 六项：HP / 攻击 / 防御 / 特攻 / 特防 / 速度。 */
  evs: number[]
  /** Champions 没有 IV，为 null。 */
  ivs: number[] | null
  moves: string[]
  teraType: string | null
}

export interface ShowdownRenderOptions {
  tradePrefix: string | null
  /** 是否输出太晶属性行（仅朱紫）。 */
  includeTera: boolean
  /** 是否输出极巨化等级行（仅剑盾）。 */
  includeDynamax?: boolean
  /**
   * 是否输出 `Language:` 行。剑盾不输出（复制给交换机器人时不需要）；
   * 缺省为 true，保持详情页其它格式的既有格式。
   */
  includeLanguage?: boolean
}

/**
 * 统计条目 → Showdown 可用的英文名。
 *
 * 导出的代码必须是纯英文（Showdown / 交换机器人按英文名解析）：
 * `name_en` 缺失时用 slug 转成可读英文，**绝不回落到中文名**。
 */
export function usageEnglish(usage: DoublesUsage): string {
  if (usage.name_en) return usage.name_en
  return usage.slug
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

/**
 * 下拉框标签：中文（英文）· 使用率。选项顺序即统计里的推荐顺序（使用率降序）。
 */
export function usageOptionLabel(usage: DoublesUsage): string {
  const en = usageEnglish(usage)
  const zh = usage.name && usage.name !== en ? usage.name : null
  const base = zh ? `${zh}（${en}）` : en
  return `${base} · ${usage.pct >= 1 ? usage.pct.toFixed(1) : usage.pct.toFixed(2)}%`
}

/**
 * 默认草稿：性格 / 配点 / 特性 / 道具 / 招式全取统计推荐值；
 * IV 全 31（用户要求），闪光、CHS、雌性默认开启。
 *
 * `genderRate` 来自图鉴（-1 无性别，0 仅雄性，8 仅雌性），用于避免生成
 * Showdown 会拒绝的性别标记。
 */
export function defaultDraft(
  format: DoublesFormatBlock,
  profile: DoublesProfile,
  genderRate: number | null,
): ShowdownDraft {
  const spread: DoublesSpread | null = profile.spreads[0] ?? null
  const points = spread?.points ?? [0, 0, 0, 0, 0, 0]

  let gender: Gender | null = 'F'
  if (genderRate === -1) gender = null
  else if (genderRate === 0) gender = 'M'
  else if (genderRate === 8) gender = 'F'

  return {
    species: profile.showdown_name,
    gender,
    shiny: true,
    language: 'CHS',
    level: format.default_level || 50,
    ability: profile.abilities[0] ? usageEnglish(profile.abilities[0]) : '',
    item: profile.items[0] ? usageEnglish(profile.items[0]) : '',
    nature: spread?.nature ?? 'hardy',
    evs: [...points],
    ivs: format.points_kind === 'stat_points' ? null : [31, 31, 31, 31, 31, 31],
    moves: profile.moves.slice(0, 4).map(usageEnglish),
    teraType:
      format.key === 'sv' && profile.tera_types[0]
        ? capitalize(profile.tera_types[0].type)
        : null,
  }
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** 把草稿渲染成 Showdown 文本。空行与行尾空格与 Showdown 官方导出一致。 */
export function renderShowdown(draft: ShowdownDraft, options: ShowdownRenderOptions): string {
  const lines: string[] = []

  let head = draft.nickname
    ? `${draft.nickname} (${draft.species})`
    : draft.species
  if (draft.gender) head += ` (${draft.gender})`
  if (draft.item.trim()) head += ` @ ${draft.item.trim()}`
  lines.push(head)

  if (draft.ability.trim()) lines.push(`Ability: ${draft.ability.trim()}`)
  if (draft.level && draft.level !== 100) lines.push(`Level: ${draft.level}`)
  // 剑盾始终写出极巨化等级（未设置按 Showdown 默认值 10），
  // 这样复制出去的代码明确带上该参数，而不是靠隐式默认。
  if (options.includeDynamax) {
    const dynamaxLevel = draft.dynamaxLevel ?? 10
    lines.push(`Dynamax Level: ${dynamaxLevel}`)
    // 超极巨化紧跟 Dynamax Level（两行相对顺序与 Showdown 一致；解析按行识别）
    if (draft.gigantamax) lines.push('Gigantamax: Yes')
  }
  if (draft.shiny) lines.push('Shiny: Yes')
  if (options.includeLanguage !== false) lines.push(`Language: ${draft.language}`)
  if (options.includeTera && draft.teraType) lines.push(`Tera Type: ${draft.teraType}`)

  const evs = draft.evs
    .map((value, index) =>
      value > 0 ? `${value} ${SHOWDOWN_STAT_SHORT[index]}` : '',
    )
    .filter(Boolean)
  if (evs.length > 0) lines.push(`EVs: ${evs.join(' / ')}`)

  const nature = NATURE_EN[draft.nature] ?? draft.nature
  lines.push(`${nature} Nature`)

  if (draft.ivs) {
    const ivs = draft.ivs
      .map((value, index) =>
        value !== 31 ? `${value} ${SHOWDOWN_STAT_SHORT[index]}` : '',
      )
      .filter(Boolean)
    if (ivs.length > 0) lines.push(`IVs: ${ivs.join(' / ')}`)
  }

  for (const move of draft.moves) {
    if (move.trim()) lines.push(`- ${move.trim()}`)
  }

  // 行尾两个空格是 Showdown 的导出习惯，这里保留以保持逐字节一致
  const set = lines.map((line) => `${line}  `).join('\n')
  return options.tradePrefix ? `${options.tradePrefix}\n${set}` : set
}

/** 校验草稿中的数值边界，返回修正后的副本（不抛错，保证界面始终可编辑）。 */
export function normalizeDraft(
  draft: ShowdownDraft,
  pointsKind: 'ev' | 'stat_points',
): ShowdownDraft {
  const maxEv = pointsKind === 'stat_points' ? 32 : 252
  const step = pointsKind === 'stat_points' ? 1 : 4
  const clampEv = (value: number) => {
    if (!Number.isFinite(value)) return 0
    const stepped = pointsKind === 'stat_points' ? Math.round(value) : Math.round(value / step) * step
    return Math.min(maxEv, Math.max(0, stepped))
  }
  const level = Number.isFinite(draft.level) ? Math.round(draft.level) : 50
  return {
    ...draft,
    level: Math.min(100, Math.max(1, level)),
    evs: draft.evs.map(clampEv),
    ivs: draft.ivs
      ? draft.ivs.map((value) => Math.min(31, Math.max(0, Math.round(value || 0))))
      : null,
    moves: draft.moves.map((move) => move.trim()).filter(Boolean).slice(0, 4),
  }
}

/**
 * 性格的增减项：`[提升, 下降]`，中性性格为 null。
 *
 * 顺序与 `SHOWDOWN_STAT_SHORT` 对应（0 HP / 1 攻击 / 2 防御 / 3 特攻 / 4 特防 / 5 速度）。
 * 用于下拉框与编辑区标注「▲攻击 ▼特攻」，避免用户只看到名字却不知道效果。
 */
export const NATURE_EFFECT: Record<string, [up: number, down: number] | null> = {
  hardy: null,
  lonely: [1, 2],
  brave: [1, 5],
  adamant: [1, 3],
  naughty: [1, 4],
  bold: [2, 1],
  docile: null,
  relaxed: [2, 5],
  impish: [2, 3],
  lax: [2, 4],
  timid: [5, 1],
  hasty: [5, 2],
  serious: null,
  jolly: [5, 3],
  naive: [5, 4],
  modest: [3, 1],
  mild: [3, 2],
  quiet: [3, 5],
  bashful: null,
  rash: [3, 4],
  calm: [4, 1],
  gentle: [4, 2],
  sassy: [4, 5],
  careful: [4, 3],
  quirky: null,
}

/** 六项的中文短名（与 EV 编辑器一致）。 */
export const STAT_ZH = ['HP', '攻击', '防御', '特攻', '特防', '速度'] as const

/** 性格效果的一句话描述，如 `攻击 ↑ / 特攻 ↓`；中性返回「无增减」。 */
export function natureEffectLabel(nature: string): string {
  const effect = NATURE_EFFECT[nature]
  if (!effect) return '无增减'
  return `${STAT_ZH[effect[0]]} ↑ / ${STAT_ZH[effect[1]]} ↓`
}
