/**
 * 招式数据 hooks（TanStack Query）。
 */

import { useQuery } from '@tanstack/react-query'

import { fetchMoveDetail, fetchMoveList, type MoveListParams } from './api'

export const moveListKey = (params: MoveListParams) => ['moves', 'list', params] as const
export const moveDetailKey = (name: string) => ['moves', 'detail', name] as const

export function useMoveList(params: MoveListParams) {
  return useQuery({
    queryKey: moveListKey(params),
    queryFn: ({ signal }) => fetchMoveList(params, signal),
    staleTime: 5 * 60_000,
    placeholderData: (previous) => previous,
  })
}

export function useMoveDetail(name: string | null) {
  return useQuery({
    queryKey: moveDetailKey(name ?? ''),
    queryFn: ({ signal }) => fetchMoveDetail(name as string, signal),
    enabled: Boolean(name),
    staleTime: 5 * 60_000,
  })
}
