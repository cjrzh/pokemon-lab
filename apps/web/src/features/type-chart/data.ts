/**
 * 属性克制规范数据的加载与类型化。
 *
 * 数据来源：仓库根 `data/type-chart.json`（由后端 `scripts/gen_type_chart.py`
 * 从 PokéAPI 生成，入库）。前端通过 Vite alias `@data/*` 直接 import，
 * 构建时打包进产物，离线即时计算无需网络（ARCHITECTURE.md §7）。
 *
 * 该文件在 import 时立即解析与校验：结构错误是构建期 / 首启期问题，
 * 应当尽早暴露，而不是在用户算克制时才报「数据可能过期」。
 */

import rawChart from '@data/type-chart.json'
import casesRaw from '@data/type-chart.cases.json'
import type { TypeChart } from './engine'

interface RawType {
  name: string
  zh: string
}

interface RawGeneration {
  min: number
  max: number
  note: string
}

interface RawTypeChartDocument {
  schema_version: number
  label: string
  generation: RawGeneration
  types: RawType[]
  chart: Record<string, Record<string, number>>
  source: {
    upstream: string
    method: string
    generator: string
    fetched_at: string
    license_note?: string
  }
}

interface RawCaseEvaluate {
  id: string
  kind: 'evaluate'
  attack: string
  defense: string[]
  expected: number
}

interface RawCaseReverse {
  id: string
  kind: 'reverse'
  defense: string[]
  expected: Record<string, number>
}

export type TypeChartCase = RawCaseEvaluate | RawCaseReverse

const document = rawChart as RawTypeChartDocument

const typeNames = document.types.map((t) => t.name)

/** 健全校验：18 属性、图表键一致。运行期一次，失败直接抛（构建/首启暴露）。 */
function validate(document: RawTypeChartDocument): void {
  if (typeNames.length !== 18) {
    throw new Error(`属性克制表属性数量异常：${typeNames.length}，应为 18`)
  }
  const nameSet = new Set(typeNames)
  for (const attack of Object.keys(document.chart)) {
    if (!nameSet.has(attack)) {
      throw new Error(`克制表行键不在属性列表中：${attack}`)
    }
    for (const defense of Object.keys(document.chart[attack])) {
      if (!nameSet.has(defense)) {
        throw new Error(`${attack} 行含未知防守属性 ${defense}`)
      }
    }
  }
}

validate(document)

/** 类型化的克制表（只读）。 */
export const typeChart: TypeChart = document.chart

/** 属性列表（英文键 + 中文名），保持文件中的顺序。 */
export const TYPES: readonly { name: string; zh: string }[] = document.types

/** 中文名查找。 */
export const ZH: Readonly<Record<string, string>> = Object.fromEntries(
  document.types.map((t) => [t.name, t.zh]),
)

/** 克制表元信息。 */
export const typeChartMeta = {
  label: document.label,
  generationMin: document.generation.min,
  generationMax: document.generation.max,
  note: document.generation.note,
  fetchedAt: document.source.fetched_at,
}

/** 前后端共享的测试向量（engine.test.ts 读取，与 pytest 同源）。 */
export const typeChartCases: readonly TypeChartCase[] = (casesRaw as { cases: TypeChartCase[] }).cases
