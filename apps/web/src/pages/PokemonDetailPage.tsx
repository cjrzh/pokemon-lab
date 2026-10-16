import { ArrowLeft, CircleAlert, RefreshCw } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import type { EvolutionNode, PokemonDetail } from '@/features/dex/api'
import { usePokemonDetail } from '@/features/dex/hooks'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const STAT_LABELS: Record<string, string> = {
  hp: 'HP',
  attack: '攻击',
  defense: '防御',
  'special-attack': '特攻',
  'special-defense': '特防',
  speed: '速度',
}

const STAT_MAX = 255

export function PokemonDetailPage() {
  const { dexNumber } = useParams<{ dexNumber: string }>()
  const parsed = Number(dexNumber)
  const detail = usePokemonDetail(Number.isInteger(parsed) && parsed > 0 ? parsed : -1)

  return (
    <div className="space-y-4">
      <Button asChild size="sm" variant="ghost" className="-ml-2">
        <Link to="/dex">
          <ArrowLeft aria-hidden="true" />
          返回图鉴
        </Link>
      </Button>

      {detail.isPending ? (
        <DetailSkeleton />
      ) : detail.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>无法加载图鉴详情</AlertTitle>
          <AlertDescription>{describeApiError(detail.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void detail.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : (
        <DetailBody detail={detail.data} />
      )}
    </div>
  )
}

function DetailBody({ detail }: { detail: PokemonDetail }) {
  const heightM = detail.height_dm != null ? detail.height_dm / 10 : null
  const weightKg = detail.weight_hg != null ? detail.weight_hg / 10 : null

  return (
    <>
      {/* ---------- 基本信息卡 ---------- */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm text-muted-foreground">
                #{String(detail.dex_number).padStart(3, '0')}
              </p>
              <h1 className="font-heading text-2xl font-semibold tracking-tight">
                {detail.name_zh ?? detail.name_en}
                {detail.name_zh ? (
                  <span className="ml-2 text-base font-normal text-muted-foreground">
                    {detail.name_en}
                  </span>
                ) : null}
              </h1>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {detail.types.map((t) => (
                  <TypeBadge key={t} type={t} />
                ))}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1.5 text-right">
              {detail.is_demo ? <Badge variant="secondary">演示数据</Badge> : null}
              <Badge variant="outline">{detail.source_label}</Badge>
              {detail.synced_at ? (
                <p className="text-xs text-muted-foreground">
                  同步于 {new Date(detail.synced_at).toLocaleString()}
                </p>
              ) : null}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
            {detail.generation_introduced ? (
              <div>
                <dt className="text-xs text-muted-foreground">登场世代</dt>
                <dd className="mt-0.5">第 {detail.generation_introduced} 世代</dd>
              </div>
            ) : null}
            {heightM != null ? (
              <div>
                <dt className="text-xs text-muted-foreground">身高</dt>
                <dd className="mt-0.5">{heightM.toFixed(1)} m</dd>
              </div>
            ) : null}
            {weightKg != null ? (
              <div>
                <dt className="text-xs text-muted-foreground">体重</dt>
                <dd className="mt-0.5">{weightKg.toFixed(1)} kg</dd>
              </div>
            ) : null}
          </dl>
        </CardContent>
      </Card>

      {/* ---------- 种族值 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>种族值</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {Object.entries(STAT_LABELS).map(([key, label]) => {
            const value = detail.stats[key]
            if (value == null) return null
            const percent = Math.min(100, (value / STAT_MAX) * 100)
            return (
              <div key={key} className="flex items-center gap-3 text-sm">
                <span className="w-12 shrink-0 text-muted-foreground">{label}</span>
                <span className="w-8 shrink-0 text-right font-medium tabular-nums">{value}</span>
                <div
                  className="h-2 flex-1 overflow-hidden rounded-full bg-muted"
                  role="meter"
                  aria-valuenow={value}
                  aria-valuemin={0}
                  aria-valuemax={STAT_MAX}
                  aria-label={`${label} ${value}`}
                >
                  <div
                    className={cn(
                      'h-full rounded-full transition-[width]',
                      value >= 120
                        ? 'bg-primary'
                        : value >= 80
                          ? 'bg-primary/70'
                          : 'bg-primary/40',
                    )}
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>

      {/* ---------- 特性 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>特性</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            {detail.abilities.length === 0 ? (
              <li className="text-muted-foreground">暂无特性数据。</li>
            ) : (
              detail.abilities.map((ability) => (
                <li key={ability.name} className="flex items-center gap-2">
                  {ability.is_hidden ? (
                    <Badge variant="outline">隐藏</Badge>
                  ) : (
                    <Badge variant="secondary">普通</Badge>
                  )}
                  <span className="font-medium">{ability.zh ?? ability.name}</span>
                  {ability.zh ? (
                    <span className="text-xs text-muted-foreground">{ability.name}</span>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </CardContent>
      </Card>

      {/* ---------- 进化链 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>进化链</CardTitle>
        </CardHeader>
        <CardContent>
          {detail.evolution.chain ? (
            <EvolutionTree node={detail.evolution.chain} currentDex={detail.dex_number} />
          ) : (
            <p className="text-sm text-muted-foreground">暂无进化信息。</p>
          )}
        </CardContent>
      </Card>
    </>
  )
}

function EvolutionTree({ node, currentDex }: { node: EvolutionNode; currentDex: number }) {
  const isCurrent = node.dex === currentDex

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link
        to={`/dex/${node.dex}`}
        className={cn(
          'rounded-lg px-3 py-1.5 text-sm transition-colors',
          isCurrent
            ? 'bg-primary/10 font-medium text-primary ring-1 ring-primary/30'
            : 'bg-muted hover:bg-muted/70',
        )}
      >
        #{String(node.dex).padStart(3, '0')} {node.name}
      </Link>
      {node.evolves_to.map((child, index) => (
        <div key={child.dex + index} className="flex flex-wrap items-center gap-2">
          <span aria-hidden="true" className="text-muted-foreground">
            →
          </span>
          <EvolutionTree node={child} currentDex={currentDex} />
        </div>
      ))}
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Card>
        <CardContent className="space-y-3 pt-6">
          <Skeleton className="h-3 w-12" />
          <Skeleton className="h-8 w-48" />
          <div className="flex gap-1.5">
            <Skeleton className="h-5 w-10" />
            <Skeleton className="h-5 w-10" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-3 pt-6">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-2 flex-1" />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
