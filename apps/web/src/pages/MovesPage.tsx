/**
 * 招式列表页：搜索 + 属性 / 分类 / 学习器筛选 + 排序 + 分页。
 *
 * 视觉上沿用图鉴的控制卡：一张卡里放全部筛选，选中状态用属性色或品牌色标记。
 * 每一行可点进 `/moves/{slug}`；详情页里的学习者再链回 `/dex/{dex}`，形成双向导航。
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronLeft, ChevronRight, CircleAlert, RefreshCw, Search, X } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { useDebouncedValue } from '@/features/dex/hooks'
import {
  DAMAGE_CLASS_LABEL,
  DAMAGE_CLASS_TONE,
  MOVE_SORT_LABEL,
  moveDisplayName,
  type DamageClass,
  type MoveListParams,
  type MoveSort,
  type MoveSummary,
} from '@/features/moves/api'
import { useMoveList } from '@/features/moves/hooks'
import { TYPES } from '@/features/type-chart/data'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200] as const

function classes(): { value: DamageClass | 'all'; label: string }[] {
  return [
    { value: 'all', label: '全部分类' },
    { value: 'physical', label: '物理' },
    { value: 'special', label: '特殊' },
    { value: 'status', label: '变化' },
  ]
}

export function MovesPage() {
  const [search, setSearch] = useState('')
  const [type, setType] = useState('all')
  const [damageClass, setDamageClass] = useState<DamageClass | 'all'>('all')
  const [machineOnly, setMachineOnly] = useState(false)
  const [sort, setSort] = useState<MoveSort>('name')
  const [pageSize, setPageSize] = useState<number>(50)
  const [page, setPage] = useState(1)

  const debounced = useDebouncedValue(search, 300)
  const params: MoveListParams = useMemo(
    () => ({
      page,
      page_size: pageSize,
      q: debounced.trim() || undefined,
      type: type === 'all' ? undefined : type,
      damage_class: damageClass === 'all' ? undefined : damageClass,
      machine_only: machineOnly,
      sort,
    }),
    [page, pageSize, debounced, type, damageClass, machineOnly, sort],
  )
  const list = useMoveList(params)
  const totalPages = list.data?.meta.total_pages ?? 1
  const hasFilters =
    type !== 'all' || damageClass !== 'all' || machineOnly || search.trim().length > 0

  const reset = () => {
    setSearch('')
    setType('all')
    setDamageClass('all')
    setMachineOnly(false)
    setPage(1)
  }

  const goPage = (target: number) => {
    setPage(Math.min(Math.max(1, target), totalPages))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <PageHeader
        title="招式"
        description="全部 797 个招式的数值与图鉴说明，以及「谁会这招」。点进详情可看到按世代与学习方式分组的宝可梦列表，每个宝可梦都能跳回图鉴。"
        actions={
          <Badge variant="outline" className="tabular-nums">
            {list.data ? `${list.data.meta.total} 个` : '—'}
          </Badge>
        }
      />

      <div className="mb-4 space-y-2.5 rounded-xl border bg-card/60 p-3 shadow-sm">
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
              placeholder="搜索招式名、英文名或说明…"
              className="h-9 pl-8"
              aria-label="搜索招式"
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

          <SelectFilter
            label="伤害分类"
            value={damageClass}
            onChange={(value) => {
              setDamageClass(value as DamageClass | 'all')
              setPage(1)
            }}
            options={classes()}
          />

          <SelectFilter
            label="排序"
            value={sort}
            onChange={(value) => {
              setSort(value as MoveSort)
              setPage(1)
            }}
            options={(Object.keys(MOVE_SORT_LABEL) as MoveSort[]).map((value) => ({
              value,
              label: `按${MOVE_SORT_LABEL[value]}`,
            }))}
          />

          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={machineOnly}
              onChange={(event) => {
                setMachineOnly(event.target.checked)
                setPage(1)
              }}
              className="size-3.5 accent-(--primary)"
            />
            仅学习器
          </label>

          {hasFilters ? (
            <Button size="sm" variant="ghost" onClick={reset}>
              <X aria-hidden="true" />
              清除
            </Button>
          ) : null}
        </div>

        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1" role="group" aria-label="按属性筛选">
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

      {list.isPending ? (
        <MoveListSkeleton />
      ) : list.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>招式加载失败</AlertTitle>
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
          没有匹配的招式 —— 试试更换关键词或筛选条件。
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={reset}>
              清除筛选
            </Button>
          </div>
        </Card>
      ) : (
        <>
          <MoveRows items={list.data.items} />

          <nav
            aria-label="招式分页"
            className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4"
          >
            <p className="text-xs text-muted-foreground">
              共 <span className="font-medium text-foreground tabular-nums">{list.data.meta.total}</span>{' '}
              个招式 · 第 {list.data.meta.page}/{totalPages} 页
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
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => goPage(page - 1)}
              >
                <ChevronLeft aria-hidden="true" />
                上一页
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => goPage(page + 1)}
              >
                下一页
                <ChevronRight aria-hidden="true" />
              </Button>
            </div>
          </nav>
        </>
      )}
    </>
  )
}

function MoveRows({ items }: { items: MoveSummary[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border bg-card">
      <table className="w-full min-w-[46rem] border-collapse text-sm">
        <caption className="sr-only">招式列表：名称、属性、分类、威力、命中、PP 与学习者数量</caption>
        <thead>
          <tr className="border-b bg-muted/40 text-left text-[11px] text-muted-foreground">
            <th scope="col" className="py-2 pl-3 font-medium">招式</th>
            <th scope="col" className="w-20 py-2 pr-2 font-medium">属性</th>
            <th scope="col" className="w-16 py-2 pr-2 font-medium">分类</th>
            <th scope="col" className="w-14 py-2 pr-2 text-right font-medium">威力</th>
            <th scope="col" className="w-14 py-2 pr-2 text-right font-medium">命中</th>
            <th scope="col" className="w-12 py-2 pr-2 text-right font-medium">PP</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">学习者</th>
          </tr>
        </thead>
        <tbody>
          {items.map((move) => (
            <tr key={move.name} className="group border-b last:border-b-0 hover:bg-muted/40">
              <td className="max-w-80 py-1.5 pl-3">
                <Link to={`/moves/${move.name}`} className="block min-w-0">
                  <span className="flex items-center gap-1.5 font-medium group-hover:text-primary">
                    <span className="truncate">{moveDisplayName(move)}</span>
                    <span className="truncate text-[11px] font-normal text-muted-foreground">
                      {move.name_en}
                    </span>
                    {move.is_machine ? (
                      <span className="shrink-0 rounded bg-muted px-1 text-[9px] text-muted-foreground">
                        TM
                      </span>
                    ) : null}
                  </span>
                  {move.description_zh ? (
                    <span className="mt-0.5 line-clamp-1 block text-[10px] text-muted-foreground">
                      {move.description_zh}
                    </span>
                  ) : null}
                </Link>
              </td>
              <td className="py-1.5 pr-2">
                {move.type ? (
                  <TypeBadge type={move.type} className="px-1.5 py-0 text-[10px]" />
                ) : (
                  '—'
                )}
              </td>
              <td className="py-1.5 pr-2">
                {move.damage_class ? (
                  <span
                    className={cn(
                      'inline-flex rounded px-1.5 py-0 text-[10px]',
                      DAMAGE_CLASS_TONE[move.damage_class],
                    )}
                  >
                    {DAMAGE_CLASS_LABEL[move.damage_class]}
                  </span>
                ) : (
                  '—'
                )}
              </td>
              <td className="py-1.5 pr-2 text-right text-xs tabular-nums">{move.power ?? '—'}</td>
              <td className="py-1.5 pr-2 text-right text-xs tabular-nums">
                {move.accuracy ?? '—'}
              </td>
              <td className="py-1.5 pr-2 text-right text-xs tabular-nums">{move.pp ?? '—'}</td>
              <td className="py-1.5 pr-3 text-right text-xs text-muted-foreground tabular-nums">
                {move.learner_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SelectFilter({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label}
        className="h-9 appearance-none rounded-lg border border-input bg-background pr-7 pl-3 text-sm text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-2 size-3.5 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  )
}

function MoveListSkeleton() {
  return (
    <div className="space-y-1.5" aria-busy="true">
      {Array.from({ length: 10 }, (_, index) => (
        <Skeleton key={index} className="h-10 w-full rounded-lg" />
      ))}
    </div>
  )
}
