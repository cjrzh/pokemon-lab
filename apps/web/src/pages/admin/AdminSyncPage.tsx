import { useState } from 'react'
import { CircleAlert, Database, Play, RefreshCw } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useDoublesStatus,
  useImportDoubles,
  useOpLogs,
  useSyncStatus,
  useTriggerSync,
} from '@/features/admin/hooks'
import { describeApiError } from '@/lib/apiClient'

/** 世代看板：label 用地区名，expected 为该世代全国图鉴数量。 */
const GEN_DASHBOARD = [
  { gen: 1, label: '关都', expected: 151 },
  { gen: 2, label: '城都', expected: 100 },
  { gen: 3, label: '丰缘', expected: 135 },
  { gen: 4, label: '神奥', expected: 107 },
  { gen: 5, label: '合众', expected: 156 },
  { gen: 6, label: '卡洛斯', expected: 72 },
  { gen: 7, label: '阿罗拉', expected: 88 },
  { gen: 8, label: '伽勒尔', expected: 96 },
  { gen: 9, label: '帕底亚', expected: 120 },
] as const

export function AdminSyncPage() {
  const status = useSyncStatus()
  const logs = useOpLogs()
  const trigger = useTriggerSync()
  const doubles = useDoublesStatus()
  const importDoubles = useImportDoubles()

  const [start, setStart] = useState('1')
  const [end, setEnd] = useState('1025')
  const [force, setForce] = useState(false)
  const [skipExisting, setSkipExisting] = useState(true)

  const canSubmit =
    !trigger.isPending &&
    Number(start) >= 1 &&
    Number(end) >= Number(start) &&
    Number(end) - Number(start) < 1025

  return (
    <>
      <PageHeader
        title="数据同步"
        description="从 PokéAPI 拉取图鉴数据到本地 SQLite。同步后站点离线可用；手动编辑过的条目默认不会被覆盖。"
      />

      <div className="space-y-4">
        {/* ---------- 当前状态 ---------- */}
        {status.isPending ? (
          <Card>
            <CardContent className="space-y-2 pt-6">
              <Skeleton className="h-4 w-64" />
              <Skeleton className="h-4 w-48" />
            </CardContent>
          </Card>
        ) : status.isError ? (
          <Alert variant="destructive">
            <CircleAlert aria-hidden="true" />
            <AlertTitle>无法读取同步状态</AlertTitle>
            <AlertDescription>{describeApiError(status.error)}</AlertDescription>
          </Alert>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database aria-hidden="true" className="size-4 text-muted-foreground" />
                本地图鉴现状
              </CardTitle>
              <CardDescription>
                {status.data.last_synced_at
                  ? `最近同步：${new Date(status.data.last_synced_at).toLocaleString()}`
                  : '尚未同步过任何数据'}
              </CardDescription>
              <CardDescription>
                同步会一并拉取特性说明、全招式表与官方立绘；立绘写到
                services/api/var/media/artwork，站点离线可用。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted-foreground">已同步条目</dt>
                  <dd className="mt-0.5 text-2xl font-semibold tabular-nums">
                    {status.data.total}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">PokéAPI 来源</dt>
                  <dd className="mt-0.5 text-2xl font-semibold tabular-nums">
                    {status.data.from_pokeapi}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">手动维护</dt>
                  <dd className="mt-0.5 text-2xl font-semibold tabular-nums">
                    {status.data.from_manual}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">演示数据</dt>
                  <dd className="mt-0.5 text-2xl font-semibold tabular-nums">
                    {status.data.demo}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">已缓存立绘</dt>
                  <dd className="mt-0.5 text-2xl font-semibold tabular-nums">
                    {status.data.artwork_cached ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">含全招式数据</dt>
                  <dd className="mt-0.5 text-2xl font-semibold tabular-nums">
                    {status.data.moves_covered ?? '—'}
                  </dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-xs text-muted-foreground">最近同步</dt>
                  <dd className="mt-1 text-sm">
                    {status.data.last_synced_at
                      ? new Date(status.data.last_synced_at).toLocaleString()
                      : '尚未同步'}
                  </dd>
                </div>
              </dl>
              {Object.keys(status.data.per_generation ?? {}).length > 0 ? (
                <div className="mt-4">
                  <p className="text-xs text-muted-foreground">分世代覆盖</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {GEN_DASHBOARD.map(({ gen, label, expected }) => {
                      const got = status.data.per_generation?.[String(gen)] ?? 0
                      const done = got >= expected
                      return (
                        <span
                          key={gen}
                          title={`第 ${gen} 世代 ${label}：${got}/${expected}`}
                          className={
                            'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] tabular-nums ' +
                            (done
                              ? 'border-transparent bg-primary/10 font-medium text-primary'
                              : 'border-border text-muted-foreground')
                          }
                        >
                          {label} {got}/{expected}
                        </span>
                      )
                    })}
                  </div>
                </div>
              ) : null}
              <p className="mt-4 text-xs text-muted-foreground">
                默认范围 #{status.data.default_range.start}–#{status.data.default_range.end}（全国图鉴）
                · 覆盖率{' '}
                {status.data.coverage != null ? `${(status.data.coverage * 100).toFixed(1)}%` : '—'}
              </p>
            </CardContent>
          </Card>
        )}

        {/* ---------- 触发同步 ---------- */}
        <Card>
          <CardHeader>
            <CardTitle>手动触发同步</CardTitle>
            <CardDescription>
              每只宝可梦需要 2 个基础请求，外加特性 / 招式详情与立绘下载（同类数据整批共享缓存）。
              全国图鉴 1025 只首次同步较慢，建议按世代分批（命令行 <code>--gen 2</code> 等）；
              已有记录可用「跳过已同步」续传。同步进行中请勿关闭页面。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault()
                if (!canSubmit) return
                trigger.mutate({
                  start: Number(start),
                  end: Number(end),
                  force,
                  skip_existing: skipExisting,
                })
              }}
            >
              <div className="w-24">
                <Label htmlFor="sync-start">起始编号</Label>
                <Input
                  id="sync-start"
                  type="number"
                  min={1}
                  value={start}
                  onChange={(event) => setStart(event.target.value)}
                  className="mt-1.5"
                />
              </div>
              <div className="w-24">
                <Label htmlFor="sync-end">结束编号</Label>
                <Input
                  id="sync-end"
                  type="number"
                  min={1}
                  value={end}
                  onChange={(event) => setEnd(event.target.value)}
                  className="mt-1.5"
                />
              </div>
              <label className="flex items-center gap-2 pb-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={skipExisting}
                  onChange={(event) => setSkipExisting(event.target.checked)}
                  className="size-4 accent-(--primary)"
                />
                跳过已同步（续传）
              </label>
              <label className="flex items-center gap-2 pb-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={force}
                  onChange={(event) => setForce(event.target.checked)}
                  className="size-4 accent-(--primary)"
                />
                覆盖手动编辑过的记录
              </label>
              <Button type="submit" disabled={!canSubmit} className="ml-auto">
                {trigger.isPending ? (
                  <RefreshCw aria-hidden="true" className="animate-spin" />
                ) : (
                  <Play aria-hidden="true" />
                )}
                {trigger.isPending ? '同步中…' : '开始同步'}
              </Button>
            </form>

            {trigger.isError ? (
              <Alert variant="destructive" className="mt-3">
                <CircleAlert aria-hidden="true" />
                <AlertTitle>同步失败</AlertTitle>
                <AlertDescription>{describeApiError(trigger.error)}</AlertDescription>
              </Alert>
            ) : null}

            {trigger.isSuccess ? (
              <Alert className="mt-3">
                <Badge variant="secondary">结果</Badge>
                <AlertTitle>{trigger.data.summary}</AlertTitle>
                <AlertDescription>
                  {Object.keys(trigger.data.failed).length > 0
                    ? `失败明细：${Object.entries(trigger.data.failed)
                        .map(([dex, reason]) => `#${dex} ${reason}`)
                        .join('；')}`
                    : '全部成功，无失败条目。'}
                  {trigger.data.skipped_manual.length > 0
                    ? `手动记录已跳过：${trigger.data.skipped_manual.map((d) => `#${d}`).join(', ')}`
                    : ''}
                </AlertDescription>
              </Alert>
            ) : null}
          </CardContent>
        </Card>

        {/* ---------- 双打辅助数据 ---------- */}
        <Card>
          <CardHeader>
            <CardTitle>双打辅助数据</CardTitle>
            <CardDescription>
              四个格式（冠军 / 朱紫 / 剑盾 / BDSP）的 Smogon 月度统计。
              数据文件在仓库 <code>data/doubles/</code>，由
              <code>scripts/fetch_doubles_stats.py</code> 联网抓取；这里只做导入，不访问网络。
              图鉴详情页的「双打对战辅助」读取的就是本表。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {doubles.isPending ? (
              <Skeleton className="h-16 w-full" />
            ) : doubles.isError ? (
              <p className="text-sm text-muted-foreground">
                无法读取双打数据现状：{describeApiError(doubles.error)}
              </p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  已导入 {doubles.data.format_count} 个格式 / {doubles.data.entries} 条记录
                </p>
                {doubles.data.formats.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="text-muted-foreground">
                        <tr>
                          <th className="py-1 pr-3 font-medium">格式</th>
                          <th className="py-1 pr-3 font-medium">统计月份</th>
                          <th className="py-1 pr-3 font-medium">等级线</th>
                          <th className="py-1 pr-3 font-medium">对战数</th>
                          <th className="py-1 pr-3 font-medium">记录</th>
                          <th className="py-1 font-medium">覆盖图鉴</th>
                        </tr>
                      </thead>
                      <tbody>
                        {doubles.data.formats.map((format) => (
                          <tr key={format.key} className="border-t">
                            <td className="py-1 pr-3">{format.label}</td>
                            <td className="py-1 pr-3 tabular-nums">{format.month}</td>
                            <td className="py-1 pr-3 tabular-nums">{format.cutoff}</td>
                            <td className="py-1 pr-3 tabular-nums">
                              {format.battles.toLocaleString()}
                            </td>
                            <td className="py-1 pr-3 tabular-nums">{format.entries}</td>
                            <td className="py-1 tabular-nums">{format.dex_covered}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={importDoubles.isPending}
                onClick={() => importDoubles.mutate()}
              >
                {importDoubles.isPending ? (
                  <RefreshCw aria-hidden="true" className="animate-spin" />
                ) : (
                  <Database aria-hidden="true" />
                )}
                {importDoubles.isPending ? '导入中…' : '重新导入 data/doubles'}
              </Button>
              {importDoubles.isError ? (
                <span className="text-xs text-destructive">
                  {describeApiError(importDoubles.error)}
                </span>
              ) : importDoubles.isSuccess ? (
                <span className="text-xs text-muted-foreground">
                  {importDoubles.data.summary}
                  {importDoubles.data.unresolved.length > 0
                    ? `（未映射：${importDoubles.data.unresolved.slice(0, 5).join('、')}…）`
                    : ''}
                </span>
              ) : null}
            </div>
          </CardContent>
        </Card>

        {/* ---------- 操作日志 ---------- */}
        <Card>
          <CardHeader>
            <CardTitle>操作日志</CardTitle>
            <CardDescription>后台的一切写操作都有记录，便于回溯。</CardDescription>
          </CardHeader>
          <CardContent>
            {logs.isPending ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-64" />
                <Skeleton className="h-4 w-48" />
              </div>
            ) : logs.isError ? (
              <p className="text-sm text-muted-foreground">日志加载失败：{describeApiError(logs.error)}</p>
            ) : logs.data.items.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无操作记录。</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {logs.data.items.map((log) => (
                  <li key={log.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                    <span className="font-medium">{log.action}</span>
                    {log.target ? <span className="text-muted-foreground">{log.target}</span> : null}
                    {log.detail ? (
                      <span className="text-xs text-muted-foreground">{log.detail}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
