/**
 * 双打建队 API：类型定义与请求函数。
 *
 * 后端契约见 services/api/app/schemas/teams.py。
 * 个人项目不做浏览器隔离：所有队伍对所有访问者可见；合法性由后端按版本数据校验。
 */

import { apiRequest, streamSse, type StreamOptions } from '@/lib/apiClient'

export interface TeamOptionUsage {
  slug: string
  name: string
  name_en: string | null
  type?: string | null
  icon_url?: string | null
  pct: number
}

export interface TeamSpread {
  nature: string
  nature_label: string
  points: number[]
  pct: number
}

export interface TeamRecommendations {
  showdown_name: string
  rank: number | null
  usage: number | null
  abilities: TeamOptionUsage[]
  items: TeamOptionUsage[]
  moves: TeamOptionUsage[]
  spread: TeamSpread | null
  spreads: TeamSpread[]
}

/** 建队时可选的形态（含默认形态），按使用率降序。 */
export interface TeamFormOption {
  /** 本地形态 slug；默认形态为 null */
  form: string | null
  label: string
  /** Showdown 显示名（导出与统计口径，如 Rotom-Wash） */
  showdown_name: string
  types: string[]
  sprite_url: string | null
  /** 该形态在该格式的使用率；没有统计时为 null */
  usage: number | null
  is_default: boolean
}

export interface TeamMemberOptions {
  dex_number: number
  showdown_name: string
  name_zh: string | null
  name_en: string | null
  types: string[]
  artwork_url: string | null
  sprite_url: string | null
  gender_rate: number | null
  /** 当前生效的形态（默认形态为 null） */
  form: string | null
  /** 可切换的形态（含默认形态）；只有一种形态时为空 */
  forms: TeamFormOption[]
  legal_moves: TeamOptionUsage[]
  legal_abilities: TeamOptionUsage[]
  /** 该格式统计里出现过的道具（按使用率降序，带图标）；无统计时为空。 */
  legal_items: TeamOptionUsage[]
  recommended: TeamRecommendations | null
  has_stats: boolean
  /** 该形态能否超极巨化（只有剑盾有实际意义；来自 Showdown pokedex）。 */
  can_gigantamax: boolean
  /** 超极巨化后的 G 招式名（如 `G-Max Wildfire`）；没有时为 null。 */
  gigantamax_move: string | null
  /**
   * 请求了 G 形态（`form=xxx-gmax`）时为 true：导入 `Charizard-Gmax` 时
   * 编辑器据此把「超极巨化」开关勾上。
   */
  gigantamax: boolean
}

export interface TeamMemberInput {
  dex_number: number
  showdown_name: string
  nickname?: string | null
  item?: string | null
  ability?: string | null
  nature?: string | null
  evs: number[]
  ivs?: number[] | null
  moves: string[]
  tera_type?: string | null
  gender?: 'M' | 'F' | null
  shiny?: boolean
  level?: number | null
  /** 极巨化等级 0–10（仅剑盾；缺省 / null 表示 Showdown 默认值 10）。 */
  dynamax_level?: number | null
  /** 超极巨化（仅剑盾；只有带 G 形态的物种合法）。 */
  gigantamax?: boolean
  /** Showdown 导出语言标记，缺省 CHS。 */
  language?: TeamLanguage
}

/** Showdown 支持的语言标记（与后端 `LANGUAGES` 一致）。 */
export const LANGUAGES = [
  'CHS',
  'CHT',
  'ENG',
  'JPN',
  'KOR',
  'FRA',
  'GER',
  'ITA',
  'ESP',
] as const
export type TeamLanguage = (typeof LANGUAGES)[number]

export interface TeamMember extends TeamMemberInput {
  position: number
  /**
   * 本地形态 slug（默认形态为 null）。保存时后端按 `showdown_name` 反查填充，
   * 编辑器据此定位形态选择器；不属于提交字段。
   */
  form?: string | null
}

export interface TeamFormat {
  key: string
  label: string
  short_label: string
  points_kind: 'ev' | 'stat_points'
  trade_prefix: string | null
  default_level: number
  month: string
  cutoff: number
}

export interface TeamSummary {
  id: number
  name: string
  format_key: string
  format_label: string | null
  note: string | null
  member_count: number
  updated_at: string | null
  /** 是否已保存过评价（列表只给标志，详情才带完整内容）。 */
  has_analysis?: boolean
}

export interface TeamDetail extends TeamSummary {
  members: TeamMember[]
  trade_prefix: string | null
  default_level: number
  points_kind: 'ev' | 'stat_points'
  /** 上次保存的评价；未评价过为 null。 */
  analysis?: StoredAnalysis | null
}

export interface TeamListResponse {
  items: TeamSummary[]
  formats: TeamFormat[]
}

export interface ValidationIssue {
  field: string
  message: string
}

export interface TeamValidationResult {
  ok: boolean
  issues: ValidationIssue[]
  warnings: string[]
}

export interface TeamShowdown {
  team_id: number
  name: string
  format_key: string
  format_label: string | null
  trade_prefix: string | null
  points_kind: 'ev' | 'stat_points'
  text: string
}

export interface TeamImportResult {
  format_key: string
  /** 解析出的成员（未落库），可直接进编辑器。 */
  members: TeamMemberInput[]
  /** 未能导入的条目说明（物种名识别不到、重复、超过 6 只…）。 */
  problems: string[]
  warnings: string[]
}

export function fetchTeams(signal?: AbortSignal): Promise<TeamListResponse> {
  return apiRequest<TeamListResponse>('/teams', { signal })
}

