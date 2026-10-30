import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Crown,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { resolveMediaUrl } from '@/features/dex/api'
import {
  RATING_SOURCE_LABEL,
  type AbilityListParams,
  type AbilityTier,
} from '@/features/abilities/api'
import { useAbilityDetail, useAbilityList, useUpdateAbilityRating } from '@/features/abilities/hooks'
import { useDebouncedValue } from '@/features/dex/hooks'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 30

type TierFilter = 'all' | AbilityTier

export function AbilitiesPage() {
  // 支持从图鉴详情 / 列表带着 `?q=<slug>` 跳转过来，直接定位到该特性。
  const [searchParams, setSearchParams] = useSearchParams()
  const queryParam = searchParams.get('q') ?? ''
  const expandParam = searchParams.get('expand')

  const [search, setSearch] = useState(queryParam)
  const [tier, setTier] = useState<TierFilter>('all')
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(expandParam)

  // URL 的 q 变化时同步搜索框（在渲染期根据「上一次的 q」调整，避免额外一轮渲染）
  const [synced, setSynced] = useState({ q: queryParam, expand: expandParam })
  if (synced.q !== queryParam || synced.expand !== expandParam) {
    setSynced({ q: queryParam, expand: expandParam })
    setSearch(queryParam)
    setPage(1)
    setExpanded(expandParam)
  }

  const debouncedSearch = useDebouncedValue(search, 300)
  const params: AbilityListParams = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      q: debouncedSearch.trim() || undefined,
      tier: tier === 'all' ? undefined : tier,
    }),
    [page, debouncedSearch, tier],
  )

  const list = useAbilityList(params)
  const totalPages = list.data?.meta.total_pages ?? 1

  // 目标行出现后滚动到视口中央（列表是异步加载的，不能在挂载时直接滚）
  const targetRef = useRef<HTMLLIElement | null>(null)
  const located = list.data?.items.some((item) => item.name === expandParam) ?? false
  useEffect(() => {
    if (!expandParam || !located) return
    targetRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [expandParam, located])

  const updateSearchParam = (value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value.trim()) next.set('q', value.trim())
    else next.delete('q')
    next.delete('expand')
    setSearchParams(next, { replace: true })
  }

  return (
    <>
      <PageHeader
        title="特性"
        description="查看特性说明与评级，展开可看到拥有该特性的宝可梦。S 级特性在图鉴中会标红显示。"
        actions={
          <Badge variant="outline" className="tabular-nums">
            S 级 {list.data?.meta.s_tier_total ?? '—'}
          </Badge>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1">
          <Search
            aria-hidden="true"
            className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
              // 搜索框变化时清掉「定位」参数，避免残留的展开状态
              if (expandParam) {
                const next = new URLSearchParams(searchParams)
                next.delete('expand')
                setSearchParams(next, { replace: true })
              }
            }}
            placeholder="搜索特性名或说明…"
            className="h-9 pl-8"
            aria-label="搜索特性"
          />
          {search ? (
            <button
              type="button"
              onClick={() => {
                updateSearchParam('')
                setSearch('')
                setPage(1)
              }}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="清空搜索"
            >
              <X aria-hidden="true" className="size-3.5" />
            </button>
          ) : null}
        </div>

        <div className="inline-flex rounded-lg border p-0.5" role="group" aria-label="按评级筛选">
          {(
            [
              { value: 'all', label: '全部' },
              { value: 's', label: 'S 级' },
              { value: 'normal', label: '普通' },
            ] as const
          ).map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                setTier(option.value)
                setPage(1)
              }}
              aria-pressed={tier === option.value}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                tier === option.value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {list.isPending ? (
        <AbilityListSkeleton />
      ) : list.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>特性加载失败</AlertTitle>
          <AlertDescription>{describeApiError(list.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void list.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : list.data.items.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          没有匹配的特性。
        </Card>
      ) : (
        <>
          <ul className="space-y-2">
            {list.data.items.map((ability) => (
              <li
                key={ability.name}
                ref={ability.name === expandParam ? targetRef : undefined}
                className={cn(
                  'scroll-mt-24 rounded-xl',
                  // 从图鉴跳转过来时给目标行一个短暂的定位高亮
                  ability.name === expandParam && 'ring-2 ring-primary/40',
                )}
              >
                <AbilityRow
                  ability={ability}
                  expanded={expanded === ability.name}
                  onToggle={() => setExpanded(expanded === ability.name ? null : ability.name)}
                />
              </li>
            ))}
          </ul>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              共 {list.data.meta.total} 个特性 · 第 {list.data.meta.page}/{totalPages} 页
            </p>
            <div className="flex items-center gap-1.5">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                <ChevronLeft aria-hidden="true" />
                上一页
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                下一页
                <ChevronRight aria-hidden="true" />
              </Button>
            </div>
          </div>
        </>
      )}

      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        S 级评级为 LLM 预评，可在展开的面板中人工修改并记录理由；修改后自动评级不再覆盖。
      </p>
    </>
  )
}

