import { NavLink, Outlet } from 'react-router-dom'

import { NAV_ITEMS } from './navItems'
import { BrandMark } from '@/components/common/BrandMark'
import { ThemeToggle } from '@/components/common/ThemeToggle'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark className="size-8 shrink-0 text-foreground" />
      <div className="min-w-0">
        <p className="font-heading truncate text-sm leading-tight font-semibold">Pokémon Lab</p>
        <p className="truncate text-xs text-muted-foreground">宝可梦研究所</p>
      </div>
    </div>
  )
}

/**
 * 应用外壳：桌面用左侧边栏，移动端用顶部标题栏 + 底部标签栏。
 * 一套代码覆盖两种形态，不做两套页面。
 */
export function AppShell() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      {/* ---------- 桌面侧边栏（lg 及以上）---------- */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
        <div className="px-4 py-4">
          <Brand />
        </div>

        <nav aria-label="主导航" className="flex-1 space-y-0.5 overflow-y-auto px-2 py-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, phase }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors',
                  'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                  isActive
                    ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                    : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {/* 激活态左侧品牌指示条，增强当前位置感知 */}
                  <span
                    aria-hidden="true"
                    className={cn(
                      'absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary transition-opacity',
                      isActive ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                  <Icon
                    aria-hidden="true"
                    className={cn(
                      'size-4 shrink-0 transition-colors',
                      isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground',
                    )}
                  />
                  <span className="truncate">{label}</span>
                  {phase !== 'P0' ? (
                    <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                      {phase}
                    </span>
                  ) : null}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center justify-between gap-2 border-t border-sidebar-border px-3 py-3">
          <Badge variant="outline">MVP · P0 骨架</Badge>
          <ThemeToggle />
        </div>
      </aside>

      {/* ---------- 主内容区 ---------- */}
      <div className="lg:pl-60">
        {/* 移动端顶部标题栏 */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/85 px-4 backdrop-blur lg:hidden">
          <Brand />
          <ThemeToggle />
        </header>

        <main className="mx-auto w-full max-w-5xl px-4 pt-6 pb-28 sm:px-6 lg:px-8 lg:pt-8 lg:pb-14">
          <Outlet />
        </main>
      </div>

      {/* ---------- 移动端底部标签栏 ---------- */}
      <nav
        aria-label="底部导航"
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex min-w-0 flex-1 flex-col items-center gap-1 py-2 text-[11px] transition-colors',
                'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                isActive ? 'font-medium text-primary' : 'text-muted-foreground',
              )
            }
          >
            <Icon aria-hidden="true" className="size-5" />
            <span className="max-w-full truncate px-0.5">{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
