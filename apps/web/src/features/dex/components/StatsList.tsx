/**
 * 种族值展示：六项固定配色 + 数值条。
 *
 * 配色按**项目**区分（HP 红 / 攻击 橙 / 防御 黄 / 特攻 蓝 / 特防 绿 / 速度 粉），
 * 不随数值高低变化 —— 这样同一项在不同宝可梦之间可以直接横向比较。
 * 颜色令牌定义在 tokens.css（--stat-*），深浅色模式各自取值。
 */

import { cn } from '@/lib/utils'

import { STAT_BAR_MAX, STAT_COLOR, STAT_LABELS, STAT_ORDER, statTotal } from './stats'

export function StatsList({
  stats,
  className,
  compact = false,
}: {
  stats: Record<string, number>
  className?: string
  compact?: boolean
}) {
  return (
    <dl className={cn('space-y-2', className)}>
      {STAT_ORDER.map((key) => {
        const value = stats[key]
        if (value == null) return null
        const color = STAT_COLOR[key]
        return (
          <div key={key} className="flex items-center gap-3 text-sm">
            <dt className="w-10 shrink-0 text-muted-foreground">{STAT_LABELS[key]}</dt>
            <dd
              className={cn(
                'w-9 shrink-0 text-right font-semibold tabular-nums',
                color?.text,
              )}
            >
              {value}
            </dd>
            <div
              className={cn('flex-1 overflow-hidden rounded-full bg-muted', compact ? 'h-1.5' : 'h-2')}
              role="meter"
              aria-valuenow={value}
              aria-valuemin={0}
              aria-valuemax={255}
              aria-label={`${STAT_LABELS[key]} ${value}`}
            >
              <div
                className={cn('h-full rounded-full transition-[width]', color?.bar)}
                style={{ width: `${Math.min(100, (value / STAT_BAR_MAX) * 100)}%` }}
              />
            </div>
          </div>
        )
      })}
    </dl>
  )
}

/** 六项配色图例：说明每种颜色对应哪个项目。 */
export function StatColorLegend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
      {STAT_ORDER.map((key) => (
        <li key={key} className="inline-flex items-center gap-1">
          <span className={cn('size-2 rounded-full', STAT_COLOR[key]?.swatch)} aria-hidden="true" />
          {STAT_LABELS[key]}
        </li>
      ))}
    </ul>
  )
}

export function StatTotal({ stats }: { stats: Record<string, number> }) {
  const total = statTotal(stats)
  if (total === 0) return null
  return (
    <p className="text-sm text-muted-foreground">
      合计 <span className="font-semibold text-foreground tabular-nums">{total}</span>
    </p>
  )
}
