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
  ok: 'bg-success/10 text-success ring-success/20',
  degraded: 'bg-warning/15 text-warning ring-warning/25',
  error: 'bg-destructive/10 text-destructive ring-destructive/25',
}

function StatusPill({ status }: { status: HealthStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset',
        STATUS_TONE[status],
      )}
    >
      <span
        aria-hidden="true"
        className={cn('size-1.5 rounded-full bg-current', status === 'ok' && 'animate-pulse')}
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
    <Card className="overflow-hidden">
      {/* 顶部状态光带：正常为青绿，降级为琥珀 */}
      <div
        aria-hidden="true"
        className={cn(
          'h-px w-full bg-[linear-gradient(90deg,transparent,currentColor,transparent)] opacity-60',
          overallStatus === 'ok' ? 'text-success' : 'text-warning',
        )}
      />
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-inset ring-primary/15">
            <Server aria-hidden="true" className="size-4" />
          </span>
          <CardTitle>后端服务状态</CardTitle>
          <StatusPill status={overallStatus} />
          <span className="ml-auto hidden text-[11px] text-muted-foreground tabular-nums sm:block">
            {new Date(data.generated_at).toLocaleString()}
          </span>
        </div>
        <CardDescription className="pl-[2.875rem]">
          {data.service} · v{data.version}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border/60">
          {data.checks.map((check) => (
            <li
              key={check.name}
              className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5 text-sm first:pt-0 last:pb-0"
            >
              <span className="flex items-center gap-2 font-medium">
                <span className="flex size-6 items-center justify-center rounded-md bg-muted/70 text-muted-foreground">
                  <Database aria-hidden="true" className="size-3.5" />
                </span>
                {check.name}
              </span>
              <span className="flex items-center gap-3">
                <span className="text-[12px] text-muted-foreground">{check.detail}</span>
                <StatusPill status={check.status} />
              </span>
            </li>
          ))}
        </ul>
        <div className="pt-3">
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
  '/dex': 'text-type-water bg-type-water/10 ring-type-water/20',
  '/abilities': 'text-type-psychic bg-type-psychic/10 ring-type-psychic/20',
  '/moves': 'text-type-fighting bg-type-fighting/10 ring-type-fighting/20',
  '/items': 'text-type-ground bg-type-ground/15 ring-type-ground/25',
  '/usage': 'text-type-steel bg-type-steel/15 ring-type-steel/25',
  '/teams': 'text-type-dragon bg-type-dragon/10 ring-type-dragon/20',
  '/quiz': 'text-brand-violet bg-brand-violet/10 ring-brand-violet/20',
  '/usage/history': 'text-brand-cyan bg-brand-cyan/10 ring-brand-cyan/20',
  '/tournaments': 'text-brand-amber bg-brand-amber/10 ring-brand-amber/20',
  '/type-calc': 'text-type-fire bg-type-fire/10 ring-type-fire/20',
  '/admin': 'text-muted-foreground bg-muted ring-border',
}

function SectionHeading({
  id,
  title,
  aside,
}: {
  id: string
  title: string
  aside?: React.ReactNode
}) {
  return (
    <div className="mb-3.5 flex items-end justify-between gap-3">
      <div className="flex items-center gap-2.5">
        <span aria-hidden="true" className="glow-line h-4 w-1 rounded-full" />
        <h2 id={id} className="font-heading text-[1.05rem] font-semibold tracking-tight">
          {title}
        </h2>
      </div>
      {aside}
    </div>
  )
}

