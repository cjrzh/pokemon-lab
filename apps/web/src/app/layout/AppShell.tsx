import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { NAV_ITEMS } from './navItems'
import { BrandMark } from '@/components/common/BrandMark'
import { ThemeToggle } from '@/components/common/ThemeToggle'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** 导航分组之间的视觉分隔（不新增文字，只拉开信息层级）。 */
const GROUP_BREAKS = new Set(['/usage', '/quiz', '/type-calc'])

/** 移动端底栏保留的四个高频入口，其余收进抽屉。 */
const MOBILE_PRIMARY = ['/', '/dex', '/usage', '/teams'] as const

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="relative flex size-9 shrink-0 items-center justify-center rounded-xl bg-[linear-gradient(145deg,var(--primary),var(--brand-violet))] p-px shadow-lg shadow-primary/25">
        <span className="flex size-full items-center justify-center rounded-[0.7rem] bg-sidebar">
          <BrandMark className="size-6 text-foreground" />
        </span>
      </span>
      <div className={cn('min-w-0', compact && 'hidden sm:block')}>
        <p className="font-heading truncate text-[13px] leading-tight font-semibold tracking-tight">
          Pokémon Lab
        </p>
        <p className="truncate text-[11px] text-muted-foreground">宝可梦研究所</p>
      </div>
    </div>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="主导航" className="space-y-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon, delivered }) => (
        <div key={to}>
          {GROUP_BREAKS.has(to) ? (
            <div
              aria-hidden="true"
              className="mx-3 my-2.5 h-px bg-[linear-gradient(90deg,transparent,var(--sidebar-border),transparent)]"
            />
          ) : null}
          <NavLink
            to={to}
            end={to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] transition-all duration-200',
                'focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none',
                isActive
                  ? 'bg-[linear-gradient(100deg,color-mix(in_oklch,var(--primary)_16%,transparent),color-mix(in_oklch,var(--primary)_4%,transparent))] font-medium text-foreground ring-1 ring-primary/20'
                  : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute top-1/2 left-0 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-[linear-gradient(180deg,var(--primary),var(--brand-cyan))] transition-opacity duration-200',
                    isActive ? 'opacity-100' : 'opacity-0',
                  )}
                />
                <span
                  className={cn(
                    'flex size-7 shrink-0 items-center justify-center rounded-lg transition-colors',
                    isActive
                      ? 'bg-primary/15 text-primary'
                      : 'text-muted-foreground group-hover:bg-sidebar-accent/70 group-hover:text-foreground',
                  )}
                >
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <span className="truncate">{label}</span>
                {!delivered ? (
                  <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                    规划中
                  </span>
                ) : null}
              </>
            )}
          </NavLink>
        </div>
      ))}
    </nav>
  )
}

function SidebarFooter() {
  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-sidebar-border/70 bg-sidebar-accent/25 px-2.5 py-2">
      <Badge variant="outline" className="gap-1.5 border-transparent bg-transparent px-0 text-[10px]">
        <span className="relative flex size-1.5">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-success/60" />
          <span className="relative inline-flex size-1.5 rounded-full bg-success" />
        </span>
        本地 · 个人使用
      </Badge>
      <ThemeToggle />
    </div>
  )
}

/**
 * 应用外壳：桌面用左侧边栏，移动端用顶部标题栏 + 底部标签栏 + 完整导航抽屉。
 * 底部只保留四个高频入口，其余从抽屉进入 —— 11 个标签挤在一行会难以点按。
 */
