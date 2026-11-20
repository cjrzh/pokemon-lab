/**
 * 冠军图鉴：Pokémon Champions 双打（Reg M-C）的独立图鉴页。
 *
 * 与「使用率」页的区别：这里只锁定冠军双打一个格式，把该格式最有用的信息
 * 摊开成一页 —— 排名、使用率、常见招式 / 特性 / 道具、能力点配点，点开进详情。
 *
 * 数据来自 Smogon 月度统计快照（`/usage-ranking?format=champions`），
 * 页面必须如实展示规则、月份与等级线，不能把旧数据说成当前环境。
 */

import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, CircleAlert, RefreshCw, Search, Trophy, X } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { spreadText } from '@/features/champions/api'
import { useChampionsRanking } from '@/features/champions/hooks'
import { ItemIcon } from '@/features/dex/components/ItemIcon'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { useDebouncedValue } from '@/features/dex/hooks'
import { pageRange } from '@/features/dex/pagination'
import { formatMonth, formatPct } from '@/features/doubles/api'
import { usageDisplayName, type UsageRankingItem } from '@/features/usage/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const PAGE_SIZE_OPTIONS = [24, 48, 96] as const
const DEFAULT_PAGE_SIZE = 24

export function ChampionsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const qParam = searchParams.get('q') ?? ''

  const [search, setSearch] = useState(qParam)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE)

  // URL 的 q 变化时同步本地输入（渲染期调整，避免多一轮渲染）
  const [syncedQ, setSyncedQ] = useState(qParam)
  if (syncedQ !== qParam) {
    setSyncedQ(qParam)
    setSearch(qParam)
    setPage(1)
  }

  const debounced = useDebouncedValue(search, 300)
  const params = useMemo(
    () => ({ q: debounced.trim() || undefined, page, page_size: pageSize }),
    [debounced, page, pageSize],
  )
  const ranking = useChampionsRanking(params)

  const items = ranking.data?.items ?? []
  const format = ranking.data?.formats.find((item) => item.key === 'champions')
  const hasData = ranking.data?.has_data ?? false
  const total = ranking.data?.meta.total ?? 0
  const totalPages = ranking.data?.meta.total_pages ?? 1

  const updateSearch = (value: string) => {
    setSearch(value)
    setPage(1)
    const next = new URLSearchParams(searchParams)
    if (value.trim()) next.set('q', value.trim())
    else next.delete('q')
    setSearchParams(next, { replace: true })
  }

  const goToPage = (target: number) => {
    setPage(Math.min(Math.max(1, target), totalPages))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <PageHeader
        title="冠军图鉴"
        description="Pokémon Champions 双打使用率图鉴：排名、常见配装与能力点分配。数据为 Smogon 公开月度统计快照，不是实时对战数据。"
        actions={
          <Badge variant="outline" className="text-xs">
            <Trophy aria-hidden="true" />
            {format ? `${format.ruleset} · 双打` : '双打'}
          </Badge>
        }
      />

      {format ? (
        <div className="panel mb-5 flex flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-3 text-xs">
          <span className="font-medium text-foreground">{format.label}</span>
          <span className="rounded-full bg-muted/70 px-2 py-0.5 text-muted-foreground">
            {formatMonth(format.month)} · cutoff {format.cutoff}
          </span>
          <span className="text-muted-foreground tabular-nums">
            {format.battles.toLocaleString()} 场对战
          </span>
          <span className="text-muted-foreground tabular-nums">收录 {format.entries} 只</span>
          <span className="text-muted-foreground">配点单位：能力点</span>
          {format.source_url ? (
            <a
              href={format.source_url}
              target="_blank"
              rel="noreferrer"
              className="ml-auto underline underline-offset-2 hover:text-foreground"
            >
              数据原文
            </a>
          ) : null}
          {format.note ? (
            <p className="w-full text-[11px] text-muted-foreground">{format.note}</p>
          ) : null}
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1 sm:max-w-sm">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            aria-label="搜索冠军图鉴"
            placeholder="搜索中文名 / 英文名 / 编号"
            value={search}
            onChange={(event) => updateSearch(event.target.value)}
            className="pl-9"
          />
          {search ? (
            <button
              type="button"
              aria-label="清除搜索"
              onClick={() => updateSearch('')}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded-full p-1 text-muted-foreground hover:text-foreground"
            >
              <X aria-hidden="true" className="size-3.5" />
            </button>
          ) : null}
        </div>

        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          每页
          <select
            aria-label="每页条数"
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number(event.target.value))
              setPage(1)
            }}
            className="h-9 rounded-lg border border-input bg-transparent px-2 text-xs"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>

        <span className="text-xs text-muted-foreground tabular-nums">共 {total} 只</span>
      </div>

      {ranking.isPending ? (
        <ChampionsSkeleton count={Math.min(pageSize, 12)} />
      ) : ranking.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>冠军图鉴加载失败</AlertTitle>
          <AlertDescription>{describeApiError(ranking.error)}</AlertDescription>
          <AlertAction>
            <Button size="sm" variant="outline" onClick={() => void ranking.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : !hasData ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          还没有导入冠军双打数据 —— 到后台同步页导入{' '}
          <code className="rounded bg-muted px-1">data/doubles/champions.json</code> 后即可查看。
        </Card>
      ) : items.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          没有匹配的宝可梦 —— 试试更换关键词。
          {search.trim() ? (
            <div className="mt-3">
              <Button size="sm" variant="outline" onClick={() => updateSearch('')}>
                清除搜索
              </Button>
            </div>
          ) : null}
        </Card>
      ) : (
        <>
          <ol
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3"
            aria-label="冠军双打使用率图鉴"
          >
            {items.map((item) => (
              <ChampionCard
                key={`${item.showdown_name}-${item.rank ?? 0}`}
                item={item}
                pointsKind={format?.points_kind ?? 'stat_points'}
              />
            ))}
          </ol>

          <Pagination
            page={page}
            totalPages={totalPages}
            total={total}
            pageSize={pageSize}
            onChange={goToPage}
          />
        </>
      )}

      <p className="mt-6 text-center text-[11px] leading-relaxed text-muted-foreground">
        数据来自 Smogon University 公开的月度天梯统计
        {format ? `（${formatMonth(format.month)}，等级线 ${format.cutoff} 以上）` : ''}
        ，为历史快照而非实时环境。Champions 使用能力点（单项上限 32）且无个体值系统。
        宝可梦名称与形象版权归任天堂 / GAME FREAK / Creatures Inc. 所有。
      </p>
    </>
  )
}

