/**
 * 双打建队 hooks（TanStack Query）。
 *
 * 队伍是用户数据，改动后要立刻反映到列表与详情，因此在 mutation 成功后
 * 主动失效相关 query，而不是等 staleTime。
 */

import { useCallback, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { describeApiError } from '@/lib/apiClient'
import {
  batchTeamMembers,
  createTeam,
  deleteTeam,
  fetchTeam,
  fetchTeamMemberOptions,
  fetchTeamShowdown,
  fetchTeams,
  importTeam,
  reorderTeams,
  streamDraftAnalysis,
  streamSavedAnalysis,
  updateTeam,
  validateTeam,
  type TeamAnalysis,
  type TeamAnalysisEvent,
  type TeamMemberInput,
} from './api'

export const teamsKey = () => ['teams', 'list'] as const
export const teamKey = (teamId: number) => ['teams', 'detail', teamId] as const
export const teamShowdownKey = (teamId: number) => ['teams', 'showdown', teamId] as const
export const teamOptionsKey = (dex: number, format: string, form?: string | null) =>
  ['teams', 'options', dex, format, form ?? 'auto'] as const

export function useTeams() {
  return useQuery({
    queryKey: teamsKey(),
    queryFn: ({ signal }) => fetchTeams(signal),
    staleTime: 30_000,
  })
}

export function useTeam(teamId: number | null) {
  return useQuery({
    queryKey: teamKey(teamId ?? -1),
    queryFn: ({ signal }) => fetchTeam(teamId as number, signal),
    enabled: teamId != null && teamId > 0,
    staleTime: 30_000,
  })
}

export function useTeamShowdown(teamId: number | null) {
  return useQuery({
    queryKey: teamShowdownKey(teamId ?? -1),
    queryFn: ({ signal }) => fetchTeamShowdown(teamId as number, signal),
    enabled: teamId != null && teamId > 0,
    staleTime: 30_000,
  })
}

export function useTeamMemberOptions(
  dexNumber: number | null,
  formatKey: string,
  form?: string | null,
) {
  return useQuery({
    queryKey: teamOptionsKey(dexNumber ?? -1, formatKey, form),
    queryFn: ({ signal }) =>
      fetchTeamMemberOptions(dexNumber as number, formatKey, signal, form),
    enabled: dexNumber != null && dexNumber > 0 && Boolean(formatKey),
    staleTime: 5 * 60_000,
  })
}

export function useCreateTeam() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: createTeam,
    onSuccess: () => void client.invalidateQueries({ queryKey: teamsKey() }),
  })
}

export function useUpdateTeam() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, payload }: { teamId: number; payload: { name?: string; note?: string | null; members?: TeamMemberInput[] } }) =>
      updateTeam(teamId, payload),
    onSuccess: (_data, variables) => {
      void client.invalidateQueries({ queryKey: teamsKey() })
      void client.invalidateQueries({ queryKey: teamKey(variables.teamId) })
      void client.invalidateQueries({ queryKey: teamShowdownKey(variables.teamId) })
    },
  })
}

/** 保存队伍顺序：成功后把新列表写回缓存，不需要再拉一次。 */
export function useReorderTeams() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: reorderTeams,
    // 乐观更新：拖动是即时交互，等接口回来再换顺序会「闪一下」
    onMutate: async (teamIds) => {
      await client.cancelQueries({ queryKey: teamsKey() })
      const previous = client.getQueryData<{ items: { id: number }[] }>(teamsKey())
      if (previous) {
        const byId = new Map(previous.items.map((team) => [team.id, team]))
        const ordered = teamIds
          .map((id) => byId.get(id))
          .filter((team): team is NonNullable<typeof team> => Boolean(team))
        client.setQueryData(teamsKey(), { ...previous, items: ordered })
      }
      return { previous }
    },
    onError: (_error, _ids, context) => {
      if (context?.previous) client.setQueryData(teamsKey(), context.previous)
    },
    onSuccess: (data) => client.setQueryData(teamsKey(), data),
  })
}

export function useDeleteTeam() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: deleteTeam,
    onSuccess: () => void client.invalidateQueries({ queryKey: teamsKey() }),
  })
}

/** 编辑过程中的即时校验（防抖由调用方决定）。 */
export function useValidateTeam() {
  return useMutation({ mutationFn: validateTeam })
}

/** 解析 Showdown 队伍代码（不落库）。 */
export function useImportTeam() {
  return useMutation({ mutationFn: importTeam })
}

/** 批量改闪光 / 等级 / 性别（不落库）。 */
export function useBatchTeamMembers() {
  return useMutation({ mutationFn: batchTeamMembers })
}

export interface StreamAnalysisParams {
  teamId?: number | null
  members: TeamMemberInput[]
  /** 队伍所在版本（草稿要用；保存的队伍按库里的版本）。 */
  formatKey: string
  useLlm: boolean
}

/**
 * 流式队伍评价：边收边更新 UI。
 *
 * 为什么不用 mutation：LLM 是推理模型，完整回答要 10–50 秒。普通 fetch 会撞上
 * `apiRequest` 的 10 秒超时；SSE 只要有字节流动就不会超时，而且能更早显示内容。
 *
 * 返回的状态：
 *   - `coverage`：计算部分（首帧就有）
 *   - `text`：已收到的 AI 正文（增量拼接）
 *   - `reasoning`：是否还在思考阶段（已收到思维链但还没有正文）
 *   - `running` / `error`：请求状态
 */
export function useStreamTeamAnalysis() {
  const client = useQueryClient()
  const abortRef = useRef<AbortController | null>(null)
  const [running, setRunning] = useState(false)
  const [coverage, setCoverage] = useState<TeamAnalysis | null>(null)
  const [text, setText] = useState('')
  const [model, setModel] = useState<string | null>(null)
  const [llmError, setLlmError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
  }, [])

  const start = useCallback(
    async ({ teamId, members, formatKey, useLlm }: StreamAnalysisParams) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setRunning(true)
      setCoverage(null)
      setText('')
      setModel(null)
      setLlmError(null)
      setError(null)

      try {
        const emit = (event: TeamAnalysisEvent) => {
          switch (event.event) {
            case 'coverage':
              setCoverage(event.data)
              break
            case 'delta':
              setText((prev) => prev + event.text)
              if (event.model) setModel(event.model)
              break
            case 'done':
              if (event.model) setModel(event.model)
              // done 带完整正文时以它为准（避免个别增量丢失）
              if (event.text) setText(event.text)
              break
            case 'error':
              setLlmError(event.text)
              break
          }
        }

        if (teamId && teamId > 0) {
          await streamSavedAnalysis(teamId, useLlm, emit, { signal: controller.signal })
          // 落库版本已在服务端更新，刷新详情让「更新评价」按钮拿到最新状态
          void client.invalidateQueries({ queryKey: teamKey(teamId) })
          void client.invalidateQueries({ queryKey: teamsKey() })
        } else {
          await streamDraftAnalysis({ members, format_key: formatKey, use_llm: useLlm }, emit, {
            signal: controller.signal,
          })
        }
      } catch (cause) {
        // 用户主动取消不算错误
        if (!controller.signal.aborted) {
          setError(describeApiError(cause))
        }
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
          setRunning(false)
        }
      }
    },
    [client],
  )

  return { start, stop, running, coverage, text, model, llmError, error }
}
