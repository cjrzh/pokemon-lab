/**
 * 属性克制计算器。
 *
 * 三块内容，全部在本机计算（克制表随包加载，断网可用）：
 *   1. 倍率计算：选 1 个进攻属性 + 1–2 个防守属性，得到最终倍率；
 *   2. 谁克我（反向查询）：给 1–2 个防守属性，按倍率分组列出攻击属性；
 *   3. 进攻速查：每个属性一行的 18×18 矩阵（只显示 ≠1× 的格子）。
 *
 * 计算复用 `features/type-chart/engine.ts` —— 与图鉴详情页「属性相性」、
 * 后端 `/types/evaluate`、`/types/reverse` 是同一份规范克制表。
 */

import { useMemo, useState } from 'react'
import { ArrowRightLeft, Calculator, RotateCcw, Search, Shield, Swords, X } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { TYPES, typeChart, typeChartMeta } from '@/features/type-chart/data'
import {
  attackProfile,
  evaluate,
  formatMultiplier,
  multiplierTone,
  reverse,
} from '@/features/type-chart/engine'
import { cn } from '@/lib/utils'

const TYPE_NAME = new Map(TYPES.map((type) => [type.name, type.zh]))

/** 倍率档位的展示配色。 */
const TONE_CLASS: Record<ReturnType<typeof multiplierTone>, string> = {
  immune: 'bg-muted text-muted-foreground',
  resist: 'bg-type-grass/20 text-foreground',
  neutral: 'bg-muted/60 text-muted-foreground',
  effective: 'bg-type-fire/20 text-foreground',
  super: 'bg-destructive/15 text-destructive',
}

const MAX_DEFENDERS = 2

export function TypeCalcPage() {
  return (
    <>
      <PageHeader
        title="属性克制"
        description="选择进攻属性与最多两个防守属性计算倍率；也可以反过来查「谁克我」。计算在浏览器本地完成，断网可用。"
        actions={
          <Badge variant="outline" className="tabular-nums">
            {typeChartMeta.label}
          </Badge>
        }
      />

      <div className="space-y-4">
        <MultiplierCalculator />
        <ReverseLookup />
        <OffenseMatrix />
      </div>

      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        规则：{typeChartMeta.label} · {typeChartMeta.note}
      </p>
    </>
  )
}

