import { useQuery } from '@tanstack/react-query'

import { fetchHealth } from './api'

export const healthQueryKey = ['health'] as const

/**
 * 后端健康状态。
 * 刷新频率刻意放低：这是「自检」信息，不需要高频轮询。
 */
export function useHealth() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(signal),
    staleTime: 15_000,
    retry: 1,
  })
}