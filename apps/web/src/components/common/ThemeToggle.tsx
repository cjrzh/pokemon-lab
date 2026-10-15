import { Monitor, Moon, Sun } from 'lucide-react'

import { useTheme } from '@/app/theme'
import type { Theme } from '@/app/theme'
import { Button } from '@/components/ui/button'

const ORDER: readonly Theme[] = ['light', 'dark', 'system']

const LABELS: Record<Theme, string> = {
  light: '浅色',
  dark: '深色',
  system: '跟随系统',
}

export interface ThemeToggleProps {
  className?: string
  /** 是否在按钮内显示当前模式文字（侧边栏用 false，设置区用 true）。 */
  showLabel?: boolean
}

/** 主题切换：浅色 → 深色 → 跟随系统 三态循环，无需额外下拉组件依赖。 */
export function ThemeToggle({ className, showLabel = false }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme()

  const currentIndex = ORDER.indexOf(theme)
  const nextTheme = ORDER[(currentIndex + 1) % ORDER.length] ?? 'system'
  const Icon = theme === 'light' ? Sun : theme === 'dark' ? Moon : Monitor
  const hint = `当前主题：${LABELS[theme]}，点击切换为${LABELS[nextTheme]}`

  return (
    <Button
      type="button"
      variant="ghost"
      size={showLabel ? 'sm' : 'icon-sm'}
      className={className}
      onClick={() => setTheme(nextTheme)}
      title={hint}
      aria-label={hint}
    >
      <Icon aria-hidden="true" />
      {showLabel ? <span>{LABELS[theme]}</span> : null}
    </Button>
  )
}