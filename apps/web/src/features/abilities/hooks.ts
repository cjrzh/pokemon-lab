/**
 * 特性数据 hooks（TanStack Query）。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchAbilityDetail,
  fetchAbilityList,
  fetchSTierAbilityNames,
  updateAbilityRating,
  type AbilityListParams,
  type AbilityTier,
} from './api'

export const abilityListKey = (params: AbilityListParams) => ['abilities', 'list', params] as const
export const abilityDetailKey = (name: string) => ['abilities', 'detail', name] as const
export const sTierAbilityKey = ['abilities', 's-tier'] as const

export function useAbilityList(params: AbilityListParams) {
  return useQuery({
    queryKey: abilityListKey(params),
    queryFn: ({ signal }) => fetchAbilityList(params, signal),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  })
}

export function useAbilityDetail(name: string | null) {
  return useQuery({
    queryKey: abilityDetailKey(name ?? ''),
    queryFn: ({ signal }) => fetchAbilityDetail(name as string, signal),
    enabled: Boolean(name),
    staleTime: 5 * 60_000,
  })
}

/** S 级特性名集合：图鉴页用于标红加粗，缓存 5 分钟。 */
export function useSTierAbilityNames() {
  return useQuery({
    queryKey: sTierAbilityKey,
    queryFn: ({ signal }) => fetchSTierAbilityNames(signal),
    staleTime: 5 * 60_000,
    select: (names) => names,
  })
}

export function useUpdateAbilityRating(name: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { tier: AbilityTier; note?: string | null }) =>
      updateAbilityRating(name, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['abilities'] })
    },
  })
}
