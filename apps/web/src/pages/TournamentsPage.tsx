/**
 * 官方赛事页。
 *
 * 两块内容：
 *   1. 赛事列表：按规则 / 类型 / 年份筛选，显示冠军、人数、队表数；
 *      **赛事名是链接**，点进 `/tournaments/{id}` 查看详情（队伍 / 使用率 / 名次）；
 *   2. 同步：增量同步 Limitless VGC 的官方赛事数据（后台任务 + 进度）。
 *
 * 列表页只做「找到赛事」；详情独立成页 —— 它有三个视图与分页，塞在列表下方
 * 会让页面变得很长，也无法直接分享或回退。
 *
 * 与「历史使用率」页的区别：那边是 Smogon **天梯**统计（按月 / 等级线），
 * 这边是**线下官方赛事**的实际参赛队伍与使用率，两者口径不同、不混用。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ChevronRight,
  CircleAlert,
  Download,
  Loader2,
  RefreshCw,
  Search,
  Square,
  Trophy,
  X,
} from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useDebouncedValue } from '@/features/dex/hooks'
import { pageRange } from '@/features/dex/pagination'
import {
  useActiveTournamentSync,
  useCancelTournamentSync,
  useRefreshTournaments,
  useStartTournamentSync,
  useTournaments,
} from '@/features/tournaments/hooks'
import type {
  TournamentQueryParams,
  TournamentSummary,
  TournamentSyncRun,
} from '@/features/tournaments/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 20

export function TournamentsPage() {
  const [search, setSearch] = useState('')
  const debounced = useDebouncedValue(search, 300)
  const [ruleset, setRuleset] = useState<string | null>(null)
  const [eventType, setEventType] = useState<string | null>(null)
  const [year, setYear] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [runId, setRunId] = useState<number | null>(null)

  const params = useMemo<TournamentQueryParams>(
    () => ({
      ruleset: ruleset ?? undefined,
      event_type: eventType ?? undefined,
      year: year ?? undefined,
      q: debounced.trim() || undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [ruleset, eventType, year, debounced, page],
  )
  const list = useTournaments(params)

  const sync = useStartTournamentSync()
  const cancel = useCancelTournamentSync()
  // 刷新页面后也跟随「最近一次同步」轮询，而不是停在加载那一刻
  const activeSync = useActiveTournamentSync(runId)
  const activeRun = activeSync.run
  const refreshTournaments = useRefreshTournaments()

  // 同步从 running 变成终态时刷新列表（新赛事 / 新队表）
  const previousStatusRef = useRef<string | null>(null)
  const runStatus = activeRun?.status ?? null
  useEffect(() => {
    const previous = previousStatusRef.current
    previousStatusRef.current = runStatus
    if (previous === 'running' && runStatus && runStatus !== 'running') {
      refreshTournaments()
    }
  }, [runStatus, refreshTournaments])

  const items = list.data?.items ?? []
  const totalPages = list.data?.total_pages ?? 1
  const rulesets = list.data?.rulesets ?? []
  const years = list.data?.years ?? []

  const onSync = (payload: { types?: string[]; refresh?: boolean }) => {
    sync.mutate(payload, {
      onSuccess: (created) => {
        previousStatusRef.current = 'running'
        setRunId(created.id)
      },
    })
  }

  return (
    <>
      <PageHeader
        title="官方赛事"
        description="VGC 官方比赛（地区赛 / 国际赛 / 世锦赛 / 特殊赛事 / 国家赛）的规则、名次、选手队表与赛事使用率。数据来自 Limitless VGC，可按需增量同步。"
        actions={<SyncBadge run={activeRun} />}
      />

      <SyncBar
        run={activeRun}
        starting={sync.isPending}
        onRecent={() => onSync({ types: ['regional'] })}
        onFull={() => onSync({})}
        onRefresh={() => onSync({ refresh: true })}
        onCancel={() => {
          if (activeRun?.status === 'running') cancel.mutate(activeRun.id)
        }}
        error={sync.error ? describeApiError(sync.error) : null}
      />

      {/* ---------- 筛选 ---------- */}
      <div className="panel mb-4 space-y-2.5 p-3.5">
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="按年份筛选">
          <FilterChip active={year === null} onClick={() => { setYear(null); setPage(1) }}>
            全部年份
          </FilterChip>
          {years.map((value) => (
            <FilterChip
              key={value}
              active={year === value}
              onClick={() => { setYear(value); setPage(1) }}
            >
              {value}
            </FilterChip>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="按规则筛选">
          <FilterChip active={ruleset === null} onClick={() => { setRuleset(null); setPage(1) }}>
            全部规则
          </FilterChip>
          {rulesets.map((item) => (
            <FilterChip
              key={item.identifier}
              active={ruleset === item.identifier}
              onClick={() => { setRuleset(item.identifier); setPage(1) }}
              title={item.label}
            >
              {item.label}
              {item.format_key ? null : (
                <span className="ml-1 text-[9px] opacity-70">只读</span>
              )}
            </FilterChip>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="按赛事类型筛选">
            <FilterChip
              active={eventType === null}
              onClick={() => { setEventType(null); setPage(1) }}
            >
              全部类型
            </FilterChip>
            {EVENT_TYPE_OPTIONS.map((item) => (
              <FilterChip
                key={item.value}
                active={eventType === item.value}
                onClick={() => { setEventType(item.value); setPage(1) }}
              >
                {item.label}
              </FilterChip>
            ))}
          </div>
          <div className="relative min-w-52 flex-1">
            <Search
              aria-hidden="true"
              className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              placeholder="搜索赛事名或冠军…"
              className="h-10 pl-9"
              aria-label="搜索赛事"
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
        </div>
      </div>

      {/* ---------- 列表 / 详情 ---------- */}
      {list.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-14 w-full" />
          ))}
        </div>
      ) : list.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>无法加载赛事列表</AlertTitle>
          <AlertDescription>{describeApiError(list.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void list.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="space-y-2 pt-6 text-center text-sm text-muted-foreground">
            <Trophy aria-hidden="true" className="mx-auto size-6" />
            <p>还没有赛事数据。</p>
            <p className="text-xs">点上方「同步最近赛事」抓取最近一届地区赛，或「同步全部」回补历史。</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <ul className="divide-y divide-border/60 overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[var(--card-glow)]">
            {items.map((item) => (
              <li key={item.id}>
                <EventRow item={item} />
              </li>
            ))}
          </ul>

          {totalPages > 1 ? (
            <nav className="mt-4 flex flex-wrap items-center justify-center gap-1" aria-label="赛事分页">
              <Button
                size="xs"
                variant="outline"
                disabled={(list.data?.page ?? 1) <= 1}
                onClick={() => setPage(Math.max(1, (list.data?.page ?? 1) - 1))}
              >
                上一页
              </Button>
              <span className="px-2 text-[11px] text-muted-foreground tabular-nums">
                {pageRange(list.data?.page ?? 1, PAGE_SIZE, list.data?.total ?? 0)[0]}–
                {pageRange(list.data?.page ?? 1, PAGE_SIZE, list.data?.total ?? 0)[1]} /{' '}
                {list.data?.total ?? 0}
              </span>
              <Button
                size="xs"
                variant="outline"
                disabled={(list.data?.page ?? 1) >= totalPages}
                onClick={() => setPage(Math.min(totalPages, (list.data?.page ?? 1) + 1))}
              >
                下一页
              </Button>
            </nav>
          ) : null}
        </>
      )}
    </>
  )
}

const EVENT_TYPE_OPTIONS = [
  { value: 'regional', label: '地区赛' },
  { value: 'international', label: '国际赛' },
  { value: 'worlds', label: '世锦赛' },
  { value: 'special', label: '特殊赛事' },
  { value: 'national', label: '国家赛' },
  { value: 'players_cup', label: 'Players Cup' },
] as const

/**
 * 列表的一行：整行可点，赛事名是真正的链接（可中键新标签打开、可复制地址）。
 */
function EventRow({ item }: { item: TournamentSummary }) {
  return (
    <Link
      to={`/tournaments/${item.id}`}
      className="group flex w-full flex-wrap items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-primary/[0.045] focus-visible:bg-primary/[0.045] focus-visible:outline-none"
    >
      <span className="w-20 shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">
        {item.date}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="truncate text-sm font-medium text-primary group-hover:underline group-hover:underline-offset-2">
            {item.name}
          </span>
          <Badge variant="outline" className="text-[10px]">{item.event_type_label}</Badge>
          <Badge variant="secondary" className="text-[10px]">{item.ruleset_label}</Badge>
          {item.format_key ? null : (
            <Badge variant="outline" className="text-[10px] text-muted-foreground">
              本地不可建队
            </Badge>
          )}
        </span>
        <span className="mt-0.5 flex flex-wrap gap-x-3 text-[11px] text-muted-foreground">
          <span>{item.players} 人</span>
          {item.winner ? <span>冠军 {item.winner}</span> : null}
          <span>队表 {item.team_count > 0 ? item.team_count : '—'}</span>
          <span>名次 {item.standings_count}</span>
        </span>
      </span>
      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground transition-colors group-hover:text-primary">
        查看
        <ChevronRight aria-hidden="true" className="size-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  )
}

function SyncBadge({ run }: { run: TournamentSyncRun | null }) {
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
        <Trophy aria-hidden="true" className="size-3" />
      )}
      {text}
    </Badge>
  )
}

