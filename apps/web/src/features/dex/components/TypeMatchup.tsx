/**
 * 属性相性：同时展示「防守面」与「进攻面」。
 *
 *   防守面（受击）：这只宝可梦被哪种属性的招式打时，倍率是多少。
 *   进攻面（出击）：用这只宝可梦自身属性的招式，去打其他属性时的倍率。
 *
 * 两个方向都直接复用 `features/type-chart/engine.ts` —— 与属性克制计算器、
 * 后端 `/types/evaluate`、`/types/reverse` 是同一套规则，不在图鉴里另写一份倍率表。
 * 双属性宝可梦的进攻面按「每种自身属性各一行」展示（招式只会属于其中一种属性）。
 */

import { useState } from 'react'
import { Swords, Shield } from 'lucide-react'

import { typeChart } from '@/features/type-chart/data'
import { attackProfile, reverse } from '@/features/type-chart/engine'
import { cn } from '@/lib/utils'

import { TypeBadge } from './TypeBadge'

/** 倍率分组（防守面使用的固定档位）。 */
const DEFENSE_GROUPS = [
  { multiplier: 4, label: '4× 弱点', tone: 'bg-destructive/10 text-destructive' },
  { multiplier: 2, label: '2× 弱点', tone: 'bg-type-fire/15 text-foreground' },
  { multiplier: 0.5, label: '1/2× 抗性', tone: 'bg-type-grass/15 text-foreground' },
  { multiplier: 0.25, label: '1/4× 抗性', tone: 'bg-type-grass/25 text-foreground' },
  { multiplier: 0, label: '0× 免疫', tone: 'bg-muted text-muted-foreground' },
] as const

/** 进攻面的分组：4×/2× 有效、1× 一般、1/2×/1/4× 不理想、0× 无效。 */
const OFFENSE_GROUPS = [
  { multiplier: 4, label: '4× 效果绝佳', tone: 'bg-type-grass/30 text-foreground' },
  { multiplier: 2, label: '2× 效果绝佳', tone: 'bg-type-grass/15 text-foreground' },
  { multiplier: 0.5, label: '1/2× 效果不佳', tone: 'bg-destructive/10 text-destructive' },
  { multiplier: 0.25, label: '1/4× 效果不佳', tone: 'bg-destructive/15 text-destructive' },
  { multiplier: 0, label: '0× 无效', tone: 'bg-muted text-muted-foreground' },
] as const

type View = 'defense' | 'offense'

export function TypeMatchup({ types }: { types: string[] }) {
  const [view, setView] = useState<View>('defense')

  if (types.length === 0) return null

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          className="inline-flex rounded-lg border border-border p-0.5"
          role="group"
          aria-label="切换属性相性视角"
        >
          <ViewButton
            active={view === 'defense'}
            onClick={() => setView('defense')}
            icon={Shield}
            label="受击"
          />
          <ViewButton
            active={view === 'offense'}
            onClick={() => setView('offense')}
            icon={Swords}
            label="出击"
          />
        </div>
        <p className="text-[11px] text-muted-foreground">
          {view === 'defense'
            ? '按自身属性组合，计算受到各属性攻击时的倍率'
            : '用自身属性的招式攻击各属性时的倍率'}
        </p>
      </div>

      {view === 'defense' ? (
        <DefenseGroups types={types} />
      ) : (
        <OffenseProfiles types={types} />
      )}
    </div>
  )
}

function ViewButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: typeof Shield
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      <Icon aria-hidden="true" className="size-3" />
      {label}
    </button>
  )
}

/** 防守面：被攻击时的倍率（原「属性相性」内容）。 */
function DefenseGroups({ types }: { types: string[] }) {
  const result = reverse(types, typeChart)
  const groups = DEFENSE_GROUPS.map((group) => ({
    ...group,
    types: [...result.entries()]
      .filter(([, multiplier]) => Math.abs(multiplier - group.multiplier) < 1e-9)
      .map(([type]) => type),
  })).filter((group) => group.types.length > 0)

  if (groups.length === 0) {
    return <p className="text-sm text-muted-foreground">该属性组合没有明显的弱点或抗性。</p>
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {groups.map((group) => (
        <div key={group.label} className="rounded-lg border p-2.5">
          <p className="mb-1.5 flex items-center gap-2 text-xs font-medium">
            <span className={cn('rounded px-1.5 py-0.5', group.tone)}>{group.label}</span>
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
  )
}

/**
 * 进攻面：每种自身属性一行，列出它对 18 种防守属性的倍率分组。
 *
 * 中性（1×）不单独占一格，避免把「一般」堆满整屏；用「其余 N 种为 1×」概括。
 */
function OffenseProfiles({ types }: { types: string[] }) {
  return (
    <div className="space-y-3">
      {types.map((attack) => {
        const profile = attackProfile(attack, typeChart)
        const groups = OFFENSE_GROUPS.map((group) => ({
          ...group,
          types: [...profile.entries()]
            .filter(([, multiplier]) => Math.abs(multiplier - group.multiplier) < 1e-9)
            .map(([type]) => type),
        })).filter((group) => group.types.length > 0)

        const neutral = 18 - groups.reduce((sum, group) => sum + group.types.length, 0)

        return (
          <div key={attack} className="rounded-lg border p-2.5">
            <p className="mb-2 flex flex-wrap items-center gap-2 text-xs font-medium">
              <TypeBadge type={attack} className="px-1.5 py-0 text-[10px]" />
              <span className="text-muted-foreground">属性招式对以下属性的倍率</span>
            </p>

            {groups.length === 0 ? (
              <p className="text-xs text-muted-foreground">对所有属性都是 1×。</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {groups.map((group) => (
                  <div key={group.label} className="flex flex-wrap items-center gap-1">
                    <span
                      className={cn(
                        'shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium tabular-nums',
                        group.tone,
                      )}
                    >
                      {group.label}
                    </span>
                    {group.types.map((type) => (
                      <TypeBadge key={type} type={type} className="px-1.5 py-0 text-[10px]" />
                    ))}
                  </div>
                ))}
              </div>
            )}

            {neutral > 0 ? (
              <p className="mt-1.5 text-[10px] text-muted-foreground">
                其余 {neutral} 种属性为 1×（中性）
              </p>
            ) : null}
          </div>
        )
      })}

      <p className="text-[11px] text-muted-foreground">
        招式倍率只看属性；实际伤害还会受特性、道具、太晶化等影响。
      </p>
    </div>
  )
}
