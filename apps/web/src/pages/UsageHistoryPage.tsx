/**
 * 历史使用率页（Smogon）。
 *
 * 与「使用率排行」页的区别：
 *   - 那个页是**四个固定格式的单一快照**（含招式 / 道具 / 配点的深度数据）；
 *   - 这个页是**任意月份 × 格式 × 等级线**的历史排行（只有名次与使用率），
 *     数据由页内「同步」按钮按需抓取，支持增量。
 *
 * 布局：版本筛选 → 规则下拉 → 月份下拉 → 等级线 → 同步状态 → 搜索与榜单。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Database,
  Download,
  Loader2,
  RefreshCw,
  Search,
  Square,
  X,
} from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { useDebouncedValue } from '@/features/dex/hooks'
import { pageItems, pageRange } from '@/features/dex/pagination'
import {
  useActiveSyncRun,
  useCancelSync,
  useRefreshUsageHistory,
  useStartSync,
  useUsageHistory,
} from '@/features/usage-history/hooks'
import type { SyncRun, UsageFormatInfo } from '@/features/usage-history/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const
const DEFAULT_PAGE_SIZE = 50

export function UsageHistoryPage() {
  const [game, setGame] = useState<string>('all')
  const [formatId, setFormatId] = useState<string | null>(null)
  const [month, setMonth] = useState<string | null>(null)
  const [cutoff, setCutoff] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE)
  const [runId, setRunId] = useState<number | null>(null)

  const debounced = useDebouncedValue(search, 300)
  const params = useMemo(
    () => ({
      format: formatId ?? undefined,
      month: month ?? undefined,
      cutoff: cutoff ?? undefined,
      q: debounced.trim() || undefined,
      page,
      page_size: pageSize,
    }),
    [formatId, month, cutoff, debounced, page, pageSize],
  )
  const data = useUsageHistory(params)
  const formats = useMemo(() => data.data?.formats ?? [], [data.data])
  const months = useMemo(() => data.data?.months ?? [], [data.data])
  const totalPages = data.data?.total_pages ?? 1

  // 实际生效的格式 / 月份以接口返回为准（未指定时服务端取默认值）
  const activeFormatId = data.data?.format_id ?? formatId
  const activeFormat = formats.find((item) => item.format_id === activeFormatId)

  const games = useMemo(
    () => [...new Set(formats.map((item) => item.game))],
    [formats],
  )
  const visibleFormats = useMemo(
    () => (game === 'all' ? formats : formats.filter((item) => item.game === game)),
    [formats, game],
  )

  const sync = useStartSync()
  const cancel = useCancelSync()
  /**
   * 同步进度：本页启动的任务优先；**刷新页面后**跟随「最近一次同步」。
   * 以前只在 `runId` 存在时轮询，刷新后进度会停在加载那一刻（一直转圈）。
   */
  const syncRun = useActiveSyncRun(runId)
  const refreshHistory = useRefreshUsageHistory()
  const activeRun = syncRun.run
  const syncing = activeRun?.status === 'running'

  // 同步从 running 变成终态（done / error / cancelled）时刷新榜单：
  // 新快照的月份、条目、「该格式共 N 个月」都会变。刷新页面后跟随的
  // 「最近一次同步」也走这条路径。
  const previousStatusRef = useRef<string | null>(null)
  const runStatus = activeRun?.status ?? null
  useEffect(() => {
    const previous = previousStatusRef.current
    previousStatusRef.current = runStatus
    if (previous === 'running' && runStatus && runStatus !== 'running') {
      refreshHistory()
    }
  }, [runStatus, refreshHistory])

  /** 启动同步并跟踪这次任务（结束后刷新榜单）。 */
  const startRun = (payload: Parameters<typeof sync.mutate>[0]) => {
    sync.mutate(payload, {
      onSuccess: (created) => {
        previousStatusRef.current = 'running'
        setRunId(created.id)
      },
    })
  }

  /** 单条目同步：只同步当前选中的规则（全部历史月份 × 三档等级线）。 */
  const syncActiveFormat = () => {
    if (!activeFormatId) return
    startRun({ format_ids: [activeFormatId] })
  }

  /** 同步当前选中的单个快照（规则 + 月份 + 等级线）。 */
  const syncCurrentSnapshot = () => {
    // 该规则完全没同步时还没有可选月份，只能走「同步本规则」
    if (!data.data?.month) return
    startRun({
      format_ids: [data.data.format_id],
      months: [data.data.month],
      cutoffs: [data.data.cutoff],
    })
  }

  const selectFormat = (item: UsageFormatInfo) => {
    setFormatId(item.format_id)
    setMonth(null) // 换格式后月份列表不同，交回服务端选最新
    setPage(1)
  }

  return (
    <>
      <PageHeader
        title="历史使用率"
        description="Smogon 双打 / VGC 使用率达到任意月份、任意规则与等级线。数据来自 smogon.com/stats，按需同步、增量更新。"
        actions={<SyncBadge run={activeRun} />}
      />

      {/* ---------- 同步条 ---------- */}
      <SyncBar
        run={activeRun}
        starting={sync.isPending}
        onStart={() => startRun({ recent_months: 3 })}
        onBackfill={() => startRun({})}
        onCancel={() => {
          if (activeRun?.status === 'running') cancel.mutate(activeRun.id)
        }}
        error={sync.error ? describeApiError(sync.error) : null}
      />

      {/* ---------- 版本筛选 ---------- */}
      <div className="mb-3 flex flex-wrap items-center gap-1.5" role="group" aria-label="选择版本">
        <FilterChip active={game === 'all'} onClick={() => setGame('all')}>
          全部版本
        </FilterChip>
        {games.map((name) => (
          <FilterChip key={name} active={game === name} onClick={() => setGame(name)}>
            {name}
          </FilterChip>
        ))}
      </div>

      {/* ---------- 规则 / 月份 / 等级线 ---------- */}
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <label className="min-w-56 space-y-1">
          <span className="text-[11px] text-muted-foreground">规则 / 格式</span>
          <select
            value={activeFormatId ?? ''}
            onChange={(event) => {
              const item = formats.find((f) => f.format_id === event.target.value)
              if (item) selectFormat(item)
            }}
            aria-label="规则格式"
            className="h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm"
          >
            {visibleFormats.map((item) => (
              <option key={item.format_id} value={item.format_id}>
                {item.label}
                {item.months === 0 ? '（未同步）' : ''}
              </option>
            ))}
          </select>
        </label>

        {/* 单条目同步：只抓当前这个规则，不必等「全部格式」的同步 */}
        <div className="space-y-1">
          <span className="text-[11px] text-muted-foreground">该规则</span>
          <div className="flex items-center gap-1.5">
            <Button
              size="sm"
              variant="outline"
              className="h-9"
              onClick={syncActiveFormat}
              disabled={sync.isPending || syncing || !activeFormatId}
              title="只同步当前选中的规则（全部历史月份 × 三档等级线，已同步的会跳过）"
            >
              {sync.isPending || syncing ? (
                <Loader2 aria-hidden="true" className="animate-spin" />
              ) : (
                <Download aria-hidden="true" />
              )}
              {activeFormat && activeFormat.months === 0 ? '同步本规则' : '补齐本规则'}
            </Button>
            {activeFormat ? (
              <span className="text-[10px] text-muted-foreground">
                {activeFormat.months > 0
                  ? `已同步 ${activeFormat.months} 个月`
                  : '该规则还没同步'}
              </span>
            ) : null}
          </div>
        </div>

        <label className="space-y-1">
          <span className="text-[11px] text-muted-foreground">月份</span>
          <select
            value={data.data?.month ?? ''}
            onChange={(event) => {
              setMonth(event.target.value)
              setPage(1)
            }}
            aria-label="统计月份"
            disabled={months.length === 0}
            className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm tabular-nums disabled:opacity-50"
          >
            {months.length === 0 ? <option value="">无数据</option> : null}
            {[...months].reverse().map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <div className="space-y-1">
          <span className="text-[11px] text-muted-foreground">等级线</span>
          <div className="flex gap-1" role="group" aria-label="等级线">
            {(data.data?.cutoffs ?? [1500, 1630, 1760]).map((value) => (
              <FilterChip
                key={value}
                active={data.data?.cutoff === value}
                onClick={() => {
                  setCutoff(value)
                  setPage(1)
                }}
              >
                {value === 1500 ? '1500+' : value === 1630 ? '1630+' : '1760+'}
              </FilterChip>
            ))}
          </div>
        </div>
      </div>

      {/* ---------- 快照信息 ---------- */}
      {data.data ? (
        <p className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline" className="font-mono text-[10px]">
            {data.data.format_id}
          </Badge>
          {data.data.has_snapshot ? (
            <span>
              {data.data.month} · cut-off {data.data.cutoff} · {data.data.battles} 场对战 ·{' '}
              {data.data.total} 只
            </span>
          ) : (
            <span className="text-amber-600">
              该快照尚未同步
              {data.data.month
                ? `（${data.data.month} · cut-off ${data.data.cutoff}）`
                : '（该规则还没有任何月份数据）'}
            </span>
          )}
          {activeFormat && activeFormat.months > 0 && months.length > 1 ? (
            <span className="text-[11px]">· 该格式共 {activeFormat.months} 个月</span>
          ) : null}
          {!data.data.has_snapshot ? (
            <Button
              size="xs"
              variant="outline"
              onClick={syncCurrentSnapshot}
              disabled={sync.isPending || syncing || !data.data.month}
              title={
                data.data.month
                  ? `只同步 ${data.data.format_id} ${data.data.month} cut-off ${data.data.cutoff}`
                  : '该规则还没有任何月份数据，请先同步本规则'
              }
            >
              {sync.isPending || syncing ? (
                <Loader2 aria-hidden="true" className="animate-spin" />
              ) : (
                <Download aria-hidden="true" />
              )}
              同步该月份 / 等级线
            </Button>
          ) : null}
        </p>
      ) : null}

      {/* ---------- 搜索 ---------- */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
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
            }}
            placeholder="搜索 Showdown 名或图鉴编号…"
            className="h-9 pl-8"
            aria-label="搜索宝可梦"
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="清空搜索"
            >
              <X aria-hidden="true" className="size-3.5" />
            </button>
          ) : null}
        </div>
        <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          每页
          <select
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number(event.target.value))
              setPage(1)
            }}
            aria-label="每页条数"
            className="h-8 rounded-md border border-input bg-background px-2 text-xs tabular-nums"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* ---------- 榜单 ---------- */}
      {data.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      ) : data.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>无法加载使用率数据</AlertTitle>
          <AlertDescription>{describeApiError(data.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void data.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : (data.data?.items.length ?? 0) === 0 ? (
        <Card>
          <CardContent className="space-y-2 pt-6 text-center text-sm text-muted-foreground">
            <Database aria-hidden="true" className="mx-auto size-6" />
            {data.data && !data.data.has_snapshot ? (
              <>
                <p>
                  这个规则在这个月份 / 等级线还没有同步
                  {activeFormat ? `（${activeFormat.label}）` : ''}。
                </p>
                <div className="flex flex-wrap items-center justify-center gap-1.5">
                  <Button
                    size="sm"
                    onClick={syncActiveFormat}
                    disabled={sync.isPending || syncing}
                  >
                    {sync.isPending || syncing ? (
                      <Loader2 aria-hidden="true" className="animate-spin" />
                    ) : (
                      <Download aria-hidden="true" />
                    )}
                    同步本规则（全部历史）
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={syncCurrentSnapshot}
                    disabled={sync.isPending || syncing || !data.data.month}
                    title={
                      data.data.month
                        ? '只抓当前选中的月份与等级线'
                        : '该规则还没有任何月份数据，请先同步本规则'
                    }
                  >
                    只同步这个快照
                  </Button>
                </div>
                <p className="text-xs">
                  已同步的月份 / 等级线会跳过；也可以只抓当前选中的月份与等级线。
                </p>
              </>
            ) : (
              <>
                <p>这个月份 / 格式 / 等级线还没有数据。</p>
                <p className="text-xs">点上方「同步数据」抓取最近几个月，或「回补全部历史」。</p>
              </>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          <ul className="divide-y divide-border/60 overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[var(--card-glow)]">
            {data.data?.items.map((item) => (
              <li key={item.showdown_name} className="flex items-center gap-2.5 px-3.5 py-2.5 transition-colors hover:bg-primary/[0.045]">
                <span className="w-8 shrink-0 text-right font-mono text-[11px] text-muted-foreground tabular-nums">
                  {item.rank}
                </span>
                <PokemonSprite
                  src={resolveMediaUrl(item.sprite_url)}
                  alt={item.name_zh ?? item.showdown_name}
                  type={item.types[0]}
                  className="size-7 shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-1.5 text-sm">
                    {item.dex_number ? (
                      <Link
                        to={`/dex/${item.dex_number}`}
                        className="font-medium underline-offset-2 hover:text-primary hover:underline"
                      >
                        {item.name_zh ?? item.name_en ?? item.showdown_name}
                      </Link>
                    ) : (
                      <span className="font-medium">{item.showdown_name}</span>
                    )}
                    {item.types.map((type) => (
                      <TypeBadge key={type} type={type} className="px-1 py-0 text-[9px]" />
                    ))}
                  </p>
                  <p className="truncate text-[10px] text-muted-foreground">
                    {item.showdown_name}
                  </p>
                </div>
                <div className="w-28 shrink-0">
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.min(100, item.usage)}%` }}
                    />
                  </div>
                </div>
                <span className="w-14 shrink-0 text-right text-xs tabular-nums">
                  {item.usage.toFixed(2)}%
                </span>
              </li>
            ))}
          </ul>

          {totalPages > 1 ? (
            <nav
              className="mt-4 flex flex-wrap items-center justify-center gap-1"
              aria-label="使用率分页"
            >
              <Button
                size="xs"
                variant="outline"
                disabled={(data.data?.page ?? 1) <= 1}
                onClick={() => {
                  setPage(Math.max(1, (data.data?.page ?? 1) - 1))
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                <ChevronLeft aria-hidden="true" />
              </Button>
              {pageItems(data.data?.page ?? 1, totalPages).map((item, index) =>
                item === 'ellipsis' ? (
                  <span key={`e${index}`} className="px-1 text-xs text-muted-foreground">
                    …
                  </span>
                ) : (
                  <Button
                    key={item}
                    size="xs"
                    variant={item === data.data?.page ? 'default' : 'outline'}
                    onClick={() => {
                      setPage(item)
                      window.scrollTo({ top: 0, behavior: 'smooth' })
                    }}
                  >
                    {item}
                  </Button>
                ),
              )}
              <Button
                size="xs"
                variant="outline"
                disabled={(data.data?.page ?? 1) >= totalPages}
                onClick={() => {
                  setPage(Math.min(totalPages, (data.data?.page ?? 1) + 1))
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                <ChevronRight aria-hidden="true" />
              </Button>
              <span className="ml-2 text-[11px] text-muted-foreground tabular-nums">
                {pageRange(data.data?.page ?? 1, pageSize, data.data?.total ?? 0)[0]}–
                {pageRange(data.data?.page ?? 1, pageSize, data.data?.total ?? 0)[1]} /{' '}
                {data.data?.total ?? 0}
              </span>
            </nav>
          ) : null}
        </>
      )}
    </>
  )
}

function SyncBadge({ run }: { run: SyncRun | null }) {
  if (!run) return null
  const text =
    run.status === 'running'
      ? '同步中'
      : run.status === 'error'
        ? '同步失败'
        : run.status === 'cancelled'
          ? '已取消'
          : '已同步'
  return (
    <Badge
      variant="outline"
      className={cn(
        'gap-1 tabular-nums',
        run.status === 'running' && 'text-primary',
        run.status === 'error' && 'text-destructive',
      )}
    >
      {run.status === 'running' ? (
        <Loader2 aria-hidden="true" className="size-3 animate-spin" />
      ) : (
        <Database aria-hidden="true" className="size-3" />
      )}
      {text}
    </Badge>
  )
}

function SyncBar({
  run,
  starting,
  onStart,
  onBackfill,
  onCancel,
  error,
}: {
  run: SyncRun | null
  starting: boolean
  onStart: () => void
  onBackfill: () => void
  onCancel: () => void
  error: string | null
}) {
  const running = run?.status === 'running'
  const percent = run && run.total > 0 ? Math.round((run.done / run.total) * 100) : 0

  return (
    <Card className="mb-3">
      <CardContent className="space-y-2 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={onStart} disabled={starting || running}>
            {starting || running ? (
              <Loader2 aria-hidden="true" className="animate-spin" />
            ) : (
              <Download aria-hidden="true" />
            )}
            同步最近 3 个月
          </Button>
          <Button size="sm" variant="outline" onClick={onBackfill} disabled={starting || running}>
            <Database aria-hidden="true" />
            回补全部历史
          </Button>
          {running ? (
            <Button size="sm" variant="ghost" onClick={onCancel}>
              <Square aria-hidden="true" />
              取消
            </Button>
          ) : null}
          <span className="text-[11px] text-muted-foreground">
            增量同步：已抓过的月份 / 等级线会跳过
          </span>
        </div>

        {running || (run && run.done > 0) ? (
          <div className="space-y-1">
            <div
              className="h-1.5 overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${percent}%` }}
              />
            </div>
            <p className="flex flex-wrap gap-x-3 text-[11px] text-muted-foreground tabular-nums">
              <span>
                {run?.done} / {run?.total}
              </span>
              <span>新增 {run?.created}</span>
              <span>跳过 {run?.skipped}</span>
              {run && run.failed > 0 ? (
                <span className="text-destructive">失败 {run.failed}</span>
              ) : null}
              {run?.current ? <span>正在处理 {run.current}</span> : null}
            </p>
            {run?.message ? (
              <p className="text-[11px] text-muted-foreground">{run.message}</p>
            ) : null}
          </div>
        ) : null}

        {error ? <p className="text-xs text-destructive">{error}</p> : null}
      </CardContent>
    </Card>
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
        'rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors',
        active
          ? 'border-primary/40 bg-primary/10 text-primary'
          : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}