function AbilityRow({
  ability,
  expanded,
  onToggle,
}: {
  ability: {
    name: string
    zh: string | null
    effect_zh: string | null
    tier: AbilityTier
    rating_source: 'llm' | 'manual'
    rating_note: string | null
    holder_count: number
  }
  expanded: boolean
  onToggle: () => void
}) {
  const isS = ability.tier === 's'
  return (
    <Card className={cn('overflow-hidden p-0', isS && 'ring-primary/40')}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
      >
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2">
            {isS ? (
              <Badge className="gap-1 bg-primary text-primary-foreground">
                <Crown aria-hidden="true" className="size-3" />
                S 级
              </Badge>
            ) : null}
            <span
              className={cn(
                'font-medium',
                isS && 'font-bold text-destructive dark:text-destructive',
              )}
            >
              {ability.zh ?? ability.name}
            </span>
            {ability.zh ? (
              <span className="text-xs text-muted-foreground">{ability.name}</span>
            ) : null}
            <span className="text-xs text-muted-foreground tabular-nums">
              {ability.holder_count} 只宝可梦
            </span>
          </p>
          {ability.effect_zh ? (
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{ability.effect_zh}</p>
          ) : null}
        </div>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            'mt-1 size-4 shrink-0 text-muted-foreground transition-transform',
            expanded && 'rotate-180',
          )}
        />
      </button>
      {expanded ? <AbilityExpanded name={ability.name} /> : null}
    </Card>
  )
}

function AbilityExpanded({ name }: { name: string }) {
  const detail = useAbilityDetail(name)
  const [note, setNote] = useState<string | null>(null)
  const update = useUpdateAbilityRating(name)

  if (detail.isPending) {
    return (
      <CardContent className="border-t pt-4">
        <Skeleton className="h-4 w-64" />
        <Skeleton className="mt-2 h-4 w-48" />
      </CardContent>
    )
  }
  if (detail.isError) {
    return (
      <CardContent className="border-t pt-4">
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertDescription>{describeApiError(detail.error)}</AlertDescription>
        </Alert>
      </CardContent>
    )
  }

  const ability = detail.data
  const isS = ability.tier === 's'

  return (
    <CardContent className="space-y-4 border-t pt-4">
      {ability.effect_zh ? (
        <p className="text-sm leading-relaxed">{ability.effect_zh}</p>
      ) : ability.effect_en ? (
        <p className="text-sm leading-relaxed text-muted-foreground">{ability.effect_en}</p>
      ) : null}

      <div className="rounded-lg bg-muted/50 p-3 text-sm">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          <Sparkles aria-hidden="true" className="size-3.5 text-muted-foreground" />
          评级：{isS ? 'S 级' : '普通'}
          <Badge variant="outline" className="text-[10px]">
            {RATING_SOURCE_LABEL[ability.rating_source]}
          </Badge>
        </p>
        {ability.rating_note ? (
          <p className="mt-1 text-muted-foreground">{ability.rating_note}</p>
        ) : null}

        <div className="mt-2 flex flex-wrap items-end gap-2">
          <label className="flex flex-1 flex-col gap-1 text-xs text-muted-foreground">
            人工修改理由（可选）
            <Input
              value={note ?? ability.rating_note ?? ''}
              onChange={(event) => setNote(event.target.value)}
              className="h-8"
              placeholder="为什么这样评级"
            />
          </label>
          <Button
            size="sm"
            variant="outline"
            disabled={update.isPending}
            onClick={() =>
              update.mutate({ tier: isS ? 'normal' : 's', note: note ?? ability.rating_note })
            }
          >
            {update.isPending ? (
              <RefreshCw aria-hidden="true" className="animate-spin" />
            ) : (
              <Crown aria-hidden="true" />
            )}
            {isS ? '改为普通' : '标为 S 级'}
          </Button>
        </div>
        {update.isError ? (
          <p className="mt-1 text-xs text-destructive">{describeApiError(update.error)}</p>
        ) : null}
      </div>

      <div>
        <p className="mb-2 text-xs font-medium text-muted-foreground">
          拥有该特性的宝可梦（{ability.holders.length}）
        </p>
        {ability.holders.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无记录。</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {ability.holders.map((holder) => (
              <li key={holder.dex_number}>
                <Link
                  to={`/dex/${holder.dex_number}`}
                  className="group inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition-colors hover:border-primary/40 hover:bg-muted"
                >
                  <PokemonSprite
                    src={resolveMediaUrl(holder.sprite_url)}
                    alt={holder.name_zh ?? holder.name_en}
                    type={holder.types[0]}
                    className="size-6"
                  />
                  <span className="text-muted-foreground tabular-nums">
                    #{String(holder.dex_number).padStart(4, '0')}
                  </span>
                  <span className="font-medium group-hover:text-primary">
                    {holder.name_zh ?? holder.name_en}
                  </span>
                  {holder.is_hidden ? (
                    <span className="rounded bg-muted px-1 text-[10px] text-muted-foreground">
                      隐藏
                    </span>
                  ) : null}
                  {holder.types.map((type) => (
                    <TypeBadge key={type} type={type} className="px-1 py-0 text-[9px]" />
                  ))}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </CardContent>
  )
}

function AbilityListSkeleton() {
  return (
    <ul className="space-y-2" aria-busy="true">
      {Array.from({ length: 8 }, (_, index) => (
        <li key={index}>
          <Card className="p-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="mt-2 h-3 w-full max-w-md" />
          </Card>
        </li>
      ))}
    </ul>
  )
}
