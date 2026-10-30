/**
 * 属性克制引擎（纯函数）—— 与后端 `app/domain/type_engine.py` 镜像的同一套逻辑。
 *
 * 硬性约束（与后端 domain 层一致）：
 *   - 不做 IO：克制表由调用方以参数传入（前端由 data.ts 从 data/ 导入）。
 *   - 两端共用同一份测试向量 `data/type-chart.cases.json`（pytest + Vitest 同读），
 *     保证结果一致；向量本身由 gen_type_chart.py 校验与 PokéAPI 一致。
 *
 * 计算在浏览器本地完成，断网可用（ARCHITECTURE.md §7）。
 */

/** 克制表：attack → {defense: 倍率}，缺省 1.0。 */
export type TypeChart = Readonly<Record<string, Readonly<Record<string, number>>>>

export const NEUTRAL = 1

const EPSILON = 1e-9

function isZero(value: number): boolean {
  return Math.abs(value) < EPSILON
}

function equals(a: number, b: number): boolean {
  return Math.abs(a - b) < EPSILON
}

/**
 * 计算单个进攻属性对一组防守属性的最终倍率。
 *
 * 规则（Gen 6+）：查表相乘；任一免疫则整体为 0。
 * 防守属性长度 1–2 由调用方（UI/API schema）保证；引擎本身不做上限校验，
 * 与后端行为一致 —— 传入 3 个属性也会按乘法算出来。
 * @throws 进攻属性不在克制表中时抛 Error（配置错误，不是用户输入错误）
 */
export function evaluate(attack: string, defense: readonly string[], chart: TypeChart): number {
  const row = chart[attack]
  if (row === undefined) {
    throw new Error(`进攻属性 ${attack} 不在克制表中`)
  }
  let multiplier = 1
  for (const defenseType of defense) {
    multiplier *= row[defenseType] ?? NEUTRAL
  }
  return isZero(multiplier) ? 0 : multiplier
}

/**
 * 反向查询：给定防守属性组合，列出所有进攻属性及其倍率。
 * 默认只返回非中性（≠1）项；includeNeutral 为 true 时返回全部 18 项。
 */
export function reverse(
  defense: readonly string[],
  chart: TypeChart,
  { includeNeutral = false }: { includeNeutral?: boolean } = {},
): Map<string, number> {
  const result = new Map<string, number>()
  for (const attack of Object.keys(chart)) {
    const multiplier = evaluate(attack, defense, chart)
    if (includeNeutral || !equals(multiplier, NEUTRAL)) {
      result.set(attack, multiplier)
    }
  }
  return result
}

/**
 * 进攻面：单一进攻属性对 18 种防守属性各自的倍率（含 1× 中性项）。
 *
 * 与 `reverse` 的区别：`reverse` 回答「谁打我、打得有多疼」，本函数回答
 * 「我用这个属性的招式打谁有效」。图鉴详情页的「进攻」视图用它。
 */
export function attackProfile(attack: string, chart: TypeChart): Map<string, number> {
  const row = chart[attack]
  if (row === undefined) {
    throw new Error(`进攻属性 ${attack} 不在克制表中`)
  }
  const result = new Map<string, number>()
  for (const defense of Object.keys(chart)) {
    const multiplier = row[defense] ?? NEUTRAL
    result.set(defense, isZero(multiplier) ? 0 : multiplier)
  }
  return result
}

/** 把倍率转成人可读标签（与后端 format_multiplier 保持一致）。 */
export function formatMultiplier(multiplier: number): string {
  if (isZero(multiplier)) return '无效（免疫）'
  if (equals(multiplier, 0.25)) return '1/4×'
  if (equals(multiplier, 0.5)) return '1/2×'
  if (equals(multiplier, 1)) return '1×'
  if (equals(multiplier, 2)) return '2×'
  if (equals(multiplier, 4)) return '4×'
  return `${multiplier}×`
}

/** 倍率→语义强度，用于 UI 配色与排序。 */
export function multiplierTone(multiplier: number): 'immune' | 'resist' | 'neutral' | 'effective' | 'super' {
  if (isZero(multiplier)) return 'immune'
  if (equals(multiplier, 0.25)) return 'resist'
  if (equals(multiplier, 0.5)) return 'resist'
  if (equals(multiplier, 1)) return 'neutral'
  if (equals(multiplier, 2)) return 'effective'
  return 'super'
}
