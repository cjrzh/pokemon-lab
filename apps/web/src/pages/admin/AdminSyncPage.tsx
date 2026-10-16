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
import { useOpLogs, useSyncStatus, useTriggerSync } from '@/features/admin/hooks'
import { describeApiError } from '@/lib/apiClient'

export function AdminSyncPage() {
  const status = useSyncStatus()
  const logs = useOpLogs()
  const trigger = useTriggerSync()

  const [start, setStart] = useState('1')
  const [end, setEnd] = useState('151')
  const [force, setForce] = useState(false)

  const canSubmit =
    !trigger.isPending &&
    Number(start) >= 1 &&
    Number(end) >= Number(start) &&
    Number(end) - Number(start) < 300

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
              </dl>
              <p className="mt-4 text-xs text-muted-foreground">
                默认范围 #{status.data.default_range.start}–#{status.data.default_range.end}（关都图鉴）
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
              每只宝可梦需要 3 个上游请求，151 只约需数分钟（取决于网络）。同步进行中请勿关闭页面。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault()
                if (!canSubmit) return
                trigger.mutate({ start: Number(start), end: Number(end), force })
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
