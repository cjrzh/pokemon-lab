import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, CircleAlert, RefreshCw, Search } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { useDebouncedValue, usePokemonList } from '@/features/dex/hooks'
import { TYPES, typeChartMeta } from '@/features/type-chart/data'
import { describeApiError } from '@/lib/apiClient'

const PAGE_SIZE = 20

export function DexPage() {
  const [search, setSearch] = useState('')
  const [type, setType] = useState<string>('all')
  const [page, setPage] = useState(1)

  const debouncedSearch = useDebouncedValue(search, 300)

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      q: debouncedSearch.trim() || undefined,
      type: type === 'all' ? undefined : type,
    }),
    [page, debouncedSearch, type],
  )
  const list = usePokemonList(params)

  const totalPages = list.data?.meta.total_pages ?? 1

  return (
    <>
      <PageHeader
        title="图鉴"
        description={`检索宝可梦，查看属性、种族值、特性与进化信息。数据来自 PokéAPI 同步到本地，离线可用。`}
        actions={<Badge variant="outline">{typeChartMeta.label}</Badge>}
      />

      {/* ---------- 搜索与筛选 ---------- */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1">
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
            placeholder="搜索中文名或英文名…"
            className="pl-8"
            aria-label="搜索宝可梦"
          />
        </div>
        <select
          value={type}
          onChange={(event) => {
            setType(event.target.value)
            setPage(1)
          }}
          className="h-9 rounded-lg border border-input bg-background px-3 text-sm text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          aria-label="按属性筛选"
        >
          <option value="all">全部属性</option>
          {TYPES.map(({ name, zh }) => (
            <option key={name} value={name}>
              {zh}
            </option>
          ))}
        </select>
      </div>

      {/* ---------- 四态渲染 ---------- */}
      {list.isPending ? (
        <DexListSkeleton />
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
          <div className="mt-1 text-xs">
            当前本地已同步 {list.data.meta.total} 条，可在后台管理页触发同步扩大范围。
          </div>
        </Card>
      ) : (
        <>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.data.items.map((p) => (
              <li key={p.dex_number}>
                <Link
                  to={`/dex/${p.dex_number}`}
                  className="group rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  <Card className="h-full p-4 transition-all group-hover:-translate-y-0.5 group-hover:shadow-md group-hover:ring-primary/30">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs text-muted-foreground">#{String(p.dex_number).padStart(3, '0')}</p>
                        <p className="truncate font-medium">
                          {p.name_zh ?? p.name_en}
                          {p.name_zh ? (
                            <span className="ml-1.5 text-xs text-muted-foreground">{p.name_en}</span>
                          ) : null}
                        </p>
                      </div>
                      {p.is_demo ? <Badge variant="secondary">演示数据</Badge> : null}
                    </div>
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {p.types.map((t) => (
                        <TypeBadge key={t} type={t} />
                      ))}
                    </div>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>

          {/* ---------- 分页 ---------- */}
          <div className="mt-4 flex items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              共 {list.data.meta.total} 条 · 第 {list.data.meta.page}/{totalPages} 页
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
    </>
  )
}

function DexListSkeleton() {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
      {Array.from({ length: 9 }, (_, index) => (
        <li key={index}>
          <Card className="p-4">
            <Skeleton className="h-3 w-10" />
            <Skeleton className="mt-2 h-5 w-24" />
            <div className="mt-3 flex gap-1.5">
              <Skeleton className="h-5 w-10" />
              <Skeleton className="h-5 w-10" />
            </div>
          </Card>
        </li>
      ))}
    </ul>
  )
}
