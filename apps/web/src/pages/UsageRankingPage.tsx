/**
 * 对战使用率排行页：按格式查看 Smogon 月度使用率榜单。
 *
 * 布局：
 *   1. 标题 + 当前格式的统计月份 / 等级线 / 对战数（数据是快照，必须显眼）
 *   2. 格式标签（BDSP → 剑盾 → 朱紫 → 冠军），带条目数
 *   3. 搜索与每页条数
 *   4. 排行行：名次、立绘、名称 / 属性、使用率条、常见配装摘要
 *   5. 分页与来源说明
 *
 * 数据与图鉴详情页的「双打对战辅助」同源（doubles_pokemon_stat），
 * 页面只负责展示，不在前端做任何名次计算。
 */

import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  RefreshCw,
  Search,
  Trophy,
  X,
} from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ItemIcon } from '@/features/dex/components/ItemIcon'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { useDebouncedValue } from '@/features/dex/hooks'
import { pageItems, pageRange } from '@/features/dex/pagination'
import { formatMonth, formatPct, pointsUnit } from '@/features/doubles/api'
import {
  isUsageFormat,
  usageDisplayName,
  type UsageFormatInfo,
  type UsageRankingItem,
  type UsageFormat,
} from '@/features/usage/api'
import { useUsageRanking } from '@/features/usage/hooks'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const
const DEFAULT_PAGE_SIZE = 50

