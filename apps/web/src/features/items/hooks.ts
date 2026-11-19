/**
 * 道具数据 hooks（TanStack Query）。
 */

import { useQuery } from '@tanstack/react-query'

import { fetchItemList, type ItemListParams } from './api'

export const itemListKey = (params: ItemListParams) => ['items', 'list', params] as const

export function useItemList(params: ItemListParams) {
  return useQuery({
    queryKey: itemListKey(params),
    queryFn: ({ signal }) => fetchItemList(params, signal),
    staleTime: 10 * 60_000,
    placeholderData: (previous) => previous,
  })
}