/** 类型选择器：一排色块按钮；支持「取消已选」。 */
function TypePicker({
  label,
  types,
  value,
  onChange,
  max,
}: {
  label: string
  types: readonly { name: string; zh: string }[]
  value: string[]
  onChange: (next: string[]) => void
  max: number
}) {
  const toggle = (name: string) => {
    if (value.includes(name)) {
      onChange(value.filter((item) => item !== name))
      return
    }
    if (value.length >= max) {
      // 达到上限时替换最早选的，保持「最多 max 个」
      onChange([...value.slice(1), name])
      return
    }
    onChange([...value, name])
  }

  return (
    <div>
      <p className="mb-1.5 flex items-center gap-2 text-xs font-medium text-muted-foreground">
        {label}
        <span className="text-[10px] font-normal">
          {value.length}/{max}
        </span>
      </p>
      <div className="flex flex-wrap gap-1" role="group" aria-label={label}>
        {types.map((type) => {
          const active = value.includes(type.name)
          return (
            <button
              key={type.name}
              type="button"
              onClick={() => toggle(type.name)}
              aria-pressed={active}
              className={cn(
                'rounded-full border px-2.5 py-0.5 text-xs font-medium transition-all',
                active ? 'scale-105 border-transparent shadow-sm' : 'border-border opacity-80 hover:opacity-100',
              )}
              style={{
                backgroundColor: active ? `var(--type-${type.name})` : 'transparent',
                color: active ? `var(--type-${type.name}-fg)` : 'var(--muted-foreground)',
              }}
            >
              {type.zh}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function MultiplierCalculator() {
  const [attack, setAttack] = useState<string[]>([])
  const [defenders, setDefenders] = useState<string[]>([])

  const result = useMemo(() => {
    if (attack.length !== 1) return null
    return evaluate(attack[0], defenders, typeChart)
  }, [attack, defenders])

  const reset = () => {
    setAttack([])
    setDefenders([])
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calculator aria-hidden="true" className="size-4 text-muted-foreground" />
          倍率计算
        </CardTitle>
        <CardDescription>选 1 个进攻属性、最多 2 个防守属性，立即得到最终倍率。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <TypePicker
          label="进攻属性（1 个）"
          types={TYPES}
          value={attack}
          onChange={(next) => setAttack(next.slice(-1))}
          max={1}
        />
        <TypePicker
          label="防守属性（1–2 个）"
          types={TYPES}
          value={defenders}
          onChange={setDefenders}
          max={MAX_DEFENDERS}
        />

        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border/70 bg-muted/30 p-3.5">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            {attack.length === 1 ? (
              <TypeBadge type={attack[0]} className="px-2 py-0.5 text-xs" />
            ) : (
              <span className="text-xs text-muted-foreground">选择进攻属性</span>
            )}
            <ArrowRightLeft aria-hidden="true" className="size-3.5 text-muted-foreground" />
            {defenders.length > 0 ? (
              defenders.map((type) => (
                <TypeBadge key={type} type={type} className="px-2 py-0.5 text-xs" />
              ))
            ) : (
              <span className="text-xs text-muted-foreground">无防守属性（按 1× 计）</span>
            )}
          </div>

          <div className="ml-auto flex items-center gap-2">
            {result != null ? (
              <span
                className={cn(
                  'rounded-md px-2.5 py-1 text-sm font-semibold tabular-nums',
                  TONE_CLASS[multiplierTone(result)],
                )}
                aria-live="polite"
                aria-label="最终倍率"
              >
                {formatMultiplier(result)}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">—</span>
            )}
            <Button size="xs" variant="ghost" onClick={reset} disabled={!attack.length && !defenders.length}>
              <RotateCcw aria-hidden="true" />
              重置
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

/** 反向查询：给定防守属性，按倍率列出「谁打我」。 */
function ReverseLookup() {
  const [defenders, setDefenders] = useState<string[]>([])

  const groups = useMemo(() => {
    if (defenders.length === 0) return null
    const entries = [...reverse(defenders, typeChart).entries()]
    const order = [4, 2, 0.5, 0.25, 0]
    return order
      .map((multiplier) => ({
        multiplier,
        types: entries
          .filter(([, value]) => Math.abs(value - multiplier) < 1e-9)
          .map(([type]) => type),
      }))
      .filter((group) => group.types.length > 0)
  }, [defenders])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield aria-hidden="true" className="size-4 text-muted-foreground" />
          谁克我（受击查询）
        </CardTitle>
        <CardDescription>
          选 1–2 个防守属性，按倍率分组列出所有进攻属性；中性（1×）不显示。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <TypePicker
          label="受击属性（1–2 个）"
          types={TYPES}
          value={defenders}
          onChange={setDefenders}
          max={MAX_DEFENDERS}
        />

        {defenders.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border/70 bg-card/40 p-4 text-center text-xs text-muted-foreground">
            选择一个属性查看它的弱点与抗性。
          </p>
        ) : groups && groups.length > 0 ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {groups.map((group) => (
              <div key={group.multiplier} className="rounded-xl border border-border/70 bg-card/50 p-2.5">
                <p className="mb-1.5 flex items-center gap-2 text-xs font-medium">
                  <span
                    className={cn(
                      'rounded px-1.5 py-0.5 tabular-nums',
                      TONE_CLASS[multiplierTone(group.multiplier)],
                    )}
                  >
                    {formatMultiplier(group.multiplier)}
                  </span>
                  <span className="text-muted-foreground tabular-nums">{group.types.length}</span>
                </p>
                <div className="flex flex-wrap gap-1">
                  {group.types.map((type) => (
                    <TypeBadge key={type} type={type} className="px-1.5 py-0 text-[10px]" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-2xl border border-dashed border-border/70 bg-card/40 p-4 text-center text-xs text-muted-foreground">
            该组合对所有属性都是 1×（没有明显弱点或抗性）。
          </p>
        )}
      </CardContent>
    </Card>
  )
}

/** 进攻速查：每个属性一行，列出它打出去 ≠1× 的属性。 */
function OffenseMatrix() {
  const [query, setQuery] = useState('')
  const keyword = query.trim()
  const rows = useMemo(() => {
    const list = TYPES.map((type) => {
      const profile = attackProfile(type.name, typeChart)
      const groups = [2, 0.5, 0]
        .map((multiplier) => ({
          multiplier,
          types: [...profile.entries()]
            .filter(([, value]) => Math.abs(value - multiplier) < 1e-9)
            .map(([defense]) => defense),
        }))
        .filter((group) => group.types.length > 0)
      return { attack: type.name, groups }
    })
    if (!keyword) return list
    return list.filter(
      (row) =>
        (TYPE_NAME.get(row.attack) ?? '').includes(keyword) || row.attack.includes(keyword),
    )
  }, [keyword])

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Swords aria-hidden="true" className="size-4 text-muted-foreground" />
              进攻速查
            </CardTitle>
            <CardDescription>每种属性的招式打出去的倍率；只列 ≠1× 的属性。</CardDescription>
          </div>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="筛选属性…"
              aria-label="筛选属性"
              className="h-7 w-36 rounded-md border border-input bg-background pl-7 text-xs"
            />
            {query ? (
              <button
                type="button"
                onClick={() => setQuery('')}
                aria-label="清空属性筛选"
                className="absolute top-1/2 right-1 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-muted"
              >
                <X aria-hidden="true" className="size-3" />
              </button>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1.5">
          {rows.map((row) => (
            <li
              key={row.attack}
              data-testid={`offense-${row.attack}`}
              className="flex flex-wrap items-start gap-x-3 gap-y-1 rounded-xl border border-border/70 bg-card/50 p-2"
            >
              <TypeBadge type={row.attack} className="mt-0.5 shrink-0 px-2 py-0 text-[10px]" />
              <div className="flex min-w-0 flex-1 flex-wrap gap-x-3 gap-y-1">
                {row.groups.length === 0 ? (
                  <span className="text-[11px] text-muted-foreground">对所有属性都是 1×</span>
                ) : (
                  row.groups.map((group) => (
                    <span key={group.multiplier} className="inline-flex flex-wrap items-center gap-1">
                      <span className="text-[10px] text-muted-foreground tabular-nums">
                        {formatMultiplier(group.multiplier)}
                      </span>
                      {group.types.map((type) => (
                        <TypeBadge
                          key={type}
                          type={type}
                          className="px-1.5 py-0 text-[10px]"
                        />
                      ))}
                    </span>
                  ))
                )}
              </div>
            </li>
          ))}
          {rows.length === 0 ? (
            <li className="py-4 text-center text-xs text-muted-foreground">没有匹配的属性。</li>
          ) : null}
        </ul>
      </CardContent>
    </Card>
  )
}
