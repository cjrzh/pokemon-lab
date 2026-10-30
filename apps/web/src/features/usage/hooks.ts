/**
 * 使用率排行 hooks（TanStack Query）。
 *
 * 数据是月度快照，同一天内不会变化：缓存 10 分钟；翻页 / 切格式时
 * 保留旧数据避免整页闪烁。
 */

import { useQuery } from '@tanstack/react-query'

import { fetchUsageRanking, type UsageRankingParams } from '@/features/usage/api'

export const usageRankingKey = (params: UsageRankingParams) =>
  ['usage-ranking', params] as const

export function useUsageRanking(params: UsageRankingParams) {
  return useQuery({
    queryKey: usageRankingKey(params),
    queryFn: ({ signal }) => fetchUsageRanking(params, signal),
    staleTime: 10 * 60_000,
    placeholderData: (previous) => previous,
  })
}
