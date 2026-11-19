/**
 * 官方赛事 API：类型定义与请求函数。
 *
 * 后端契约见 services/api/app/schemas/tournaments.py。
 * 数据来自 Limitless VGC：赛事成绩、选手队表（物种 / 道具 / 特性 / 性格 / 太晶 /
 * 招式）与由全部队表重算的使用率。赛事未公开 EV / IV。
 */

import { apiRequest } from '@/lib/apiClient'

export interface TournamentSummary {
  id: number
  source_id: number
  name: string
  date: string
  ruleset: string
  ruleset_label: string
  event_type: string
  event_type_label: string
  country: string | null
  players: number
  winner: string | null
  winner_country: string | null
  /** 可一键建队的格式；null 表示本地无法建队 */
  format_key: string | null
  standings_count: number
  team_count: number
  has_teamlists: boolean
  source_url: string | null
}

export interface RulesetOption {
  identifier: string
  label: string
  game: string
  format_key: string | null
}

export interface TournamentListResponse {
  items: TournamentSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
  years: number[]
  rulesets: RulesetOption[]
}

export interface StandingView {
  rank: number
  player: string
  country: string | null
  species: string[]
  team_id: number | null
}

export interface EventTeamMember {
  position: number
  dex_number: number | null
  showdown_name: string
  species_slug: string
  item: string | null
  ability: string | null
  nature: string | null
  tera_type: string | null
  moves: string[]
  /** 超极巨化（剑盾）：队表的 `-Gmax` 别名已折算成基础形态 + 该标记。 */
  gigantamax: boolean
  /** 极巨化等级 0–10（赛事未公开，按 Showdown 默认值 10）。 */
  dynamax_level: number | null
}

export interface EventTeamValidation {
  ok?: boolean
  issues?: string[]
}

export interface EventTeam {
  id: number
  rank: number
  player: string
  country: string | null
  showdown_text: string
  problems: string[]
  /** 本地规则校验结果（源站笔误如实记录，不阻断建队） */
  validation?: EventTeamValidation
  members: EventTeamMember[]
}

export interface EventUsage {
  rank: number
  species_slug: string
  showdown_name: string
  dex_number: number | null
  count: number
  share: number
}

export interface TournamentDetail {
  tournament: TournamentSummary
  standings: StandingView[]
  teams: EventTeam[]
  usage: EventUsage[]
}

export interface EventTeamImport {
  tournament: TournamentSummary
  format_key: string
  default_level: number
  trade_prefix: string | null
  points_kind: 'ev' | 'stat_points'
  team: {
    id: number
    rank: number
    player: string
    showdown_text: string
    validation?: EventTeamValidation
  }
  members: EventTeamMemberForImport[]
  validation: { ok?: boolean; issues?: string[] }
}

/** 一键建队返回的成员字段（与后端 `TeamMemberInput` 一致）。 */
export interface EventTeamMemberForImport {
  dex_number: number
  showdown_name: string
  /** 本地非默认形态 slug（如 `urshifu-rapid-strike`）；默认形态为 null。 */
  form?: string | null
  item: string | null
  ability: string | null
  nature: string | null
  evs: number[]
  moves: string[]
  tera_type: string | null
  /** 官方赛事默认满级 100（与页面导出的 Showdown 代码一致）。 */
  level: number | null
  language: string
  /** 官方赛事默认闪光（`Shiny: Yes`）。 */
  shiny: boolean
  gender: 'M' | 'F' | null
  /** 超极巨化（剑盾）：`Gigantamax: Yes`。 */
  gigantamax: boolean
  /** 极巨化等级 0–10（剑盾；默认 10）。 */
  dynamax_level: number | null
}

export interface TournamentQueryParams {
  ruleset?: string
  event_type?: string
  format_key?: string
  year?: number
  q?: string
  page?: number
  page_size?: number
}

export function fetchTournaments(
  params: TournamentQueryParams,
  signal?: AbortSignal,
): Promise<TournamentListResponse> {
  const search = new URLSearchParams()
  if (params.ruleset) search.set('ruleset', params.ruleset)
  if (params.event_type) search.set('event_type', params.event_type)
  if (params.format_key) search.set('format_key', params.format_key)
  if (params.year) search.set('year', String(params.year))
  if (params.q) search.set('q', params.q)
  if (params.page) search.set('page', String(params.page))
  if (params.page_size) search.set('page_size', String(params.page_size))
  const qs = search.toString()
  return apiRequest<TournamentListResponse>(`/tournaments${qs ? `?${qs}` : ''}`, { signal })
}

export function fetchTournament(id: number, signal?: AbortSignal): Promise<TournamentDetail> {
  return apiRequest<TournamentDetail>(`/tournaments/${id}`, { signal })
}

/** 取一支队伍的建队草稿（不落库）。 */
export function fetchEventTeamImport(
  tournamentId: number,
  teamId: number,
  signal?: AbortSignal,
): Promise<EventTeamImport> {
  return apiRequest<EventTeamImport>(`/tournaments/${tournamentId}/teams/${teamId}`, { signal })
}

export interface TournamentSyncRun {
  id: number
  status: 'running' | 'done' | 'error' | 'cancelled'
  total: number
  done: number
  created: number
  skipped: number
  failed: number
  current: string | null
  message: string | null
  scope: Record<string, unknown>
  started_at: string | null
  finished_at: string | null
}

export interface TournamentSyncPayload {
  types?: string[]
  date_from?: string
  date_to?: string
  rulesets?: string[]
  refresh?: boolean
}

export function startTournamentSync(payload: TournamentSyncPayload): Promise<TournamentSyncRun> {
  return apiRequest<TournamentSyncRun>('/tournaments/sync', { method: 'POST', body: payload })
}

export function fetchTournamentSyncRun(
  runId: number,
  signal?: AbortSignal,
): Promise<TournamentSyncRun> {
  return apiRequest<TournamentSyncRun>(`/tournaments/sync/${runId}`, { signal })
}

export function fetchLatestTournamentSync(
  signal?: AbortSignal,
): Promise<TournamentSyncRun | null> {
  return apiRequest<TournamentSyncRun | null>('/tournaments/sync/latest', { signal })
}

export function cancelTournamentSync(runId: number): Promise<TournamentSyncRun> {
  return apiRequest<TournamentSyncRun>(`/tournaments/sync/${runId}/cancel`, { method: 'POST' })
}
