/**
 * 种族值的展示常量与配色（纯函数，便于单独测试与复用）。
 *
 * 配色按「项目」而不是「数值」区分：HP 红、攻击橙、防御黄、特攻蓝、
 * 特防绿、速度粉 —— 同一项在不同宝可梦之间可以横向比较。
 */

export const STAT_LABELS: Record<string, string> = {
  hp: 'HP',
  attack: '攻击',
  defense: '防御',
  'special-attack': '特攻',
  'special-defense': '特防',
  speed: '速度',
}

export const STAT_ORDER = [
  'hp',
  'attack',
  'defense',
  'special-attack',
  'special-defense',
  'speed',
] as const

/**
 * 种族值条形的满量程。游戏上限是 255，但 180 能让 80–140 的常见区间
 * 在视觉上更容易区分。
 */
export const STAT_BAR_MAX = 180

/** 世代编号 → 地区名（详情页的「登场世代」展示用）。 */
export const GENERATION_REGION: Record<number, string> = {
  1: '关都',
  2: '城都',
  3: '丰缘',
  4: '神奥',
  5: '合众',
  6: '卡洛斯',
  7: '阿罗拉',
  8: '伽勒尔',
  9: '帕底亚',
}

/**
 * 每个种族值项目的固定配色类名。
 *
 * 对照「值越高颜色越深」的做法，这里按**项目**着色：同一项在所有宝可梦身上
 * 始终是同一种颜色，便于横向比较（HP 永远是红的、速度永远是粉的）。
 * 颜色令牌定义在 tokens.css 的 --stat-*，深色模式自动提亮。
 */
export const STAT_COLOR: Record<string, { bar: string; text: string; swatch: string }> = {
  hp: { bar: 'bg-stat-hp', text: 'text-stat-hp', swatch: 'bg-stat-hp' },
  attack: { bar: 'bg-stat-attack', text: 'text-stat-attack', swatch: 'bg-stat-attack' },
  defense: { bar: 'bg-stat-defense', text: 'text-stat-defense', swatch: 'bg-stat-defense' },
  'special-attack': {
    bar: 'bg-stat-special-attack',
    text: 'text-stat-special-attack',
    swatch: 'bg-stat-special-attack',
  },
  'special-defense': {
    bar: 'bg-stat-special-defense',
    text: 'text-stat-special-defense',
    swatch: 'bg-stat-special-defense',
  },
  speed: { bar: 'bg-stat-speed', text: 'text-stat-speed', swatch: 'bg-stat-speed' },
}

/** 六项之和（缺失项按 0 计）。 */
export function statTotal(stats: Record<string, number>): number {
  return STAT_ORDER.reduce((sum, key) => sum + (stats[key] ?? 0), 0)
}
