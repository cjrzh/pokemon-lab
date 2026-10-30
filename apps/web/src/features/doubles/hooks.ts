/**
 * 双打辅助数据 hooks（TanStack Query）。
 *
 * 统计是月度快照，同一天内不会变化：缓存 10 分钟，切回页面时直接复用。
 */

import { useQuery } from '@tanstack/react-query'

import { fetchDoubles } from './api'

export const doublesKey = (dexNumber: number) => ['doubles', dexNumber] as const

export function useDoubles(dexNumber: number) {
  return useQuery({
    queryKey: doublesKey(dexNumber),
    queryFn: ({ signal }) => fetchDoubles(dexNumber, signal),
    staleTime: 10 * 60_000,
    enabled: Number.isInteger(dexNumber) && dexNumber > 0,
  })
}
