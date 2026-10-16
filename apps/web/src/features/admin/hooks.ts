/**
 * 后台管理 hooks。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createPokemon,
  editPokemon,
  fetchOpLogs,
  fetchSyncStatus,
  triggerSync,
  type PokemonEditPayload,
} from './api'
import { pokemonDetailKey } from '@/features/dex/hooks'

export function useSyncStatus() {
  return useQuery({
    queryKey: ['admin', 'sync-status'],
    queryFn: ({ signal }) => fetchSyncStatus(signal),
    refetchInterval: 15_000, // 同步进行中时页面能看到数字增长
  })
}

export function useTriggerSync() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { start: number; end: number; force?: boolean }) =>
      triggerSync(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'sync-status'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'ops'] })
      void queryClient.invalidateQueries({ queryKey: ['pokemon'] })
    },
  })
}

export function useOpLogs() {
  return useQuery({
    queryKey: ['admin', 'ops'],
    queryFn: ({ signal }) => fetchOpLogs(signal),
  })
}

export function useEditPokemon(dexNumber: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PokemonEditPayload) => editPokemon(dexNumber, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pokemonDetailKey(dexNumber) })
      void queryClient.invalidateQueries({ queryKey: ['pokemon', 'list'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'ops'] })
    },
  })
}

export function useCreatePokemon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PokemonEditPayload & { dex_number: number }) => createPokemon(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['pokemon', 'list'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'ops'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'sync-status'] })
    },
  })
}
