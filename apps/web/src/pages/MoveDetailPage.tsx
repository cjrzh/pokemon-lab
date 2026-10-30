/**
 * 招式详情页：数值 + 图鉴说明 + 「谁会这招」。
 *
 * 学习者按世代分组（版本组从新到旧），每个宝可梦卡片可点击回到图鉴详情；
 * 图鉴详情页的招式表也链接回这里 —— 双向导航。
 */

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CircleAlert, RefreshCw, Search, Sparkles, Star, Users } from 'lucide-react'

import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import {
  DAMAGE_CLASS_LABEL,
  DAMAGE_CLASS_TONE,
  moveDisplayName,
  type MoveDetail,
  type MoveLearnerPokemon,
} from '@/features/moves/api'
import { useMoveDetail } from '@/features/moves/hooks'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

export function MoveDetailPage() {
  const { moveName } = useParams<{ moveName: string }>()
  const detail = useMoveDetail(moveName ?? null)

  return (
    <div className="space-y-4">
      <Button asChild size="sm" variant="ghost" className="-ml-2">
        <Link to="/moves">
          <ArrowLeft aria-hidden="true" />
          返回招式列表
        </Link>
      </Button>

      {detail.isPending ? (
        <MoveDetailSkeleton />
      ) : detail.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>无法加载招式详情</AlertTitle>
          <AlertDescription>{describeApiError(detail.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void detail.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : (
        <MoveDetailBody move={detail.data} />
      )}
    </div>
  )
}

/** 详情页默认展示最新版本组，并提供切换。 */
function MoveDetailBody({ move }: { move: MoveDetail }) {
  const versionKeys = useMemo(
    () => Object.keys(move.learners_by_version),
    [move.learners_by_version],
  )
  const [version, setVersion] = useState<string | null>(versionKeys[0] ?? null)
  const [method, setMethod] = useState<string | 'all'>('all')
  const [query, setQuery] = useState('')

  const visible = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return move.learners.filter((learner) => {
      if (version) {
        const entries = learner.version_groups[version] ?? []
        if (entries.length === 0) return false
        if (method !== 'all' && !entries.some((entry) => entry.method === method)) return false
      }
      if (keyword) {
        const haystack = `${learner.name_zh ?? ''} ${learner.name_en}`.toLowerCase()
        if (!haystack.includes(keyword)) return false
      }
      return true
    })
  }, [move.learners, version, method, query])

  const methodsInVersion = useMemo(() => {
    if (!version) return Object.keys(move.method_counts)
    const counts = new Set<string>()
    for (const learner of move.learners) {
      for (const entry of learner.version_groups[version] ?? []) counts.add(entry.method)
    }
    return [...counts]
  }, [move.learners, move.method_counts, version])

  return (
    <div className="space-y-4">
      {/* ---------- Hero ---------- */}
      <Card className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background: move.type
              ? `radial-gradient(110% 80% at 6% 0%, color-mix(in oklab, var(--type-${move.type}) 24%, transparent), transparent 62%)`
              : undefined,
          }}
        />
        <div className="relative space-y-3 p-4 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            {move.type ? (
              <TypeBadge type={move.type} className="px-2.5 py-1 text-sm shadow-sm" />
            ) : null}
            {move.damage_class ? (
              <Badge className={cn('border-0', DAMAGE_CLASS_TONE[move.damage_class])}>
                {DAMAGE_CLASS_LABEL[move.damage_class]}
              </Badge>
            ) : null}
            {move.is_machine ? <Badge variant="outline">招式学习器</Badge> : null}
            <Badge variant="outline" className="tabular-nums">
              {move.learner_count} 只可学
            </Badge>
            {version ? (
              <Badge variant="secondary" className="tabular-nums">
                {move.version_labels[version] ?? version} 版 {move.learners_by_version[version] ?? 0} 只
              </Badge>
            ) : null}
          </div>

          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            {moveDisplayName(move)}
          </h1>
          <p className="text-sm text-muted-foreground">
            {[move.name_en, move.name].filter(Boolean).join(' · ')}
          </p>

          <dl className="grid max-w-md grid-cols-3 gap-3 text-sm">
            <Stat label="威力" value={move.power ?? '—'} />
            <Stat label="命中" value={move.accuracy ?? '—'} />
            <Stat label="PP" value={move.pp ?? '—'} />
          </dl>

          {move.description_zh ? (
            <p className="max-w-3xl rounded-xl border border-border/70 bg-card/70 p-3 text-sm leading-relaxed shadow-sm">
              {move.description_zh}
            </p>
          ) : null}
        </div>
      </Card>

      {/* ---------- 谁可以学 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users aria-hidden="true" className="size-4 text-muted-foreground" />
            谁会这招
          </CardTitle>
          <CardDescription>
            按版本筛选：点标题里的版本标签切换。每个宝可梦都可以点击回到图鉴详情。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="选择版本">
            {versionKeys.map((key) => {
              const active = key === version
              const count = move.learners_by_version[key] ?? 0
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setVersion(key)
                    setMethod('all')
                  }}
                  aria-pressed={active}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors',
                    active
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
                  )}
                >
                  {move.version_labels[key] ?? key}
                  <span className="text-[10px] tabular-nums opacity-80">{count}</span>
                </button>
              )
            })}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-1" role="group" aria-label="按学习方式筛选">
              <FilterChip active={method === 'all'} onClick={() => setMethod('all')}>
                全部 {version ? (move.learners_by_version[version] ?? 0) : move.learner_count}
              </FilterChip>
              {methodsInVersion.map((key) => (
                <FilterChip
                  key={key}
                  active={method === key}
                  onClick={() => setMethod(method === key ? 'all' : key)}
                >
                  {move.method_labels[key] ?? key}
                </FilterChip>
              ))}
            </div>

            <div className="relative ml-auto min-w-44">
              <Search
                aria-hidden="true"
                className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="筛选宝可梦…"
                className="h-8 pl-7 text-xs"
                aria-label="筛选宝可梦"
              />
            </div>
          </div>

          {visible.length === 0 ? (
            <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              {version
                ? '该版本没有符合筛选条件的宝可梦。'
                : '暂无学习记录（可能尚未同步招式数据）。'}
            </p>
          ) : (
            <ul className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
              {visible.map((learner) => (
                <li key={learner.dex_number}>
                  <LearnerCard learner={learner} version={version} />
                </li>
              ))}
            </ul>
          )}

          <p className="text-[11px] text-muted-foreground">
            显示 {visible.length} / {version ? (move.learners_by_version[version] ?? 0) : move.learner_count}{' '}
            只。
          </p>
        </CardContent>
      </Card>

      {/* ---------- 各版本覆盖 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle>各版本可学数量</CardTitle>
          <CardDescription>从新到旧；数量为该版本组里能学会这招的宝可梦数。</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-wrap gap-1.5">
            {versionKeys.map((key) => (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => {
                    setVersion(key)
                    setMethod('all')
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition-colors hover:border-primary/40 hover:bg-muted"
                >
                  {move.version_labels[key] ?? key}
                  <span className="text-muted-foreground tabular-nums">
                    {move.learners_by_version[key]}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

function LearnerCard({
  learner,
  version,
}: {
  learner: MoveLearnerPokemon
  version: string | null
}) {
  const entries = version ? (learner.version_groups[version] ?? []) : []
  const methods = entries.length
    ? entries.map((entry) => ({
        label: entry.method_label,
        level: entry.level,
      }))
    : (learner.latest_methods ?? []).map((key) => ({ label: key, level: 0 }))

  return (
    <Link
      to={`/dex/${learner.dex_number}`}
      className="group flex h-full items-center gap-2 rounded-lg border px-2 py-1.5 transition-colors hover:border-primary/40 hover:bg-muted"
    >
      <span className="w-9 shrink-0 font-mono text-[10px] text-muted-foreground tabular-nums">
        #{String(learner.dex_number).padStart(4, '0')}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1">
          {learner.is_legendary ? (
            <Star aria-label="传说的宝可梦" className="size-2.5 shrink-0 text-warning" />
          ) : null}
          {learner.is_mythical ? (
            <Sparkles aria-label="幻之宝可梦" className="size-2.5 shrink-0 text-primary" />
          ) : null}
          <span className="truncate text-xs font-medium group-hover:text-primary">
            {learner.name_zh ?? learner.name_en}
          </span>
        </span>
        <span className="mt-0.5 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[10px] text-muted-foreground">
          {methods.slice(0, 3).map((method) => (
            <span key={method.label} className="inline-flex items-center gap-0.5">
              {method.label}
              {method.level > 0 ? ` Lv.${method.level}` : ''}
            </span>
          ))}
        </span>
      </span>
      <span className="flex shrink-0 gap-0.5">
        {learner.types.map((type) => (
          <TypeBadge key={type} type={type} className="px-1 py-0 text-[9px]" />
        ))}
      </span>
    </Link>
  )
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-md px-2 py-1 text-xs transition-colors',
        active
          ? 'bg-primary/10 font-medium text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

function MoveDetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Card>
        <CardContent className="space-y-3 pt-6">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-9 w-52" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="grid grid-cols-2 gap-2 pt-6 sm:grid-cols-4">
          {Array.from({ length: 8 }, (_, index) => (
            <Skeleton key={index} className="h-10 w-full rounded-lg" />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
