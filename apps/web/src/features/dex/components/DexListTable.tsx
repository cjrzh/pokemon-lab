/**
 * 图鉴列表视图（表格行）。
 *
 * 用途：快速横向比较。列顺序按浏览需求排：编号 → 名称 → 属性 → 六项种族值 → 合计 → 特性。
 * 六项数值沿用详情页的**按项目配色**（stats.ts 的 STAT_COLOR），
 * 一眼能定位「哪只速度更快、哪只特攻更高」。
 *
 * 移动端：表格横向滚动，名称列 sticky，滚动时仍知道在看哪只。
 */

import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, Crown, Sparkles, Star } from 'lucide-react'

import { abilityDetailLink } from '@/features/abilities/api'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { STAT_COLOR, STAT_LABELS, STAT_ORDER } from '@/features/dex/components/stats'
import { resolveMediaUrl, type PokemonSummary } from '@/features/dex/api'
import { nextSort, type DexSort } from '@/features/dex/view'
import { cn } from '@/lib/utils'

const STAT_HEADER = STAT_ORDER.map((key) => STAT_LABELS[key])

export function DexListTable({
  items,
  sort = 'dex',
  onSort,
}: {
  items: PokemonSummary[]
  /** 当前排序（表头箭头据此显示） */
  sort?: DexSort
  /** 点击「编号」/「合计」表头切换排序；不传则表头不可点 */
  onSort?: (sort: DexSort) => void
}) {
  return (
    <div className="overflow-x-auto rounded-xl border bg-card">
      <table className="w-full min-w-[46rem] border-collapse text-sm">
        <caption className="sr-only">图鉴列表：编号、名称、属性、种族值与特性</caption>
        <thead>
          <tr className="border-b bg-muted/40 text-left text-[11px] text-muted-foreground">
            <SortableHeader
              label="编号"
              active={sort === 'dex' || sort === 'dex_desc'}
              direction={sort === 'dex_desc' ? 'desc' : 'asc'}
              onClick={onSort ? () => onSort(nextSort(sort, 'dex')) : undefined}
              className="w-16 py-2 pl-3"
            />
            <th scope="col" className="py-2 pr-3 font-medium">
              名称
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              属性
            </th>
            {STAT_HEADER.map((label) => (
              <th key={label} scope="col" className="w-11 py-2 pr-1 text-right font-medium">
                {label}
              </th>
            ))}
            <SortableHeader
              label="合计"
              active={sort === 'total_stats' || sort === 'total_stats_asc'}
              direction={sort === 'total_stats_asc' ? 'asc' : 'desc'}
              onClick={onSort ? () => onSort(nextSort(sort, 'total_stats')) : undefined}
              className="w-14 py-2 pr-1"
              align="right"
              title="按六项种族值合计排序"
            />
            <th scope="col" className="py-2 pr-3 font-medium">
              特性
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <DexListRow key={p.dex_number} pokemon={p} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * 可排序表头：整格是一个按钮，箭头只在当前排序生效时显示。
 * 用 aria-sort 把状态暴露给读屏软件（而不是只靠箭头颜色）。
 */
function SortableHeader({
  label,
  active,
  direction,
  onClick,
  className,
  align = 'left',
  title,
}: {
  label: string
  active: boolean
  direction: 'asc' | 'desc'
  onClick?: () => void
  className?: string
  align?: 'left' | 'right'
  title?: string
}) {
  const content = (
    <span
      className={cn(
        'inline-flex items-center gap-0.5',
        align === 'right' && 'flex-row-reverse',
      )}
    >
      {label}
      {active ? (
        direction === 'asc' ? (
          <ArrowUp aria-hidden="true" className="size-3 text-primary" />
        ) : (
          <ArrowDown aria-hidden="true" className="size-3 text-primary" />
        )
      ) : null}
    </span>
  )

  return (
    <th
      scope="col"
      aria-sort={active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={cn('font-medium', className)}
    >
      {onClick ? (
        <button
          type="button"
          onClick={onClick}
          title={title ?? `按${label}排序`}
          className={cn(
            'inline-flex w-full items-center rounded-sm px-0.5 py-0.5 transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none',
            align === 'right' && 'justify-end',
            active ? 'text-foreground' : 'text-muted-foreground',
          )}
        >
          {content}
        </button>
      ) : (
        content
      )}
    </th>
  )
}

function DexListRow({ pokemon: p }: { pokemon: PokemonSummary }) {
  const displayName = p.name_zh ?? p.name_en
  return (
    <tr className="group border-b last:border-b-0 hover:bg-muted/40">
      <td className="py-1.5 pl-3 text-xs text-muted-foreground tabular-nums">
        {String(p.dex_number).padStart(4, '0')}
      </td>

      <td className="max-w-56 py-1.5 pr-3">
        <Link
          to={`/dex/${p.dex_number}`}
          className="flex min-w-0 items-center gap-1.5 font-medium group-hover:text-primary"
        >
          {/* 小图标：96×96 sprite，主属性色底圈 */}
          <PokemonSprite
            src={resolveMediaUrl(p.sprite_url)}
            alt={displayName}
            type={p.types[0]}
            className="size-6"
          />
          {/* 小图标之外的特殊标记：传说（金色星）/ 幻之（品牌色闪光），与卡片模式一致 */}
          {p.is_legendary ? (
            <Star aria-label="传说的宝可梦" className="size-3 shrink-0 text-warning" />
          ) : null}
          {p.is_mythical ? (
            <Sparkles aria-label="幻之宝可梦" className="size-3 shrink-0 text-primary" />
          ) : null}
          <span className="truncate">{displayName}</span>
          <span className="truncate text-[11px] font-normal text-muted-foreground">
            {p.name_en}
          </span>
          {p.is_demo ? (
            <span className="shrink-0 rounded bg-muted px-1 text-[9px] text-muted-foreground">
              演示
            </span>
          ) : null}
        </Link>
      </td>

      <td className="py-1.5 pr-3">
        <span className="flex flex-wrap gap-1">
          {p.types.map((t) => (
            <TypeBadge key={t} type={t} className="px-1.5 py-0 text-[10px]" />
          ))}
        </span>
      </td>

      {STAT_ORDER.map((key) => {
        const value = p.stats?.[key]
        return (
          <td
            key={key}
            className={cn(
              'py-1.5 pr-1 text-right text-xs tabular-nums',
              value == null ? 'text-muted-foreground' : STAT_COLOR[key]?.text,
            )}
          >
            {value ?? '—'}
          </td>
        )
      })}

      <td className="py-1.5 pr-1 text-right text-xs font-semibold tabular-nums">
        {p.total_stats ?? '—'}
      </td>

      <td className="max-w-56 py-1.5 pr-3">
        <span className="flex flex-wrap gap-x-1.5 gap-y-0.5 text-[10px]">
          {p.abilities.length === 0 ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            p.abilities.map((ability) => (
              <Link
                key={ability.name}
                to={abilityDetailLink(ability.name)}
                className={cn(
                  'inline-flex items-center gap-0.5 rounded-sm underline-offset-2 hover:underline',
                  ability.is_s_tier
                    ? 'font-bold text-destructive'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                title={ability.is_s_tier ? 'S 级特性 · 点击查看特性页' : '点击查看特性页'}
              >
                {ability.is_s_tier ? <Crown aria-hidden="true" className="size-2.5" /> : null}
                {ability.zh ?? ability.name}
                {ability.is_hidden ? <span className="opacity-70">*</span> : null}
              </Link>
            ))
          )}
        </span>
      </td>
    </tr>
  )
}