export function HomePage() {
  const capabilities = NAV_ITEMS.filter((item) => item.to !== '/')

  return (
    <div className="space-y-7">
      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#070b16] px-6 py-10 text-white shadow-[0_36px_90px_-60px_rgb(20_30_90/0.95)] sm:px-10 sm:py-14">
        {/* 渐变网格 + 双色光晕 */}
        <div aria-hidden="true" className="absolute inset-0">
          <div className="absolute -top-32 left-[8%] size-80 rounded-full bg-primary/45 blur-[100px]" />
          <div className="absolute -right-24 -bottom-40 size-[26rem] rounded-full bg-brand-cyan/25 blur-[110px]" />
          <div className="absolute inset-0 bg-[linear-gradient(115deg,rgb(255_255_255/0.07),transparent_46%)]" />
          <div className="lab-grid absolute inset-0 opacity-[0.16]" />
        </div>

        {/* 右侧轨道装饰 */}
        <div aria-hidden="true" className="pointer-events-none absolute -right-28 -bottom-36 hidden lg:block">
          <div className="relative size-[30rem]">
            <div className="absolute inset-0 rounded-full border border-white/10" />
            <div className="absolute inset-12 rounded-full border border-white/10" />
            <div className="absolute inset-24 rounded-full border border-dashed border-white/15" />
            <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,rgb(99_102_241/0.3),transparent_62%)] blur-2xl" />
            <div className="absolute inset-32 rounded-full border border-white/15 bg-white/[0.04] backdrop-blur-sm" />
            <div className="absolute top-1/2 left-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand-cyan shadow-[0_0_30px_10px_rgb(34_211_238/0.35)]" />
          </div>
        </div>

        <div className="relative max-w-2xl">
          <Badge className="mb-4 border border-white/20 bg-white/10 px-2.5 py-0.5 text-[11px] text-white/90 backdrop-blur-sm hover:bg-white/10">
            Gen 1–9 · 持续更新
          </Badge>
          <h1 className="font-heading text-[2rem] leading-[1.08] font-semibold tracking-tight sm:text-[2.85rem]">
            <span className="bg-[linear-gradient(110deg,#ffffff_8%,#dbe3ff_52%,#7de7f5)] bg-clip-text text-transparent">
              宝可梦研究所
            </span>
          </h1>
          <p className="mt-4 max-w-xl text-[13px] leading-6 text-white/65 sm:text-sm/6">
            全国图鉴、特性、招式、道具与双打使用率——一个本地优先、离线可用的宝可梦资料站。
          </p>
        </div>
      </section>

      <HealthPanel />

      {/* ---------- 核心能力 ---------- */}
      <section aria-labelledby="capabilities-heading">
        <SectionHeading
          id="capabilities-heading"
          title="核心能力"
          aside={
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {capabilities.length} 项全部可用
            </span>
          }
        />
        <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-3">
          {capabilities.map(({ to, label, description, icon: Icon, delivered }) => (
            <Link
              key={to}
              to={to}
              className="group rounded-2xl focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
            >
              <Card className="relative h-full overflow-hidden group-hover:-translate-y-1 group-hover:border-primary/25 group-hover:shadow-[0_24px_50px_-30px_rgb(30_40_120/0.55)]">
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -top-10 -right-10 size-28 rounded-full bg-primary/10 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
                />
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <span
                      aria-hidden="true"
                      className={cn(
                        'flex size-10 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset',
                        CAPABILITY_ACCENT[to] ??
                          'bg-muted text-muted-foreground ring-border',
                      )}
                    >
                      <Icon className="size-[18px]" />
                    </span>
                    {delivered ? (
                      <ArrowRight
                        aria-hidden="true"
                        className="mt-1 size-4 -translate-x-1 text-muted-foreground/50 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:text-primary group-hover:opacity-100"
                      />
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground">
                        规划中
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="mt-1">{label}</CardTitle>
                  <CardDescription className="text-[12px] leading-5">
                    {description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="mt-auto">
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-primary">
                    {delivered ? '立即使用' : '查看规划'}
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
      <Card className="bg-card/80">
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="flex size-8 items-center justify-center rounded-lg bg-muted/80 text-muted-foreground ring-1 ring-inset ring-border/70"
            >
              <Database className="size-4" />
            </span>
            <div>
              <CardTitle>数据来源与边界</CardTitle>
              <CardDescription className="mt-0.5">
                所有数据都必须能说明来处；演示数据会被明确标记，不冒充真实数据。
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-[12px] leading-6 text-muted-foreground sm:text-[13px]">
            <li>
              · 图鉴基础数据：来自 <strong className="text-foreground">PokéAPI</strong>{' '}
              公开接口，同步到本地 SQLite 后离线可用（同步脚本手动触发，不自动跑）。
            </li>
            <li>
              · 属性克制关系：依据官方第 6 代及以后（Gen 6+）相克关系整理成仓库内规范数据，
              由前端与后端共享同一份来源。
            </li>
            <li>
              · 双打统计：来自 Smogon 公开的月度使用率快照，页面始终标注统计月份与等级线，
              不把历史数据冒充当前环境。
            </li>
            <li>
              · 世代覆盖：数据结构支持 Gen 1–9，第 1–5 代的历史克制差异会逐步补齐，
              补齐之前界面不会宣称支持。
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
      <p className="text-center text-[11px] text-muted-foreground">
        <Link
          to="/admin"
          className="rounded-full border border-border/70 bg-background/60 px-3 py-1 underline-offset-4 transition-colors hover:border-primary/30 hover:text-foreground hover:underline"
        >
          研究所后台
        </Link>
        <span className="ml-2">· 数据同步与内容编辑 · 仅本地使用</span>
      </p>
    </div>
  )
}