export function UsageRankingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const formatParam = searchParams.get('format')
  const qParam = searchParams.get('q') ?? ''

  const [format, setFormat] = useState<UsageFormat>(() =>
    isUsageFormat(formatParam) ? formatParam : 'bdsp',
  )
  const [search, setSearch] = useState(qParam)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE)

  // URL 的 format / q 变化时同步本地状态（在渲染期调整，避免额外一轮渲染）
  const [synced, setSynced] = useState({ format: formatParam, q: qParam })
  if (synced.format !== formatParam || synced.q !== qParam) {
    setSynced({ format: formatParam, q: qParam })
    if (isUsageFormat(formatParam)) setFormat(formatParam)
    setSearch(qParam)
    setPage(1)
  }

  const debounced = useDebouncedValue(search, 300)
  const params = useMemo(
    () => ({
      format,
      q: debounced.trim() || undefined,
      page,
      page_size: pageSize,
    }),
    [format, debounced, page, pageSize],
  )
  const ranking = useUsageRanking(params)

  const formats = ranking.data?.formats ?? []
  const activeFormat = formats.find((item) => item.key === format)
  const totalPages = ranking.data?.meta.total_pages ?? 1
  const total = ranking.data?.meta.total ?? 0
  const items = ranking.data?.items ?? []

  const updateFormat = (next: UsageFormat) => {
    setFormat(next)
    setPage(1)
    const params = new URLSearchParams(searchParams)
    params.set('format', next)
    setSearchParams(params, { replace: true })
  }

  const updateSearch = (value: string) => {
    setSearch(value)
    setPage(1)
    const params = new URLSearchParams(searchParams)
    if (value.trim()) params.set('q', value.trim())
    else params.delete('q')
    params.set('format', format)
    setSearchParams(params, { replace: true })
  }

  const goToPage = (target: number) => {
    setPage(Math.min(Math.max(1, target), totalPages))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <PageHeader
        title="使用率排行"
        description="四个双打格式的 Smogon 月度使用率榜单：名次、出场率，以及每只宝可梦最常见的特性、道具、招式与配点。点名称可进入图鉴详情查看完整配置与 Showdown 导出。"
        actions={
          <Badge variant="outline" className="gap-1 tabular-nums">
            <Trophy aria-hidden="true" className="size-3.5 text-warning" />
            {activeFormat ? `${activeFormat.entries} 只` : '—'}
          </Badge>
        }
      />

      {/* ---------- 格式标签 ---------- */}
      <div className="mb-4 flex flex-wrap gap-1.5" role="group" aria-label="选择双打格式">
        {(formats.length ? formats : fallbackFormats()).map((item) => {
          const isActive = item.key === format
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => updateFormat(item.key)}
              aria-pressed={isActive}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                isActive
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
                !item.imported && !isActive && 'opacity-60',
              )}
            >
              {item.short_label}
              <span className="text-[10px] tabular-nums opacity-80">
                {item.imported ? item.entries : '无数据'}
              </span>
            </button>
          )
        })}
      </div>

      {/* ---------- 当前格式的统计快照信息 ---------- */}
      {activeFormat ? <FormatSummary format={activeFormat} /> : null}

      {/* ---------- 搜索 ---------- */}
      <div className="mb-4 mt-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1">
          <Search
            aria-hidden="true"
            className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={search}
            onChange={(event) => updateSearch(event.target.value)}
            placeholder="搜索中文名、英文名、Showdown 名或图鉴编号…"
            className="h-9 pl-8"
            aria-label="搜索宝可梦"
          />
          {search ? (
            <button
              type="button"
              onClick={() => updateSearch('')}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="清空搜索"
            >
              <X aria-hidden="true" className="size-3.5" />
            </button>
          ) : null}
        </div>

        <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          每页
          <span className="relative">
            <select
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value))
                setPage(1)
              }}
              aria-label="每页条数"
              className="h-8 appearance-none rounded-md border border-input bg-background pr-6 pl-2 text-xs text-foreground tabular-nums focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
            <ChevronRight
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 right-1.5 size-3 -translate-y-1/2 rotate-90 text-muted-foreground"
            />
          </span>
        </label>

        {search.trim() ? (
          <span className="text-xs text-muted-foreground">
            找到 <span className="font-medium text-foreground tabular-nums">{total}</span> 条
          </span>
        ) : null}
      </div>

      {/* ---------- 四态 ---------- */}
      {ranking.isPending ? (
        <RankingSkeleton />
      ) : ranking.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>使用率排行加载失败</AlertTitle>
          <AlertDescription>{describeApiError(ranking.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void ranking.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : !ranking.data.has_data ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          <p>尚未导入双打使用率统计。</p>
          <p className="mt-1 text-xs">
            在后台同步页导入 <code className="rounded bg-muted px-1">data/doubles/*.json</code>
            后即可查看榜单。
          </p>
        </Card>
      ) : items.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          {activeFormat && !activeFormat.imported
            ? '该格式还没有导入统计数据 —— 切换到其它格式，或在后台重新导入。'
            : '没有匹配的宝可梦 —— 试试更换关键词。'}
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
          <RankingList items={items} pointsKind={activeFormat?.points_kind ?? 'ev'} />

          <Pagination
            page={ranking.data.meta.page}
            totalPages={totalPages}
            total={total}
            pageSize={ranking.data.meta.page_size}
            onChange={goToPage}
          />
        </>
      )}

      <p className="mt-6 text-center text-[11px] leading-relaxed text-muted-foreground">
        数据来自 Smogon University 公开的月度天梯统计（{formatMonth(activeFormat?.month ?? '')}
        ，等级线 {activeFormat?.cutoff ?? '—'} 以上），为历史快照而非实时环境。
        宝可梦名称与形象版权归任天堂 / GAME FREAK / Creatures Inc. 所有。
      </p>
    </>
  )
}

/** 接口未返回前用仓库里的格式定义渲染标签骨架（保证四个标签始终可见）。 */
function fallbackFormats(): UsageFormatInfo[] {
  return [
    { key: 'bdsp', label: 'BDSP' },
    { key: 'swsh', label: '剑盾' },
    { key: 'sv', label: '朱紫' },
    { key: 'champions', label: '冠军' },
  ].map((item) => ({
    key: item.key as UsageFormat,
    label: item.label,
    short_label: item.label,
    game: '',
    ruleset: '',
    month: '',
    cutoff: 0,
    points_kind: 'ev',
    battles: 0,
    note: null,
    source_url: null,
    entries: 0,
    imported: false,
  }))
}

function FormatSummary({ format }: { format: UsageFormatInfo }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-xl border bg-card/60 px-3.5 py-2.5 text-xs shadow-sm">
      <span className="font-medium text-foreground">{format.label}</span>
      <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
        {formatMonth(format.month)} · cutoff {format.cutoff}
      </span>
      <span className="text-muted-foreground tabular-nums">
        {format.battles.toLocaleString()} 场对战
      </span>
      <span className="text-muted-foreground">
        配点单位：{pointsUnit(format.points_kind)}
      </span>
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
  )
}

function RankingList({
  items,
  pointsKind,
}: {
  items: UsageRankingItem[]
  pointsKind: 'ev' | 'stat_points'
}) {
  // 条形宽度相对当前页最高使用率；百分比文字仍是绝对值
  const maxUsage = Math.max(1, ...items.map((item) => item.usage ?? 0))

  return (
    <ol className="space-y-1.5" aria-label="使用率排行榜">
      {items.map((item) => (
        <RankingRow
          key={`${item.showdown_name}-${item.rank ?? 0}`}
          item={item}
          maxUsage={maxUsage}
          pointsKind={pointsKind}
        />
      ))}
    </ol>
  )
}

function RankingRow({
  item,
  maxUsage,
  pointsKind,
}: {
  item: UsageRankingItem
  maxUsage: number
  pointsKind: 'ev' | 'stat_points'
}) {
  const name = usageDisplayName(item)
  const spread = item.spread
  const content = (
    <div
      className={cn(
        'grid grid-cols-[2.25rem_3rem_minmax(0,1fr)] items-center gap-x-2.5 gap-y-1.5 rounded-xl bg-card px-2.5 py-2 text-sm ring-1 ring-foreground/10 sm:grid-cols-[2.75rem_3.5rem_minmax(0,1.05fr)_minmax(0,1.25fr)_6.5rem]',
        item.dex_number != null && 'transition-colors group-hover:bg-muted/40',
      )}
    >
      {/* 名次 */}
      <span
        className={cn(
          'text-center font-heading text-lg font-semibold tabular-nums',
          item.rank != null && item.rank <= 3 ? 'text-primary' : 'text-muted-foreground',
        )}
      >
        {item.rank ?? '—'}
      </span>

      {/* 小图标（96×96）：行高受限，用 sprite 而不是 475px 立绘 */}
      <div
        className="relative aspect-square overflow-hidden rounded-lg"
        style={{
          background: `linear-gradient(160deg, color-mix(in oklab, var(--type-${item.types[0] ?? 'normal'}) 18%, transparent), transparent 72%)`,
        }}
      >
        <PokemonSprite
          src={resolveMediaUrl(item.sprite_url)}
          alt={name}
          type={item.types[0]}
          className="size-full rounded-lg"
        />
      </div>

      {/* 名称 / 属性 / 形态 */}
      <div className="min-w-0">
        <p className="flex min-w-0 flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
          <span className="truncate text-sm font-semibold">{name}</span>
          <span className="truncate text-[10px] text-muted-foreground">
            {item.dex_number != null ? `#${String(item.dex_number).padStart(4, '0')} · ` : ''}
            {item.showdown_name}
          </span>
        </p>
        <span className="mt-0.5 flex flex-wrap items-center gap-1">
          {item.types.map((type) => (
            <TypeBadge key={type} type={type} className="px-1.5 py-0 text-[10px]" />
          ))}
        </span>
      </div>

      {/* 常见配装摘要 */}
      <div className="col-span-3 min-w-0 space-y-0.5 text-[11px] text-muted-foreground sm:col-span-1">
        {item.moves.length > 0 ? (
          <p className="flex flex-wrap items-center gap-x-1 gap-y-0.5">
            <span className="text-foreground/70">招式</span>
            {item.moves.map((move) => (
              <span key={move.slug} className="inline-flex items-center gap-0.5">
                {move.type ? (
                  <TypeBadge type={move.type} className="px-1 py-0 text-[9px]" />
                ) : null}
                <span>{move.name}</span>
              </span>
            ))}
          </p>
        ) : null}
        <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
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
          {spread ? (
            <span className="tabular-nums">
              {spread.nature_label} · {spread.points.join('/')} {pointsUnit(pointsKind)}
            </span>
          ) : null}
        </p>
      </div>

      {/* 使用率 */}
      <div className="col-span-3 sm:col-span-1">
        <p className="text-right text-sm font-semibold tabular-nums">
          {item.usage != null ? formatPct(item.usage) : '—'}
        </p>
        <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-muted">
          <span
            className="block h-full rounded-full bg-primary/70"
            style={{
              width: `${Math.min(100, ((item.usage ?? 0) / maxUsage) * 100)}%`,
            }}
          />
        </span>
        <p className="mt-0.5 text-right text-[10px] text-muted-foreground tabular-nums">
          样本 {item.raw_count.toLocaleString()}
        </p>
      </div>
    </div>
  )

  if (item.dex_number == null) {
    // 名称无法映射到图鉴（如 Showdown 特有形态）：保留展示，但不做假链接
    return <li>{content}</li>
  }
  return (
    <li>
      <Link
        to={`/dex/${item.dex_number}`}
        className="group block rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        aria-label={`${name} 使用率第 ${item.rank ?? '—'} 名`}
      >
        {content}
      </Link>
    </li>
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
      aria-label="排行分页"
      className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4"
    >
      <p className="text-xs text-muted-foreground">
        第 <span className="font-medium text-foreground tabular-nums">{from}–{to}</span> 名 ·
        共 <span className="font-medium text-foreground tabular-nums">{total}</span> 条
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

        {totalPages > 1 ? (
          <div className="hidden items-center gap-0.5 sm:flex">
            {pageItems(page, totalPages).map((item, index) =>
              item === 'ellipsis' ? (
                <span
                  key={`gap-${index}`}
                  aria-hidden="true"
                  className="px-1 text-xs text-muted-foreground"
                >
                  …
                </span>
              ) : (
                <button
                  key={item}
                  type="button"
                  onClick={() => onChange(item)}
                  aria-current={item === page ? 'page' : undefined}
                  className={cn(
                    'h-7 min-w-7 rounded-md px-1.5 text-xs font-medium tabular-nums transition-colors',
                    item === page
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )}
                >
                  {item}
                </button>
              ),
            )}
          </div>
        ) : null}

        <span className="px-2 text-xs text-muted-foreground tabular-nums sm:hidden">
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

function RankingSkeleton() {
  return (
    <div className="space-y-1.5" aria-busy="true">
      {Array.from({ length: 10 }, (_, index) => (
        <Skeleton key={index} className="h-16 w-full rounded-xl" />
      ))}
      <p className="sr-only">正在加载使用率排行</p>
    </div>
  )
}
