import { ArrowRight, Database, RefreshCw, Server, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { NAV_ITEMS } from '@/app/layout/navItems'
import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { HealthStatus } from '@/features/health/api'
import { useHealth } from '@/features/health/hooks'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const STATUS_LABEL: Record<HealthStatus, string> = {
  ok: '正常',
  degraded: '降级',
  error: '异常',
}

const STATUS_TONE: Record<HealthStatus, string> = {
  ok: 'bg-success/10 text-success',
  degraded: 'bg-warning/15 text-warning',
  error: 'bg-destructive/10 text-destructive',
}

function StatusPill({ status }: { status: HealthStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        STATUS_TONE[status],
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}

function HealthPanel() {
  const health = useHealth()

  if (health.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server aria-hidden="true" className="size-4" />
            后端服务状态
          </CardTitle>
          <CardDescription>正在向后端发起 /health 检查…</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-64" />
          <Skeleton className="h-4 w-40" />
        </CardContent>
      </Card>
    )
  }

  if (health.isError) {
    return (
      <Alert variant="destructive">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>无法连接到后端服务</AlertTitle>
        <AlertDescription>{describeApiError(health.error)}</AlertDescription>
        <AlertAction>
          <Button size="xs" variant="outline" onClick={() => void health.refetch()}>
            <RefreshCw aria-hidden="true" />
            重试
          </Button>
        </AlertAction>
      </Alert>
    )
  }

  const data = health.data
  const overallStatus: HealthStatus = data.status === 'ok' ? 'ok' : 'degraded'

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Server aria-hidden="true" className="size-4 text-muted-foreground" />
          <CardTitle>后端服务状态</CardTitle>
          <StatusPill status={overallStatus} />
        </div>
        <CardDescription>
          {data.service} · v{data.version} · 检查时间 {new Date(data.generated_at).toLocaleString()}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <ul className="space-y-2">
          {data.checks.map((check) => (
            <li
              key={check.name}
              className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm"
            >
              <span className="flex items-center gap-2">
                <Database aria-hidden="true" className="size-3.5 text-muted-foreground" />
                {check.name}
              </span>
              <span className="flex items-center gap-3">
                <span className="text-muted-foreground">{check.detail}</span>
                <StatusPill status={check.status} />
              </span>
            </li>
          ))}
        </ul>
        <div className="pt-1">
          <Button size="xs" variant="ghost" onClick={() => void health.refetch()}>
            <RefreshCw aria-hidden="true" />
            重新检查
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function HomePage() {
  const capabilities = NAV_ITEMS.filter((item) => item.to !== '/')

  return (
    <>
      <PageHeader
        title="宝可梦研究所"
        description="图鉴检索、属性克制计算、个人收藏与笔记、大师考试 —— 一个本地优先的个人工具站。"
        actions={<Badge variant="outline">MVP · P0 骨架</Badge>}
      />

      <div className="space-y-6">
        <HealthPanel />

        <section aria-labelledby="capabilities-heading">
          <h2 id="capabilities-heading" className="sr-only">
            核心能力
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {capabilities.map(({ to, label, description, icon: Icon, phase }) => (
              <Link
                key={to}
                to={to}
                className="group rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <Card className="h-full transition-colors group-hover:bg-muted/40">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2">
                        <Icon aria-hidden="true" className="size-4 text-muted-foreground" />
                        <CardTitle>{label}</CardTitle>
                      </span>
                      <Badge variant="secondary">{phase}</Badge>
                    </div>
                    <CardDescription>{description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      查看阶段计划
                      <ArrowRight
                        aria-hidden="true"
                        className="size-3.5 transition-transform group-hover:translate-x-0.5"
                      />
                    </span>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>数据来源与边界</CardTitle>
            <CardDescription>
              所有数据都必须能说明来处；演示数据会被明确标记，不冒充真实数据。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5 text-sm text-muted-foreground">
              <li>
                · 图鉴基础数据：来自 <strong className="text-foreground">PokéAPI</strong>{' '}
                公开接口，同步到本地 SQLite 后离线可用（同步脚本手动触发，不自动跑）。
              </li>
              <li>
                · 属性克制关系：依据官方第 6 代及以后（Gen 6+）相克关系整理成仓库内规范数据，
                由前端与后端共享同一份来源。
              </li>
              <li>
                · 世代覆盖：数据结构支持 Gen 1–9，MVP 先交付 Gen 6+；Gen 1–5 的历史差异会逐步补齐，
                在补齐之前界面不会宣称支持。
              </li>
              <li>
                · 演示数据：任何用于占位或测试的数据都会带「演示数据」标记，仅用于离线首启与自动化测试。
              </li>
              <li>
                · 版权说明：宝可梦相关名称、形象与商标归 任天堂 / GAME FREAK / Creatures Inc. 所有；
                本项目为个人非商业学习用途，不使用官方美术素材。
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  )
}