/** 保存拖拽后的队伍顺序（完整 id 列表）。 */
export function reorderTeams(teamIds: number[]): Promise<TeamListResponse> {
  return apiRequest<TeamListResponse>('/teams/order', {
    method: 'PUT',
    body: { team_ids: teamIds },
  })
}

export function fetchTeam(teamId: number, signal?: AbortSignal): Promise<TeamDetail> {
  return apiRequest<TeamDetail>(`/teams/${teamId}`, { signal })
}

export function createTeam(payload: {
  name: string
  format_key: string
  note?: string | null
  members: TeamMemberInput[]
}): Promise<TeamDetail> {
  return apiRequest<TeamDetail>('/teams', { method: 'POST', body: payload })
}

export function updateTeam(
  teamId: number,
  payload: {
    name?: string
    note?: string | null
    members?: TeamMemberInput[]
  },
): Promise<TeamDetail> {
  return apiRequest<TeamDetail>(`/teams/${teamId}`, { method: 'PUT', body: payload })
}

export function deleteTeam(teamId: number): Promise<void> {
  return apiRequest<void>(`/teams/${teamId}`, { method: 'DELETE' })
}

export function validateTeam(payload: {
  name: string
  format_key: string
  members: TeamMemberInput[]
}): Promise<TeamValidationResult> {
  return apiRequest<TeamValidationResult>('/teams/validate', { method: 'POST', body: payload })
}

/** 解析 Showdown 队伍代码；只返回成员，不落库（用户确认后走 createTeam）。 */
export function importTeam(payload: {
  format_key: string
  text: string
}): Promise<TeamImportResult> {
  return apiRequest<TeamImportResult>('/teams/import', { method: 'POST', body: payload })
}

/** 批量修改的请求体：只传要改的字段（显式传 null = 恢复默认）。 */
export interface TeamBatchPayload {
  members: TeamMemberInput[]
  shine?: boolean
  level?: number | null
  gender?: 'M' | 'F' | null
}

export interface TeamBatchResult {
  members: TeamMember[]
  /** 因规则限制保持原样的成员说明（如尼多朗只能雄性）。 */
  skipped: string[]
}

/** 批量改闪光 / 等级 / 性别；不落库，返回改好的成员给草稿。 */
export function batchTeamMembers(payload: TeamBatchPayload): Promise<TeamBatchResult> {
  return apiRequest<TeamBatchResult>('/teams/batch', { method: 'POST', body: payload })
}

// ---------------------------- 队伍评价 ----------------------------

export interface AnalysisMember {
  dex_number: number | null
  name: string
  types: string[]
}

export interface AnalysisAttack {
  type: string
  type_zh: string
  hits: string[]
  hits_zh: string[]
  member_count: number
}

export interface AnalysisHotspot {
  type: string
  type_zh: string
  members: number[]
}

export interface TeamAnalysis {
  members: AnalysisMember[]
  attack: AnalysisAttack[]
  gaps: string[]
  gaps_zh: string[]
  hotspots: AnalysisHotspot[]
  /** LLM 的解读；为 null 时看 `llm_error`。 */
  llm: { text: string; model: string | null } | null
  llm_error: string | null
}

/** 落库的队伍评价：快照 + 生成时间 + 是否已过期。 */
export interface StoredAnalysis {
  analysis: TeamAnalysis
  generated_at: string | null
  /** 生成后又改过成员时为 true，此时结论不对应当前配置。 */
  stale: boolean
}

// ---------------------------- 流式评价 ----------------------------

/** 流式评价的增量事件（与后端 `stream_team_analysis` 对应）。 */
export type TeamAnalysisEvent =
  | { event: 'coverage'; data: TeamAnalysis }
  | { event: 'delta'; text: string; model?: string | null }
  | { event: 'done'; text: string; model?: string | null }
  | { event: 'error'; text: string }

/**
 * 流式评价草稿（不落库）。
 *
 * 用 SSE 而不是普通请求：模型是推理模型，完整回答要 10–50 秒，
 * 普通请求会撞上前端 10 秒超时。流式下只要字节在流动就不会超时。
 */
export function streamDraftAnalysis(
  payload: { members: TeamMemberInput[]; format_key?: string; use_llm?: boolean },
  onEvent: (event: TeamAnalysisEvent) => void,
  options: StreamOptions = {},
): Promise<void> {
  return streamSse(
    '/teams/analyze/stream',
    (raw) => onEvent(raw as TeamAnalysisEvent),
    { ...options, method: 'POST', body: payload },
  )
}

/** 流式评价并保存（已保存队伍）。 */
export function streamSavedAnalysis(
  teamId: number,
  useLlm: boolean,
  onEvent: (event: TeamAnalysisEvent) => void,
  options: StreamOptions = {},
): Promise<void> {
  const params = new URLSearchParams({ use_llm: String(useLlm) })
  return streamSse(
    `/teams/${teamId}/analyze/stream?${params.toString()}`,
    (raw) => onEvent(raw as TeamAnalysisEvent),
    { ...options, method: 'POST' },
  )
}

export function fetchTeamShowdown(teamId: number, signal?: AbortSignal): Promise<TeamShowdown> {
  return apiRequest<TeamShowdown>(`/teams/${teamId}/showdown`, { signal })
}

export function fetchTeamMemberOptions(
  dexNumber: number,
  formatKey: string,
  signal?: AbortSignal,
  form?: string | null,
): Promise<TeamMemberOptions> {
  const params = new URLSearchParams({ format: formatKey })
  // null 表示「自动选使用率最高的形态」；显式选默认形态传 `default`。
  if (form) params.set('form', form)
  return apiRequest<TeamMemberOptions>(
    `/pokemon/${dexNumber}/team-options?${params.toString()}`,
    { signal },
  )
}
