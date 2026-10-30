/**
 * 图鉴列表卡片。
 *
 * 视觉要点：
 *   - 立绘区用该宝可梦**主属性的颜色**做柔光底，卡片之间因此有辨识度，
 *     而不是千篇一律的灰底；
 *   - 属性徽章放在立绘下方，名称区保持两行对齐，长名字截断不跳行；
 *   - 编号、特性、种族值总和分层排列：编号弱、名称强、特性次要、数值最末。
 *
 * 颜色一律引用 `--type-*` 令牌（同 TypeBadge 的理由：动态类名不会被 Tailwind 生成）。
 */

import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'

import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { PokemonArtwork } from '@/features/dex/components/PokemonArtwork'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl, type PokemonSummary } from '@/features/dex/api'
import { cn } from '@/lib/utils'

/**
 * @param dense 紧凑模式：隐藏英文名与特性行，只保留编号 / 立绘 / 中文名 / 属性，
 *              用于「一页看更多」的场景。
 */
export function DexGridCard({
  pokemon: p,
  dense = false,
}: {
  pokemon: PokemonSummary
  dense?: boolean
}) {
  const primaryType = p.types[0] ?? 'normal'
  const displayName = p.name_zh ?? p.name_en
  const isSpecial = p.is_legendary || p.is_mythical

  return (
    <Link
      to={`/dex/${p.dex_number}`}
      className={cn(
        'group block h-full rounded-xl',
        'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
      )}
    >
      <Card
        // Card 的内边距来自 --card-spacing（py/px 工具类会覆盖 p-*），
        // 这里用 inline style 改成 10px，卡片更紧凑、一屏能多放一行。
        style={{ '--card-spacing': dense ? '0.5rem' : '0.625rem' } as CSSProperties}
        className={cn(
          'relative h-full overflow-hidden transition-all duration-200',
          dense ? 'gap-1.5' : 'gap-2.5',
          'group-hover:-translate-y-0.5 group-hover:shadow-lg group-hover:ring-primary/25',
          isSpecial && 'ring-1 ring-primary/20',
        )}
      >
        {/* 顶部细色条：一眼看出主属性，同时给卡片一个稳定的视觉锚点 */}
        <span
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-0.5 opacity-70"
          style={{ backgroundColor: `var(--type-${primaryType})` }}
        />

        <div className="flex items-center justify-between gap-2 pt-0.5">
          <span className="font-mono text-[11px] font-medium text-muted-foreground tabular-nums">
            #{String(p.dex_number).padStart(4, '0')}
          </span>
          <span className="flex items-center gap-1">
            {p.is_demo ? (
              <Badge variant="secondary" className="h-4 px-1.5 text-[9px]">
                演示
              </Badge>
            ) : null}
            {p.total_stats != null ? (
              <span
                className="text-[10px] text-muted-foreground tabular-nums"
                title="六项种族值之和"
              >
                ∑ {p.total_stats}
              </span>
            ) : null}
          </span>
        </div>

        {/* 立绘：主属性柔光底 + hover 放大 */}
        <div
          className="relative overflow-hidden rounded-lg"
          style={{
            background: `linear-gradient(160deg, color-mix(in oklab, var(--type-${primaryType}) 16%, transparent), transparent 72%)`,
          }}
        >
          <PokemonArtwork
            src={resolveMediaUrl(p.artwork_url)}
            fallbackSrc={resolveMediaUrl(p.artwork_fallback_url)}
            alt={displayName}
            legendary={p.is_legendary}
            mythical={p.is_mythical}
            variant="plain"
            className="aspect-square w-full"
            imageClassName="p-1 transition-transform duration-300 group-hover:scale-[1.06]"
          />
        </div>

        <div className="min-w-0">
          <p
            className={cn(
              'truncate leading-tight font-semibold',
              dense ? 'text-xs' : 'text-sm',
            )}
          >
            {displayName}
          </p>
          {dense ? null : (
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{p.name_en}</p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1">
          {p.types.map((t) => (
            <TypeBadge key={t} type={t} className="px-1.5 py-0 text-[10px]" />
          ))}
        </div>

        {/* 特性：S 级标红加粗（与详情页一致）；紧凑模式不显示，避免卡片过高 */}
        {!dense && p.abilities.length > 0 ? (
          <p className="mt-auto flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] leading-tight">
            {p.abilities.slice(0, 3).map((ability) => (
              <span
                key={ability.name}
                title={ability.is_s_tier ? 'S 级特性' : undefined}
                className={cn(
                  'truncate',
                  ability.is_s_tier
                    ? 'font-bold text-destructive'
                    : 'text-muted-foreground',
                )}
              >
                {ability.zh ?? ability.name}
                {ability.is_hidden ? (
                  <span className="text-muted-foreground/70" title="隐藏特性">
                    *
                  </span>
                ) : null}
              </span>
            ))}
          </p>
        ) : null}
      </Card>
    </Link>
  )
}
