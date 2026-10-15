import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'

import { ThemeProvider } from './ThemeProvider'
import { queryClient } from './queryClient'

export interface AppProvidersProps {
  children: ReactNode
}

/** 统一装配全局 Provider，main.tsx 与测试都可复用。 */
export function AppProviders({ children }: AppProvidersProps) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  )
}