/**
 * Smogon 历史使用率 hooks。
 *
 * 同步是后台任务：启动后轮询进度，直到 status 不再是 running。
 */

import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  cancelUsageSync,
  fetchLatestSync,
  fetchSyncRun,
  fetchUsageHistory,
  startUsageSync,
  type UsageQueryParams,
} from './api'

export const usageHistoryKey = (params: UsageQueryParams) =>
  ['usage-history', params] as const

export function useUsageHistory(params: UsageQueryParams) {
  return useQuery({
    queryKey: usageHistoryKey(params),
    queryFn: ({ signal }) => fetchUsageHistory(params, signal),
    staleTime: 5 * 60_000,
    placeholderData: (previous) => previous,
  })
}

export function useLatestSync() {
  return useQuery({
    queryKey: ['usage-sync', 'latest'],
    queryFn: ({ signal }) => fetchLatestSync(signal),
    staleTime: 10_000,
  })
}

/** 轮询同步进度：只在 running 时继续拉取。 */
export function useSyncRun(runId: number | null) {
  return useQuery({
    queryKey: ['usage-sync', runId],
    queryFn: ({ signal }) => fetchSyncRun(runId as number, signal),
    enabled: runId != null,
    // 轮询只在任务进行中继续；结束（done/error/cancelled）后自动停
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 1500 : false),
  })
}

/**
 * 跟随最近一次同步的进度（刷新页面后也能继续看到实时进度）。
 *
 * - `latest` 在任务进行中每 5 秒核对一次，用于发现「另一个标签页刚启动的任务」；
 * - 拿到 run id 后交给 `useSyncRun` 按 1.5 秒轮询，结束后自动停；
 * - `overrideId` 是本页刚启动的任务：优先于 latest，避免 latest 还没刷新时
 *   短暂显示成上一次的记录。
 */
export function useActiveSyncRun(overrideId: number | null = null) {
  const latest = useQuery({
    queryKey: ['usage-sync', 'latest'],
    queryFn: ({ signal }) => fetchLatestSync(signal),
    staleTime: 5_000,
    // 进行中每 5 秒核对；空闲时 10 秒一次（仅标签页可见时）——
    // 这样另一个标签页刚启动的同步也能被发现。
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 5_000 : 10_000),
  })
  const run = useSyncRun(overrideId ?? latest.data?.id ?? null)
  return {
    latest,
    /** 最新状态：有进度查询就用它，否则用最近一次同步记录 */
    run: run.data ?? latest.data ?? null,
  }
}

export function useStartSync() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: startUsageSync,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['usage-sync'] })
    },
  })
}

/** 同步完成后刷新榜单（快照数、月份列表、当前快照都会变）。 */
export function useRefreshUsageHistory() {
  const client = useQueryClient()
  // 稳定的引用：页面在「同步结束」的 effect 里调用它，不能每次渲染都变
  return useCallback(() => {
    void client.invalidateQueries({ queryKey: ['usage-history'] })
  }, [client])
}

export function useCancelSync() {
  return useMutation({
    mutationFn: (runId: number) => cancelUsageSync(runId),
  })
}
