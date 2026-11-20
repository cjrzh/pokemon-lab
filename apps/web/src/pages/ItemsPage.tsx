/**
 * 道具列表页：搜索 + 分类筛选 + 分页。
 *
 * 视觉沿用招式列表页的控制卡：一张卡里放全部筛选，分类用胶囊按钮，
 * 道具行展示 30×30 图标、中文名 + 英文名、分类与说明。
 * 数据只读；道具中文名与说明来自 PokéAPI（说明只有英文，界面不猜译）。
 */

import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Backpack, CircleAlert, ChevronLeft, ChevronRight, RefreshCw, Search, X } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ItemIcon } from '@/features/dex/components/ItemIcon'
import { resolveMediaUrl } from '@/features/dex/api'
import { useDebouncedValue } from '@/features/dex/hooks'
import { pageItems } from '@/features/dex/pagination'
import { itemDisplayName, type ItemListParams, type ItemSummary } from '@/features/items/api'
import { useItemList } from '@/features/items/hooks'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const
const DEFAULT_PAGE_SIZE = 50

export function ItemsPage() {
  // 搜索词与 URL 同步：冠军图鉴等页面用 `/items?q=<名称>` 直接定位到某个道具
  const [searchParams, setSearchParams] = useSearchParams()
  const qParam = searchParams.get('q') ?? ''

  const [search, setSearch] = useState(qParam)
  const [category, setCategory] = useState('all')
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE)
  const [page, setPage] = useState(1)

  // URL 的 q 变化时同步输入框（渲染期调整，避免多一轮渲染）
  const [syncedQ, setSyncedQ] = useState(qParam)
  if (syncedQ !== qParam) {
    setSyncedQ(qParam)
    setSearch(qParam)
    setPage(1)
  }

  const updateSearch = (value: string) => {
    setSearch(value)
    setPage(1)
    const next = new URLSearchParams(searchParams)
    if (value.trim()) next.set('q', value.trim())
    else next.delete('q')
    setSearchParams(next, { replace: true })
  }

  const debounced = useDebouncedValue(search, 300)
  const params: ItemListParams = useMemo(
    () => ({
      page,
      page_size: pageSize,
      q: debounced.trim() || undefined,
      category: category === 'all' ? undefined : category,
    }),
    [page, pageSize, debounced, category],
  )
  const list = useItemList(params)

  const total = list.data?.meta.total ?? 0
  const totalPages = list.data?.meta.total_pages ?? 1
  const categories = list.data?.categories ?? []
  const hasFilters = search.trim().length > 0 || category !== 'all'

  const reset = () => {
    updateSearch('')
    setCategory('all')
    setPage(1)
  }

  const goToPage = (target: number) => {
    setPage(Math.min(Math.max(1, target), totalPages))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <PageHeader
        title="道具"
        description="携带道具的中文名、分类、说明与图标。数据来自 PokéAPI，覆盖双打统计里实际出现过的道具；说明字段上游只有英文，界面不猜译。"
        actions={
          <Badge variant="outline" className="gap-1 tabular-nums">
            <Backpack aria-hidden="true" className="size-3.5 text-muted-foreground" />
            {list.data ? `${total} 个` : '—'}
          </Badge>
        }
      />

      {/* ---------- 搜索与筛选 ---------- */}
      <div className="panel mb-4 space-y-2.5 p-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1">
            <Search
              aria-hidden="true"
              className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={search}
              onChange={(event) => updateSearch(event.target.value)}
              placeholder="搜索道具名、英文名或说明…"
              className="h-10 pl-9"
              aria-label="搜索道具"
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

          {hasFilters ? (
            <Button size="sm" variant="ghost" onClick={reset}>
              <X aria-hidden="true" />
              清除筛选
            </Button>
          ) : null}
        </div>

        {/* 分类胶囊：横向滚动，数量来自接口的分类统计 */}
        <div
          className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:thin]"
          role="group"
          aria-label="按分类筛选"
        >
          <button
            type="button"
            onClick={() => {
              setCategory('all')
              setPage(1)
            }}
            aria-pressed={category === 'all'}
            className={cn(
              'shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              category === 'all'
                ? 'border-transparent bg-foreground text-background'
                : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            全部
          </button>
          {categories.map((option) => {
            const active = category === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  setCategory(active ? 'all' : option.value)
                  setPage(1)
                }}
                aria-pressed={active}
                className={cn(
                  'shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  active
                    ? 'border-primary/40 bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {option.label}
                <span className="ml-1 text-[10px] tabular-nums opacity-70">{option.count}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* ---------- 四态 ---------- */}
      {list.isPending ? (
        <ItemListSkeleton />
      ) : list.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>道具加载失败</AlertTitle>
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
          {total === 0
            ? '尚未导入道具数据 —— 在后台运行 scripts/sync_items.py 后即可查看。'
            : '没有匹配的道具 —— 试试更换关键词或分类。'}
          {hasFilters ? (
            <div className="mt-3">
              <Button size="sm" variant="outline" onClick={reset}>
                清除筛选
              </Button>
            </div>
          ) : null}
        </Card>
      ) : (
        <>
          <ItemRows items={list.data.items} />

          <nav
            aria-label="道具分页"
            className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4"
          >
            <p className="text-xs text-muted-foreground">
              共 <span className="font-medium text-foreground tabular-nums">{total}</span> 个道具 ·
              第 {list.data.meta.page}/{totalPages} 页
            </p>
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-muted-foreground">
                每页
                <select
                  value={pageSize}
                  onChange={(event) => {
                    setPageSize(Number(event.target.value))
                    setPage(1)
                  }}
                  aria-label="每页条数"
                  className="ml-1 h-7 rounded-md border border-input bg-background px-1.5 text-xs tabular-nums"
                >
                  {PAGE_SIZE_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                size="icon-sm"
                variant="outline"
                aria-label="上一页"
                disabled={page <= 1}
                onClick={() => goToPage(page - 1)}
              >
                <ChevronLeft aria-hidden="true" />
              </Button>
              <PageButtons
                page={list.data.meta.page}
                totalPages={totalPages}
                onChange={goToPage}
              />
              <Button
                size="icon-sm"
                variant="outline"
                aria-label="下一页"
                disabled={page >= totalPages}
                onClick={() => goToPage(page + 1)}
              >
                <ChevronRight aria-hidden="true" />
              </Button>
            </div>
          </nav>
        </>
      )}

      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        道具名称与图标来自 PokéAPI 公开数据 · 宝可梦相关名称、形象与商标归 任天堂 / GAME
        FREAK / Creatures Inc. 所有
      </p>
    </>
  )
}

function ItemRows({ items }: { items: ItemSummary[] }) {
  return (
    <ul className="space-y-1.5" aria-label="道具列表">
      {items.map((item) => {
        const name = itemDisplayName(item)
        return (
          <li
            key={item.name}
            className="flex items-start gap-3 rounded-2xl border border-border/60 bg-card px-3.5 py-3 text-sm shadow-[var(--card-glow)] transition-colors hover:border-primary/25"
          >
            <ItemIcon src={resolveMediaUrl(item.icon_url)} alt={name} className="mt-0.5 size-7" />
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="font-medium">{name}</span>
                {item.name_en && item.name_en !== name ? (
                  <span className="text-[11px] text-muted-foreground">{item.name_en}</span>
                ) : null}
                {item.category_zh ? (
                  <span className="rounded-full bg-muted px-1.5 py-0 text-[10px] text-muted-foreground">
                    {item.category_zh}
                  </span>
                ) : null}
              </p>
              {item.effect_zh ? (
                <div className="mt-0.5 space-y-0.5">
                  <p className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                    {item.effect_zh}
                  </p>
                  {item.effect_zh_source === 'project' && item.effect_en ? (
                    <details className="group">
                      <summary className="cursor-pointer list-none text-[10px] text-muted-foreground/70 hover:text-foreground">
                        <span className="group-open:hidden">项目自译 · 查看英文原文</span>
                        <span className="hidden group-open:inline">英文原文</span>
                      </summary>
                      <p className="mt-0.5 text-[10px] leading-relaxed text-muted-foreground/70">
                        {item.effect_en}
                      </p>
                    </details>
                  ) : null}
                </div>
              ) : item.effect_en ? (
                <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                  {item.effect_en}
                </p>
              ) : (
                <p className="mt-0.5 text-[11px] text-muted-foreground/70">暂无说明</p>
              )}
            </div>
            {item.cost != null && item.cost > 0 ? (
              <span className="shrink-0 text-[10px] text-muted-foreground tabular-nums">
                ₽{item.cost}
              </span>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

function PageButtons({
  page,
  totalPages,
  onChange,
}: {
  page: number
  totalPages: number
  onChange: (page: number) => void
}) {
  if (totalPages <= 1) return null
  return (
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
  )
}

function ItemListSkeleton() {
  return (
    <ul className="space-y-1.5" aria-busy="true">
      {Array.from({ length: 8 }, (_, index) => (
        <li key={index}>
          <Skeleton className="h-16 w-full rounded-xl" />
        </li>
      ))}
    </ul>
  )
}