function SyncBar({
  run,
  starting,
  onRecent,
  onFull,
  onRefresh,
  onCancel,
  error,
}: {
  run: TournamentSyncRun | null
  starting: boolean
  onRecent: () => void
  onFull: () => void
  onRefresh: () => void
  onCancel: () => void
  error: string | null
}) {
  const running = run?.status === 'running'
  const percent = run && run.total > 0 ? Math.round((run.done / run.total) * 100) : 0
  return (
    <Card className="mb-4 bg-card/80">
      <CardContent className="space-y-2 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={onFull} disabled={starting || running}>
            {starting || running ? (
              <Loader2 aria-hidden="true" className="animate-spin" />
            ) : (
              <Download aria-hidden="true" />
            )}
            同步全部赛事
          </Button>
          <Button size="sm" variant="outline" onClick={onRecent} disabled={starting || running}>
            <Trophy aria-hidden="true" />
            只同步地区赛
          </Button>
          <Button size="sm" variant="ghost" onClick={onRefresh} disabled={starting || running}>
            <RefreshCw aria-hidden="true" />
            强制重抓
          </Button>
          {running ? (
            <Button size="sm" variant="ghost" onClick={onCancel}>
              <Square aria-hidden="true" />
              取消
            </Button>
          ) : null}
          <span className="text-[11px] text-muted-foreground">
            增量同步：已抓过队表的赛事会跳过
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
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${percent}%` }} />
            </div>
            <p className="flex flex-wrap gap-x-3 text-[11px] text-muted-foreground tabular-nums">
              <span>{run?.done} / {run?.total}</span>
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
  title,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
  title?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={title}
      className={cn(
        'rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors',
        active
          ? 'border-primary/30 bg-primary/10 text-primary shadow-[inset_0_1px_0_rgb(255_255_255/0.25)]'
          : 'border-border/70 text-muted-foreground hover:border-primary/25 hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}
