import { ArrowRight, Database, RefreshCw, Server, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { NAV_ITEMS } from '@/app/layout/navItems'
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
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
        STATUS_TONE[status],
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'size-1.5 rounded-full bg-current',
          status === 'ok' && 'animate-pulse',
        )}
      />
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

/** 首页能力卡片各自的属性色点缀，让 18 属性色系成为界面的第二层色彩语言。 */
const CAPABILITY_ACCENT: Record<string, string> = {
  '/dex': 'text-type-water bg-type-water/10',
  '/type-calc': 'text-type-fire bg-type-fire/10',
  '/collection': 'text-type-electric bg-type-electric/15',
  '/notes': 'text-type-grass bg-type-grass/10',
  '/exam': 'text-type-psychic bg-type-psychic/10',
}

/** 已交付的功能（phase === 'P0'）显示「立即使用」，未交付的显示「查看阶段计划」。 */
const DELIVERED = new Set(['/dex'])

export function HomePage() {
  const capabilities = NAV_ITEMS.filter((item) => item.to !== '/')

  return (
    <div className="space-y-6">
      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary via-primary to-[#3a4fd6] px-6 py-10 text-primary-foreground sm:px-10 sm:py-14">
        {/* 精灵球轮廓水印：大而克制，贴合品牌但不喧宾夺主 */}
        <svg
          aria-hidden="true"
          viewBox="0 0 64 64"
          className="pointer-events-none absolute -right-10 -bottom-14 h-64 w-64 text-white/10 sm:h-80 sm:w-80"
        >
          <circle cx="32" cy="32" r="27" fill="none" stroke="currentColor" strokeWidth="4" />
          <path d="M5 32a27 27 0 0 1 54 0" fill="none" stroke="currentColor" strokeWidth="4" />
          <circle cx="32" cy="32" r="9" fill="none" stroke="currentColor" strokeWidth="4" />
        </svg>
        <div className="relative max-w-xl">
          <Badge className="mb-3 border-white/25 bg-white/15 text-white backdrop-blur-sm hover:bg-white/15">
            MVP · P0 骨架
          </Badge>
          <h1 className="font-heading text-3xl leading-tight font-bold tracking-tight sm:text-4xl">
            宝可梦研究所
          </h1>
          <p className="mt-3 text-sm/6 text-white/80 sm:text-base/7">
            图鉴检索、属性克制计算、个人收藏与笔记、大师考试
            —— 一个本地优先的个人工具站，后续逐步扩展为 AI 实验平台。
          </p>
        </div>
      </section>

      <HealthPanel />

      {/* ---------- 核心能力 ---------- */}
      <section aria-labelledby="capabilities-heading">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="capabilities-heading" className="font-heading text-lg font-semibold tracking-tight">
            核心能力
          </h2>
          <span className="text-xs text-muted-foreground">按阶段逐步交付</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {capabilities.map(({ to, label, description, icon: Icon, phase }) => (
            <Link
              key={to}
              to={to}
              className="group rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              <Card className="h-full transition-all group-hover:-translate-y-0.5 group-hover:shadow-md group-hover:ring-primary/30">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2.5">
                      <span
                        aria-hidden="true"
                        className={cn(
                          'flex size-8 shrink-0 items-center justify-center rounded-lg',
                          CAPABILITY_ACCENT[to],
                        )}
                      >
                        <Icon className="size-4" />
                      </span>
                      <CardTitle>{label}</CardTitle>
                    </span>
                    <Badge variant="secondary">{phase}</Badge>
                  </div>
                  <CardDescription>{description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
                    {DELIVERED.has(to) ? '立即使用' : '查看阶段计划'}
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

      {/* ---------- 数据来源与边界 ---------- */}
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
      {/* ---------- 后台管理入口（站长用；公开站点本身只读） ---------- */}
      <p className="text-center text-xs text-muted-foreground">
        <Link to="/admin" className="underline-offset-4 hover:underline">
          研究所后台
        </Link>
        · 数据同步与内容编辑 · 仅本地使用
      </p>
    </div>
  )
}
