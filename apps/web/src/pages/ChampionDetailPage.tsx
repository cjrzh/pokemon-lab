/**
 * 冠军图鉴详情：单只宝可梦在冠军双打下的配装明细。
 *
 * 与图鉴详情页的「双打对战辅助」同源（`/pokemon/{dex}/doubles`），
 * 但这里只呈现冠军一段，且按「能力点」口径展示配点。
 * 多形态（如 Charizard-Mega-Y）会各自成段，因为配装完全不同。
 */

import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CircleAlert, RefreshCw, Users } from 'lucide-react'

import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { datasetLabel, spreadText } from '@/features/champions/api'
import { useChampionsProfile } from '@/features/champions/hooks'
import { abilityDetailLink } from '@/features/abilities/api'
import { ItemIcon } from '@/features/dex/components/ItemIcon'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { usePokemonDetail } from '@/features/dex/hooks'
import {
  formatMonth,
  formatPct,
  type DoublesUsage,
} from '@/features/doubles/api'
import { NATURE_EFFECT, STAT_ZH } from '@/features/doubles/showdown'
import { itemDetailLink } from '@/features/items/api'
import { moveDetailLink } from '@/features/moves/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

export function ChampionDetailPage() {
  const { dexNumber } = useParams()
  const dex = Number(dexNumber)
  const pokemon = usePokemonDetail(dex)
  const { block, isPending, isError, error, refetch } = useChampionsProfile(dex)

  const name = pokemon.data?.name_zh ?? pokemon.data?.name_en ?? (Number.isFinite(dex) ? `#${dex}` : '宝可梦')

  if (!Number.isInteger(dex) || dex <= 0) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        图鉴编号无效。{' '}
        <Link to="/champions" className="underline underline-offset-2">
          返回冠军图鉴
        </Link>
      </Card>
    )
  }

  return (
    <>
      <Link
        to="/champions"
        className="mb-4 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden="true" className="size-3.5" />
        冠军图鉴
      </Link>

      <header className="panel mb-5 flex flex-wrap items-center gap-x-5 gap-y-3 px-4 py-4">
        <div
          className="relative size-24 shrink-0 overflow-hidden rounded-2xl ring-1 ring-inset ring-foreground/5"
          style={{
            background: `linear-gradient(160deg, color-mix(in oklab, var(--type-${pokemon.data?.types[0] ?? 'normal'}) 20%, transparent), transparent 74%)`,
          }}
        >
          <PokemonSprite
            src={resolveMediaUrl(pokemon.data?.artwork_url ?? pokemon.data?.sprite_url)}
            alt={name}
            type={pokemon.data?.types[0]}
            className="size-full"
          />
        </div>

        <div className="min-w-0 flex-1">
          <h1 className="flex flex-wrap items-baseline gap-x-2 font-heading text-2xl font-semibold tracking-tight">
            {name}
            <span className="text-xs font-normal text-muted-foreground">
              #{String(dex).padStart(4, '0')} · {pokemon.data?.name_en ?? ''}
            </span>
          </h1>
          <span className="mt-1 flex flex-wrap items-center gap-1">
            {(pokemon.data?.types ?? []).map((type) => (
              <TypeBadge key={type} type={type} className="px-1.5 py-0 text-[10px]" />
            ))}
            {pokemon.data?.abilities?.[0] ? (
              <Link
                to={abilityDetailLink(pokemon.data.abilities[0].name)}
                className="ml-1 text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                特性{' '}
                {pokemon.data.abilities[0].zh ?? pokemon.data.abilities[0].name}
              </Link>
            ) : null}
          </span>
          {block ? (
            <p className="mt-2 text-[11px] text-muted-foreground">{datasetLabel(block)}</p>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Badge variant="outline">冠军 · 双打</Badge>
          <Button size="sm" variant="outline" asChild>
            <Link to={`/dex/${dex}`}>完整图鉴</Link>
          </Button>
        </div>
      </header>

      {isPending ? (
        <Card className="p-6">
          <Skeleton className="h-40 w-full" />
        </Card>
      ) : isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>冠军配装加载失败</AlertTitle>
          <AlertDescription>{describeApiError(error)}</AlertDescription>
          <AlertAction>
            <Button size="sm" variant="outline" onClick={() => void refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : !block || block.profiles.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          这只宝可梦在冠军双打里没有统计记录 —— 可能是当前规则下未上榜，或数据尚未导入。
        </Card>
      ) : (
        <div className="space-y-4">
          {block.profiles.map((profile) => (
            <Card key={profile.showdown_name}>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-baseline gap-x-2">
                  {profile.showdown_name}
                  {profile.rank != null ? (
                    <Badge variant="secondary" className="text-[10px]">
                      第 {profile.rank} 名
                    </Badge>
                  ) : null}
                  <span className="text-sm font-normal text-muted-foreground tabular-nums">
                    使用率 {profile.usage != null ? formatPct(profile.usage) : '—'}
                  </span>
                </CardTitle>
                <CardDescription className="tabular-nums">
                  样本 {profile.raw_count.toLocaleString()} · {formatMonth(block.month)}统计 ·
                  cutoff {block.cutoff}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-5">
                <Section title="能力点配点" empty={profile.spreads.length === 0}>
                  <ul className="space-y-1.5">
                    {profile.spreads.map((spread) => (
                      <li
                        key={`${spread.nature}-${spread.points.join('-')}`}
                        className="flex items-center gap-3 rounded-xl border border-border/60 px-3 py-1.5 text-xs"
                      >
                        <span className="flex w-24 shrink-0 flex-col">
                          <span className="font-medium">{spread.nature_label}</span>
                          <NatureEffect nature={spread.nature} />
                        </span>
                        <span className="min-w-0 flex-1 font-mono text-[11px] tabular-nums">
                          {spreadText(spread, block.points_kind)}
                        </span>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {formatPct(spread.pct)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Section>

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                  <Section title="特性" empty={profile.abilities.length === 0}>
                    <UsageList items={profile.abilities} linkKind="ability" />
                  </Section>
                  <Section title="道具" empty={profile.items.length === 0}>
                    <UsageList items={profile.items} showIcon linkKind="item" />
                  </Section>
                  <Section title="招式" empty={profile.moves.length === 0}>
                    <UsageList items={profile.moves} showMoveType linkKind="move" />
                  </Section>
                  <Section title="太晶属性" empty={profile.tera_types.length === 0}>
                    <ul className="space-y-1">
                      {profile.tera_types.map((tera) => (
                        <li key={tera.type} className="flex items-center gap-2 text-xs">
                          <TypeBadge type={tera.type} className="px-1.5 py-0 text-[10px]" />
                          <Bar pct={tera.pct} />
                          <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">
                            {formatPct(tera.pct)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Section>
                </div>

                <Section
                  title="常见队友"
                  empty={profile.teammates.length === 0}
                  icon={<Users aria-hidden="true" className="size-3.5" />}
                >
                  <ul className="flex flex-wrap gap-1.5">
                    {profile.teammates.map((mate) => {
                      const label = mate.name_zh ?? mate.showdown_name
                      return (
                        <li key={mate.showdown_name}>
                          {mate.dex_number != null ? (
                            <Link
                              to={`/champions/${mate.dex_number}`}
                              className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-[11px] hover:border-primary/40 hover:text-foreground"
                            >
                              {label}
                              <span className="text-muted-foreground tabular-nums">
                                {formatPct(mate.pct)}
                              </span>
                            </Link>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-[11px]">
                              {label}
                              <span className="text-muted-foreground tabular-nums">
                                {formatPct(mate.pct)}
                              </span>
                            </span>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </Section>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

function Section({
  title,
  empty,
  icon,
  children,
}: {
  title: string
  empty: boolean
  icon?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-foreground">
        {icon}
        {title}
      </h2>
      {empty ? <p className="text-xs text-muted-foreground">无统计</p> : children}
    </section>
  )
}

function Bar({ pct }: { pct: number }) {
  return (
    <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted/70">
      <span
        className="block h-full rounded-full bg-[linear-gradient(90deg,var(--primary),var(--brand-cyan))]"
        style={{ width: `${Math.min(100, pct)}%` }}
      />
    </span>
  )
}

function UsageList({
  items,
  showIcon = false,
  showMoveType = false,
  linkKind,
}: {
  items: DoublesUsage[]
  showIcon?: boolean
  showMoveType?: boolean
  /** 是否链到已有页面：招式 → 招式详情、特性 → 特性页、道具 → 道具页。 */
  linkKind?: 'move' | 'ability' | 'item'
}) {
  const hrefOf = (item: DoublesUsage): string | null => {
    if (linkKind === 'move') return moveDetailLink(item.slug)
    if (linkKind === 'ability') return abilityDetailLink(item.slug)
    if (linkKind === 'item') return itemDetailLink(item.name)
    return null
  }

  return (
    <ul className="space-y-1">
      {items.map((item) => {
        const href = hrefOf(item)
        const label = (
          <>
            {showIcon ? (
              <ItemIcon
                src={resolveMediaUrl(item.icon_url)}
                alt={item.name}
                className="size-3.5"
              />
            ) : null}
            {showMoveType && item.type ? (
              <TypeBadge type={item.type} className="px-1 py-0 text-[9px]" />
            ) : null}
            <span className={cn('truncate', href && 'hover:text-foreground hover:underline')}>
              {item.name}
            </span>
          </>
        )

        return (
          <li key={item.slug} className="flex items-center gap-2 text-xs">
            {href ? (
              <Link to={href} className="flex min-w-0 flex-1 items-center gap-1.5">
                {label}
              </Link>
            ) : (
              <span className="flex min-w-0 flex-1 items-center gap-1.5">{label}</span>
            )}
            <Bar pct={item.pct} />
            <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">
              {formatPct(item.pct)}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * 性格的增减效果：`▲ 攻击 ▼ 特攻`。
 *
 * 只显示性格名的话，用户还得自己去记「固执到底加了什么」；
 * 这里复用组队页同一份 `NATURE_EFFECT`，中性性格如实标「无增减」。
 */
function NatureEffect({ nature }: { nature: string }) {
  const effect = NATURE_EFFECT[nature]
  if (!effect) {
    return <span className="text-[10px] text-muted-foreground">无增减</span>
  }
  return (
    <span className="flex items-center gap-1 text-[10px]">
      <span className="font-medium text-success">▲ {STAT_ZH[effect[0]]}</span>
      <span className="font-medium text-destructive">▼ {STAT_ZH[effect[1]]}</span>
    </span>
  )
}
