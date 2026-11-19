import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ArrowLeft, Database, ListChecks } from 'lucide-react'

import { BrandMark } from '@/components/common/BrandMark'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const ADMIN_NAV = [
  { to: '/admin/sync', label: '数据同步', icon: Database },
  { to: '/admin/pokemon', label: '图鉴编辑', icon: ListChecks },
] as const

/**
 * 后台管理外壳：与公开站点同一套设计系统，但独立导航与「返回站点」入口。
 * 管理区的一切「写」操作都从这里发起；公开区（AppShell）只有浏览。
 */
export function AdminShell() {
  const location = useLocation()
  return (
    <div className="relative min-h-svh bg-background text-foreground">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-48 left-[-10%] size-[36rem] rounded-full bg-primary/10 blur-[120px] dark:bg-primary/15" />
        <div className="absolute right-[-15%] bottom-[-20%] size-[30rem] rounded-full bg-brand-cyan/10 blur-[120px]" />
        <div className="lab-grid absolute inset-0 opacity-30 [mask-image:radial-gradient(ellipse_at_center,black,transparent_78%)]" />
      </div>
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-2.5">
            <span className="relative flex size-9 shrink-0 items-center justify-center rounded-xl bg-[linear-gradient(145deg,var(--primary),var(--brand-violet))] p-px shadow-lg shadow-primary/25">
              <span className="flex size-full items-center justify-center rounded-[0.7rem] bg-background">
                <BrandMark className="size-6 text-foreground" />
              </span>
            </span>
            <div>
              <p className="font-heading text-sm leading-tight font-semibold">研究所后台</p>
              <p className="text-xs text-muted-foreground">内容编辑与数据同步</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">仅本地使用</Badge>
            <a
              href="/"
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <ArrowLeft aria-hidden="true" className="size-4" />
              返回站点
            </a>
          </div>
        </div>
        <nav aria-label="后台导航" className="mx-auto flex max-w-6xl gap-1 px-4 pb-2 sm:px-6">
          {ADMIN_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-all',
                  'focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none',
                  isActive
                    ? 'gradient-primary font-medium text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground',
                )
              }
            >
              <Icon aria-hidden="true" className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 pt-6 pb-14 sm:px-6">
        <div key={location.pathname} className="page-in">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
