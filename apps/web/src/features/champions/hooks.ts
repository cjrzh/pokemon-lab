/**
 * 冠军图鉴 hooks（TanStack Query）。
 *
 * 榜单直接复用「使用率」页的查询（`format=champions`），明细复用图鉴详情页的
 * 「双打对战辅助」查询，再从响应里挑出冠军那一段 —— 不重复请求、不额外缓存一份。
 */

import { useDoubles } from '@/features/doubles/hooks'
import { useUsageRanking } from '@/features/usage/hooks'

import { CHAMPIONS_FORMAT, championsBlock } from './api'

export interface ChampionsRankingParams {
  q?: string
  page?: number
  page_size?: number
}

/** 冠军双打排行榜（与 `/usage-ranking?format=champions` 同一份数据）。 */
export function useChampionsRanking(params: ChampionsRankingParams) {
  return useUsageRanking({ format: CHAMPIONS_FORMAT, ...params })
}

/** 单只宝可梦的冠军配装明细；`block` 为空表示该宝可梦没有冠军统计。 */
export function useChampionsProfile(dexNumber: number) {
  const query = useDoubles(dexNumber)
  return { ...query, block: championsBlock(query.data) }
}