function ChampionCard({
  item,
  pointsKind,
}: {
  item: UsageRankingItem
  pointsKind: 'ev' | 'stat_points'
}) {
  const name = usageDisplayName(item)
  const spread = item.spread
  const href = item.dex_number != null ? `/champions/${item.dex_number}` : null

  const body = (
    <div
      className={cn(
        'flex h-full flex-col gap-2 rounded-2xl border border-border/60 bg-card px-3.5 py-3 text-sm shadow-[var(--card-glow)] transition-all duration-300',
        href &&
          'group-hover:-translate-y-0.5 group-hover:border-primary/25 group-hover:shadow-[0_20px_44px_-30px_rgb(30_40_120/0.55)]',
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            'flex size-7 shrink-0 items-center justify-center rounded-full font-heading text-xs font-semibold tabular-nums',
            item.rank === 1 &&
              'bg-[linear-gradient(145deg,#fcd34d,#f59e0b)] text-[#3b2100] shadow-[0_6px_16px_-6px_rgb(245_158_11/0.75)]',
            item.rank === 2 &&
              'bg-[linear-gradient(145deg,#e2e8f0,#94a3b8)] text-[#1e293b] shadow-[0_6px_16px_-8px_rgb(148_163_184/0.8)]',
            item.rank === 3 &&
              'bg-[linear-gradient(145deg,#f3c39a,#c2763f)] text-[#2b1205] shadow-[0_6px_16px_-8px_rgb(194_118_63/0.8)]',
            (item.rank == null || item.rank > 3) && 'text-muted-foreground',
          )}
        >
          {item.rank ?? '—'}
        </span>

        <div
          className="relative size-11 shrink-0 overflow-hidden rounded-xl ring-1 ring-inset ring-foreground/5"
          style={{
            background: `linear-gradient(160deg, color-mix(in oklab, var(--type-${item.types[0] ?? 'normal'}) 18%, transparent), transparent 72%)`,
          }}
        >
          <PokemonSprite
            src={resolveMediaUrl(item.sprite_url)}
            alt={name}
            type={item.types[0]}
            className="size-full rounded-xl"
          />
        </div>

        <div className="min-w-0 flex-1">
          <p className="flex min-w-0 flex-wrap items-baseline gap-x-1.5">
            <span className="truncate text-sm font-semibold">{name}</span>
            <span className="truncate text-[10px] text-muted-foreground">
              {item.dex_number != null ? `#${String(item.dex_number).padStart(4, '0')}` : ''}
            </span>
          </p>
          <span className="mt-0.5 flex flex-wrap items-center gap-1">
            {item.types.map((type) => (
              <TypeBadge key={type} type={type} className="px-1.5 py-0 text-[10px]" />
            ))}
          </span>
        </div>

        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold tabular-nums">
            {item.usage != null ? formatPct(item.usage) : '—'}
          </p>
          <p className="text-[10px] text-muted-foreground tabular-nums">
            样本 {item.raw_count.toLocaleString()}
          </p>
        </div>
      </div>

      <span className="block h-1.5 overflow-hidden rounded-full bg-muted/70">
        <span
          className="block h-full rounded-full bg-[linear-gradient(90deg,var(--primary),var(--brand-cyan))]"
          style={{ width: `${Math.min(100, item.usage ?? 0)}%` }}
        />
      </span>

      {item.moves.length > 0 ? (
        <p className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[11px] text-muted-foreground">
          <span className="text-foreground/70">招式</span>
          {item.moves.slice(0, 4).map((move) => (
            <span key={move.slug} className="inline-flex items-center gap-0.5">
              {move.type ? <TypeBadge type={move.type} className="px-1 py-0 text-[9px]" /> : null}
              <span>{move.name}</span>
            </span>
          ))}
        </p>
      ) : null}

      <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
        {item.abilities[0] ? <span>特性 {item.abilities[0].name}</span> : null}
        {item.items[0] ? (
          <span className="inline-flex items-center gap-0.5">
            <ItemIcon
              src={resolveMediaUrl(item.items[0].icon_url)}
              alt={item.items[0].name}
              className="size-3.5"
            />
            {item.items[0].name}
          </span>
        ) : null}
      </p>

      {spread ? (
        <p className="mt-auto border-t border-border/50 pt-1.5 text-[10px] text-muted-foreground tabular-nums">
          {spread.nature_label} · {spreadText(spread, pointsKind)}
        </p>
      ) : null}
    </div>
  )

  if (!href) {
    // 映射不到图鉴的条目：保留展示，但不生成假链接
    return <li>{body}</li>
  }
  return (
    <li>
      <Link
        to={href}
        aria-label={`${name} 的冠军配装（使用率 ${item.usage != null ? formatPct(item.usage) : '—'}）`}
        className="group block h-full rounded-2xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        {body}
      </Link>
    </li>
  )
}

function ChampionsSkeleton({ count }: { count: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }, (_, index) => (
        <Card key={index} className="h-[132px] p-3.5">
          <Skeleton className="h-full w-full" />
        </Card>
      ))}
    </div>
  )
}

function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onChange,
}: {
  page: number
  totalPages: number
  total: number
  pageSize: number
  onChange: (page: number) => void
}) {
  const [from, to] = pageRange(page, pageSize, total)

  return (
    <nav
      aria-label="冠军图鉴分页"
      className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4"
    >
      <p className="text-xs text-muted-foreground">
        第{' '}
        <span className="font-medium text-foreground tabular-nums">
          {from}–{to}
        </span>{' '}
        名 · 共 <span className="font-medium text-foreground tabular-nums">{total}</span> 条
      </p>

      <div className="flex items-center gap-1">
        <Button
          size="icon-sm"
          variant="outline"
          aria-label="上一页"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" />
        </Button>
        <span className="px-2 text-xs text-muted-foreground tabular-nums">
          {page} / {totalPages}
        </span>
        <Button
          size="icon-sm"
          variant="outline"
          aria-label="下一页"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight aria-hidden="true" />
        </Button>
      </div>
    </nav>
  )
}
