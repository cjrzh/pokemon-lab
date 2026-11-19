/**
 * 队伍 Showdown 代码页（独立页面）。
 *
 * 用途：把整支队伍导出成可直接粘贴到 Pokémon Showdown / 交换机器人聊天框的文本。
 * 首行是交易前缀（BDSP → `!tradeBDSP`、剑盾 → `!tradeSWSH`、朱紫 → `!tradeSV`；
 * 冠军格式没有前缀）。每只按《宝可梦》官方交换机器人的字段排列。
 *
 * 代码由后端 `/teams/{id}/showdown` 生成（与详情页 ShowdownExport 的规则一致），
 * 页面只负责展示、复制与下载。
 */

import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Check, CircleAlert, Copy, Download, RefreshCw, Terminal } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useTeamShowdown } from '@/features/teams/hooks'
import { describeApiError } from '@/lib/apiClient'

export function TeamShowdownPage() {
  const { teamId } = useParams<{ teamId: string }>()
  const parsed = Number(teamId)
  const query = useTeamShowdown(Number.isInteger(parsed) && parsed > 0 ? parsed : null)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    if (!query.data) return
    try {
      await navigator.clipboard.writeText(query.data.text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // 剪贴板被拒绝时用户仍可手动选中复制
    }
  }

  const download = () => {
    if (!query.data) return
    const blob = new Blob([query.data.text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${query.data.name || 'team'}-${query.data.format_key}.txt`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <Button asChild size="sm" variant="ghost" className="-ml-2 mb-3">
        <Link to={`/teams?team=${teamId}`}>
          <ArrowLeft aria-hidden="true" />
          返回建队
        </Link>
      </Button>

      <PageHeader
        title={query.data ? `Showdown 代码 · ${query.data.name}` : 'Showdown 代码'}
        description="可直接粘贴到 Pokémon Showdown 的队伍导入框，或发给交换机器人。首行是交易命令（冠军格式没有）。"
        actions={
          query.data ? (
            <Badge variant="outline" className="font-mono text-[10px]">
              {query.data.trade_prefix ?? '无前缀'}
            </Badge>
          ) : null
        }
      />

      {query.isPending ? (
        <Card>
          <CardContent className="space-y-2 pt-6">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-64 w-full" />
          </CardContent>
        </Card>
      ) : query.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>无法生成 Showdown 代码</AlertTitle>
          <AlertDescription>{describeApiError(query.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void query.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Terminal aria-hidden="true" className="size-4 text-muted-foreground" />
                  {query.data.format_label ?? query.data.format_key}
                </CardTitle>
                <CardDescription>
                  {query.data.points_kind === 'stat_points'
                    ? '冠军格式使用能力点（0–32），没有个体值。'
                    : 'IV 全 31 时按 Showdown 惯例省略 IV 行。'}
                </CardDescription>
              </div>
              <div className="flex items-center gap-1.5">
                <Button size="sm" variant="outline" onClick={download}>
                  <Download aria-hidden="true" />
                  下载
                </Button>
                <Button size="sm" onClick={() => void copy()}>
                  {copied ? (
                    <Check aria-hidden="true" className="text-success" />
                  ) : (
                    <Copy aria-hidden="true" />
                  )}
                  {copied ? '已复制' : '复制全部'}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[70vh] overflow-auto rounded-lg bg-muted/60 p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
              {query.data.text || '（队伍还没有成员）'}
            </pre>
          </CardContent>
        </Card>
      )}
    </>
  )
}
