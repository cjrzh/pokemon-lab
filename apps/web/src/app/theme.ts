import { createContext, useContext } from 'react'

export type Theme = 'light' | 'dark' | 'system'

export type ResolvedTheme = 'light' | 'dark'

/** 与 index.html 中的预加载脚本保持一致，否则会出现主题闪烁。 */
export const THEME_STORAGE_KEY = 'pokemon-lab:theme'

export interface ThemeContextValue {
  /** 用户选择的主题（可能是跟随系统）。 */
  theme: Theme
  /** 实际生效的主题。 */
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext)
  if (!value) {
    throw new Error('useTheme 必须在 <ThemeProvider> 内部使用。')
  }
  return value
}