export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  // Esc 关闭 + 打开时锁定页面滚动
  useEffect(() => {
    if (!menuOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  return (
    <div className="relative min-h-svh bg-background text-foreground">
      {/* ---------- 全局背景：冷色光晕 + 科研网格 ---------- */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-56 left-[-12%] size-[44rem] rounded-full bg-primary/10 blur-[130px] dark:bg-primary/20" />
        <div className="absolute top-[18%] right-[-18%] size-[38rem] rounded-full bg-brand-cyan/10 blur-[130px] dark:bg-brand-cyan/10" />
        <div className="absolute bottom-[-22%] left-[28%] size-[34rem] rounded-full bg-brand-violet/10 blur-[130px] dark:bg-brand-violet/10" />
        <div className="lab-grid absolute inset-0 opacity-40 [mask-image:radial-gradient(ellipse_at_center,black,transparent_78%)] dark:opacity-25" />
      </div>

      {/* ---------- 桌面侧边栏（lg 及以上）---------- */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[17.5rem] flex-col border-r border-sidebar-border/60 bg-sidebar/80 backdrop-blur-2xl lg:flex">
        <div className="px-4 pt-5 pb-4">
          <Brand />
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-1">
          <NavItems />
        </div>

        <div className="border-t border-sidebar-border/60 p-3">
          <SidebarFooter />
        </div>
      </aside>

      {/* ---------- 主内容区 ---------- */}
      <div className="lg:pl-[17.5rem]">
        {/* 移动端顶部标题栏 */}
        <header className="sticky top-0 z-20 flex h-16 items-center gap-2 border-b border-border/60 bg-background/70 px-3 backdrop-blur-xl lg:hidden">
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label="打开导航菜单"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            <Menu aria-hidden="true" />
          </Button>
          <Brand compact />
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 pt-6 pb-32 sm:px-6 lg:px-10 lg:pt-10 lg:pb-16">
          <div key={location.pathname} className="page-in">
            <Outlet />
          </div>
        </main>
      </div>

      {/* ---------- 移动端底部标签栏 ---------- */}
      <nav
        aria-label="底部导航"
        className="fixed inset-x-3 bottom-3 z-30 grid grid-cols-5 gap-1 rounded-2xl border border-border/60 bg-background/85 p-1.5 shadow-[0_18px_50px_-24px_rgb(15_23_42/0.55)] backdrop-blur-2xl lg:hidden"
        style={{ marginBottom: 'env(safe-area-inset-bottom)' }}
      >
        {MOBILE_PRIMARY.map((to) => {
          const item = NAV_ITEMS.find((nav) => nav.to === to)
          if (!item) return null
          const Icon = item.icon
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex min-w-0 flex-col items-center gap-0.5 rounded-xl py-1.5 text-[10px] transition-colors',
                  'focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none',
                  isActive
                    ? 'bg-[linear-gradient(160deg,color-mix(in_oklch,var(--primary)_18%,transparent),transparent)] font-medium text-primary'
                    : 'text-muted-foreground',
                )
              }
            >
              <Icon aria-hidden="true" className="size-[18px]" />
              <span className="max-w-full truncate px-0.5">{item.label}</span>
            </NavLink>
          )
        })}
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          aria-label="打开更多导航"
          className="flex min-w-0 flex-col items-center gap-0.5 rounded-xl py-1.5 text-[10px] text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
        >
          <Menu aria-hidden="true" className="size-[18px]" />
          <span>菜单</span>
        </button>
      </nav>

      {/* ---------- 移动端导航抽屉 ---------- */}
      {menuOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="关闭导航菜单"
            onClick={() => setMenuOpen(false)}
            className="absolute inset-0 bg-background/60 backdrop-blur-sm"
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="全部导航"
            className="drawer-in absolute inset-y-0 left-0 flex w-[18.5rem] max-w-[85vw] flex-col border-r border-sidebar-border/70 bg-sidebar shadow-2xl"
          >
            <div className="flex items-center justify-between px-4 pt-4 pb-3">
              <Brand />
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label="关闭导航菜单"
                onClick={() => setMenuOpen(false)}
              >
                <X aria-hidden="true" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-1">
              <NavItems onNavigate={() => setMenuOpen(false)} />
            </div>
            <div className="border-t border-sidebar-border/60 p-3">
              <SidebarFooter />
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  )
}
