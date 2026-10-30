import { useEffect, useMemo, useState } from 'react'
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  LayoutGrid,
  List,
  Maximize2,
  Minimize2,
  RefreshCw,
  Search,
  X,
} from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { DexGridCard } from '@/features/dex/components/DexGridCard'
import { DexListTable } from '@/features/dex/components/DexListTable'
import { useDebouncedValue, usePokemonList } from '@/features/dex/hooks'
import { pageItems, pageRange } from '@/features/dex/pagination'
import {
  DENSITY_LABEL,
  GRID_CLASSES,
  LIST_PAGE_SIZES,
  SORT_LABEL,
  loadPrefs,
  pageSizeFor,
  savePrefs,
  shiftDensity,
  type DexDensity,
  type DexSort,
  type DexView,
  type ListPageSize,
} from '@/features/dex/view'
import { TYPES, typeChartMeta } from '@/features/type-chart/data'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const GENERATIONS = [
  { value: 'all', label: '全部世代' },
  { value: '1', label: '第 1 世代 · 关都' },
  { value: '2', label: '第 2 世代 · 城都' },
  { value: '3', label: '第 3 世代 · 丰缘' },
  { value: '4', label: '第 4 世代 · 神奥' },
  { value: '5', label: '第 5 世代 · 合众' },
  { value: '6', label: '第 6 世代 · 卡洛斯' },
  { value: '7', label: '第 7 世代 · 阿罗拉' },
  { value: '8', label: '第 8 世代 · 伽勒尔' },
  { value: '9', label: '第 9 世代 · 帕底亚' },
]

