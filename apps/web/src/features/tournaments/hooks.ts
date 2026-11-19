/**
 * 官方赛事 hooks。
 *
 * 同步是后台任务：启动后轮询进度，直到 status 不再是 running。
 */

import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  cancelTournamentSync,
  fetchEventTeamImport,
  fetchLatestTournamentSync,
  fetchTournament,
  fetchTournamentSyncRun,
  fetchTournaments,
  startTournamentSync,
  type TournamentQueryParams,
} from './api'

export const tournamentListKey = (params: TournamentQueryParams) =>
  ['tournaments', 'list', params] as const

export const tournamentDetailKey = (id: number) => ['tournaments', 'detail', id] as const

export function useTournaments(params: TournamentQueryParams) {
  return useQuery({
    queryKey: tournamentListKey(params),
    queryFn: ({ signal }) => fetchTournaments(params, signal),
    staleTime: 5 * 60_000,
    placeholderData: (previous) => previous,
  })
}

export function useTournament(id: number | null) {
  return useQuery({
    queryKey: tournamentDetailKey(id ?? 0),
    queryFn: ({ signal }) => fetchTournament(id as number, signal),
    enabled: id != null,
    staleTime: 5 * 60_000,
  })
}

/** 一键建队用的队伍草稿（不落库）。 */
export function useEventTeamImport(tournamentId: number, teamId: number | null) {
  return useQuery({
    queryKey: ['tournaments', 'team-import', tournamentId, teamId],
    queryFn: ({ signal }) => fetchEventTeamImport(tournamentId, teamId as number, signal),
    enabled: teamId != null,
    staleTime: 5 * 60_000,
  })
}

export function useLatestTournamentSync() {
  return useQuery({
    queryKey: ['tournaments', 'sync', 'latest'],
    queryFn: ({ signal }) => fetchLatestTournamentSync(signal),
    staleTime: 10_000,
  })
}

export function useTournamentSyncRun(runId: number | null) {
  return useQuery({
    queryKey: ['tournaments', 'sync', runId],
    queryFn: ({ signal }) => fetchTournamentSyncRun(runId as number, signal),
    enabled: runId != null,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 1500 : false),
  })
}

/**
 * 跟随最近一次同步（刷新页面后继续轮询，而不是停在加载那一刻）。
 *
 * 与历史使用率页同一处理：latest 每 5 秒核对一次；拿到 run id 后交给
 * `useTournamentSyncRun` 按 1.5 秒轮询，结束后自动停。`overrideId` 是本页
 * 刚启动的任务。
 */
export function useActiveTournamentSync(overrideId: number | null = null) {
  const latest = useQuery({
    queryKey: ['tournaments', 'sync', 'latest'],
    queryFn: ({ signal }) => fetchLatestTournamentSync(signal),
    staleTime: 5_000,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 5_000 : 10_000),
  })
  const run = useTournamentSyncRun(overrideId ?? latest.data?.id ?? null)
  return { latest, run: run.data ?? latest.data ?? null }
}

/** 同步结束后刷新赛事列表与详情（新赛事 / 新队表）。 */
export function useRefreshTournaments() {
  const client = useQueryClient()
  return useCallback(() => {
    void client.invalidateQueries({ queryKey: ['tournaments'] })
  }, [client])
}

export function useStartTournamentSync() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: startTournamentSync,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['tournaments', 'sync'] })
    },
  })
}

export function useCancelTournamentSync() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: cancelTournamentSync,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['tournaments', 'sync'] })
    },
  })
}
