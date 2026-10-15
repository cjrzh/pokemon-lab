import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/lib/apiClient'

/**
 * 全局 QueryClient 配置。
 *
 * 与「外部 API 必须处理超时、失败、加载状态与缓存」这条约束对应：
 *   - staleTime / gcTime 决定「缓存」行为
 *   - retry 只重试可恢复错误（超时、网络故障、5xx），4xx 与解析失败直接暴露给用户
 *   - 超时由 apiClient 的 AbortController 负责，这里不再叠加
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          return error.retryable && failureCount < 2
        }
        return failureCount < 1
      },
    },
    mutations: {
      retry: false,
    },
  },
})