export function DexPage() {
  const [search, setSearch] = useState('')
  const [type, setType] = useState<string>('all')
  const [generation, setGeneration] = useState<string>('all')
  const [page, setPage] = useState(1)

  // 视图偏好：从 localStorage 初始化（非法值自动回落），改动后写回
  const [prefs, setPrefs] = useState(loadPrefs)
  const { view, density, listSize, sort } = prefs
  const pageSize = pageSizeFor(view, density, listSize)

  useEffect(() => {
    savePrefs(prefs)
  }, [prefs])

  const debouncedSearch = useDebouncedValue(search, 300)

  const params = useMemo(
    () => ({
      page,
      page_size: pageSize,
      q: debouncedSearch.trim() || undefined,
      type: type === 'all' ? undefined : type,
      generation: generation === 'all' ? undefined : Number(generation),
      sort,
    }),
    [page, pageSize, debouncedSearch, type, generation, sort],
  )
  const list = usePokemonList(params)

  const totalPages = list.data?.meta.total_pages ?? 1
  const total = list.data?.meta.total ?? 0
  const hasFilters = type !== 'all' || generation !== 'all' || search.trim().length > 0
  const activeType = TYPES.find((item) => item.name === type)

  /** 切换视图 / 密度后回到第 1 页：每页条数变了，旧页码没有意义。 */
  const changePrefs = (
    next: Partial<{
      view: DexView
      density: DexDensity
      listSize: ListPageSize
      sort: DexSort
    }>,
  ) => {
    setPrefs((current) => ({ ...current, ...next }))
    setPage(1)
  }

  const resetFilters = () => {
    setSearch('')
    setType('all')
    setGeneration('all')
    setPage(1)
  }

  const goToPage = (target: number) => {
    setPage(Math.min(Math.max(1, target), totalPages))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <PageHeader
        title="图鉴"
        description="全国图鉴 #1–1025：检索宝可梦，查看立绘、分类、图鉴描述、种族值、特性、进化链、全部招式与双打配置。数据来自 PokéAPI 同步到本地，离线可用。"
        actions={
          <Badge variant="outline" className="gap-1 tabular-nums">
            <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />
            {list.data ? `${total} 只` : '—'}
          </Badge>
        }
      />

      {/* ---------- 搜索与筛选：一张控制卡，搜索 / 世代 / 属性在同一视觉层级 ---------- */}
      <div className="mb-5 rounded-xl border bg-card/60 p-3 shadow-sm sm:p-3.5">
        <div className="flex flex-wrap items-center gap-2">
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
              placeholder="搜索中文名、英文名或图鉴编号…"
              className="h-9 pl-8"
              aria-label="搜索宝可梦"
            />
            {search ? (
              <button
                type="button"
                onClick={() => {
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

          <div className="relative">
            <select
              value={generation}
              onChange={(event) => {
                setGeneration(event.target.value)
                setPage(1)
              }}
              className="h-9 appearance-none rounded-lg border border-input bg-background pr-8 pl-3 text-sm text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              aria-label="按登场世代筛选"
            >
              {GENERATIONS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <ChevronRight
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 rotate-90 text-muted-foreground"
            />
          </div>

          {hasFilters ? (
            <Button size="sm" variant="ghost" onClick={resetFilters}>
              <X aria-hidden="true" />
              清除筛选
            </Button>
          ) : null}

          <ViewControls
            view={view}
            density={density}
            listSize={listSize}
            sort={sort}
            onChangeSort={(next) => changePrefs({ sort: next })}
            onChangeView={(next) => changePrefs({ view: next })}
            onChangeDensity={(next) => changePrefs({ density: next })}
            onChangeListSize={(next) => changePrefs({ listSize: next })}
          />
        </div>

        {/* 属性筛选：横向可滚动的色块；选中时整块填充该属性色 */}
        <div
          className="-mx-1 mt-2.5 flex gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:thin]"
          role="group"
          aria-label="按属性筛选"
        >
          <button
            type="button"
            onClick={() => {
              setType('all')
              setPage(1)
            }}
            aria-pressed={type === 'all'}
            className={cn(
              'shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              type === 'all'
                ? 'border-transparent bg-foreground text-background'
                : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            全部
          </button>
          {TYPES.map(({ name, zh }) => {
            const active = type === name
            return (
              <button
                key={name}
                type="button"
                onClick={() => {
                  setType(active ? 'all' : name)
                  setPage(1)
                }}
                aria-pressed={active}
                className={cn(
                  'shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-all',
                  active
                    ? 'scale-105 border-transparent shadow-sm'
                    : 'border-border opacity-85 hover:opacity-100',
                )}
                style={{
                  backgroundColor: active ? `var(--type-${name})` : 'transparent',
                  color: active ? `var(--type-${name}-fg)` : 'var(--muted-foreground)',
                }}
              >
                {zh}
              </button>
            )
          })}
        </div>
      </div>

      {/* ---------- 当前筛选摘要 ---------- */}
      {hasFilters && list.data ? (
        <p className="mb-4 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          筛选结果
          <span className="font-medium text-foreground tabular-nums">{total}</span>
          只
          {activeType ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-foreground">
              <span
                aria-hidden="true"
                className="size-1.5 rounded-full"
                style={{ backgroundColor: `var(--type-${activeType.name})` }}
              />
              {activeType.zh}
            </span>
          ) : null}
          {generation !== 'all' ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-foreground">
              {GENERATIONS.find((item) => item.value === generation)?.label}
            </span>
          ) : null}
          {search.trim() ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-foreground">
              “{search.trim()}”
            </span>
          ) : null}
          {sort !== 'dex' ? (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
              {SORT_LABEL[sort]}
            </span>
          ) : null}
        </p>
      ) : null}

      {/* ---------- 四态渲染 ---------- */}
      {list.isPending ? (
        <DexListSkeleton view={view} density={density} />
      ) : list.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>图鉴加载失败</AlertTitle>
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
          没有匹配的宝可梦 —— 试试更换关键词或属性筛选。
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={resetFilters}>
              清除筛选
            </Button>
          </div>
          <div className="mt-2 text-xs">
            当前本地已同步 {total} 条，可在后台管理页触发同步扩大范围。
          </div>
        </Card>
      ) : (
        <>
          {view === 'list' ? (
            <DexListTable
              items={list.data.items}
              sort={sort}
              onSort={(next) => changePrefs({ sort: next })}
            />
          ) : (
            <ul className={cn('grid gap-3', GRID_CLASSES[density])}>
              {list.data.items.map((p) => (
                <li key={p.dex_number}>
                  <DexGridCard pokemon={p} dense={density === 'compact'} />
                </li>
              ))}
            </ul>
          )}

          <Pagination
            page={list.data.meta.page}
            totalPages={totalPages}
            total={total}
            pageSize={list.data.meta.page_size}
            onChange={goToPage}
          />
        </>
      )}

      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        {typeChartMeta.label} · 立绘与图鉴文本来自 PokéAPI / pokemon.com 公开图鉴资源 ·
        宝可梦名称与形象版权归任天堂 / GAME FREAK / Creatures Inc. 所有
      </p>
    </>
  )
}

function ViewControls({
  view,
  density,
  listSize,
  sort,
  onChangeView,
  onChangeDensity,
  onChangeListSize,
  onChangeSort,
}: {
  view: DexView
  density: DexDensity
  listSize: ListPageSize
  sort: DexSort
  onChangeView: (view: DexView) => void
  onChangeDensity: (density: DexDensity) => void
  onChangeListSize: (size: ListPageSize) => void
  onChangeSort: (sort: DexSort) => void
}) {
  return (
    <div className="ml-auto flex flex-wrap items-center gap-1.5">
      {/* 排序：编号 / 种族值各两档；改变后回到第 1 页 */}
      <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        排序
        <span className="relative">
          <select
            value={sort}
            onChange={(event) => onChangeSort(event.target.value as DexSort)}
            aria-label="排序方式"
            className="h-7 appearance-none rounded-md border border-input bg-background pr-6 pl-2 text-xs text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            {(Object.keys(SORT_LABEL) as DexSort[]).map((value) => (
              <option key={value} value={value}>
                {SORT_LABEL[value]}
              </option>
            ))}
          </select>
          <ChevronDown
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 right-1.5 size-3 -translate-y-1/2 text-muted-foreground"
          />
        </span>
      </label>

      {/* 视图切换：卡片 / 列表 */}
      <div
        className="inline-flex rounded-lg border p-0.5"
        role="group"
        aria-label="切换视图"
      >
        <button
          type="button"
          onClick={() => onChangeView('card')}
          aria-pressed={view === 'card'}
          className={cn(
            'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
            view === 'card'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          <LayoutGrid aria-hidden="true" className="size-3.5" />
          卡片
        </button>
        <button
          type="button"
          onClick={() => onChangeView('list')}
          aria-pressed={view === 'list'}
          className={cn(
            'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
            view === 'list'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          <List aria-hidden="true" className="size-3.5" />
          列表
        </button>
      </div>

      {/* 列表模式：每页条数（后端上限 200） */}
      {view === 'list' ? (
        <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          每页
          <span className="relative">
            <select
              value={listSize}
              onChange={(event) => onChangeListSize(Number(event.target.value) as ListPageSize)}
              aria-label="列表每页条数"
              className="h-7 appearance-none rounded-md border border-input bg-background pr-6 pl-2 text-xs text-foreground tabular-nums focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {LIST_PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
            <ChevronDown
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 right-1.5 size-3 -translate-y-1/2 text-muted-foreground"
            />
          </span>
        </label>
      ) : null}

      {/* 密度：只在卡片模式有意义；列表模式固定按行显示 */}
      {view === 'card' ? (
        <div className="inline-flex items-center rounded-lg border p-0.5" role="group" aria-label="调整卡片大小">
          <button
            type="button"
            onClick={() => onChangeDensity(shiftDensity(density, -1))}
            disabled={density === 'compact'}
            aria-label="缩小卡片"
            className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
          >
            <Minimize2 aria-hidden="true" className="size-3.5" />
          </button>
          <span className="w-8 text-center text-[11px] text-muted-foreground tabular-nums">
            {DENSITY_LABEL[density]}
          </span>
          <button
            type="button"
            onClick={() => onChangeDensity(shiftDensity(density, 1))}
            disabled={density === 'large'}
            aria-label="放大卡片"
            className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
          >
            <Maximize2 aria-hidden="true" className="size-3.5" />
          </button>
        </div>
      ) : null}
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
      aria-label="图鉴分页"
      className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t pt-4"
    >
      <p className="text-xs text-muted-foreground">
        第 <span className="font-medium text-foreground tabular-nums">{from}–{to}</span> 只 ·
        共 <span className="font-medium text-foreground tabular-nums">{total}</span> 只
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
                <PageButton
                  key={item}
                  page={item}
                  active={item === page}
                  onClick={() => onChange(item)}
                />
              ),
            )}
          </div>
        ) : null}

        {/* 移动端只保留「当前 / 总数」，避免页码挤成两行 */}
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

function PageButton({
  page,
  active,
  onClick,
}: {
  page: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'h-7 min-w-7 rounded-md px-1.5 text-xs font-medium tabular-nums transition-colors',
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {page}
    </button>
  )
}

function DexListSkeleton({ view, density }: { view: DexView; density: DexDensity }) {
  if (view === 'list') {
    return (
      <div className="space-y-1.5" aria-busy="true">
        {Array.from({ length: 10 }, (_, index) => (
          <Skeleton key={index} className="h-8 w-full rounded-lg" />
        ))}
      </div>
    )
  }
  return (
    <ul className={cn('grid gap-3', GRID_CLASSES[density])} aria-busy="true">
      {Array.from({ length: 12 }, (_, index) => (
        <li key={index}>
          <Card className="gap-2.5 p-2.5">
            <div className="flex justify-between">
              <Skeleton className="h-3 w-10" />
              <Skeleton className="h-3 w-8" />
            </div>
            <Skeleton className="aspect-square w-full rounded-lg" />
            <Skeleton className="h-4 w-20" />
            <div className="flex gap-1.5">
              <Skeleton className="h-4 w-10 rounded-md" />
              <Skeleton className="h-4 w-10 rounded-md" />
            </div>
            <Skeleton className="h-2.5 w-24" />
          </Card>
        </li>
      ))}
    </ul>
  )
}
