import { apiRequest } from '@/lib/apiClient'

export type HealthStatus = 'ok' | 'degraded' | 'error'

export interface HealthCheck {
  name: string
  status: HealthStatus
  detail: string
}

export interface HealthResponse {
  /** 整体状态：任一检查项非 ok 时为 degraded */
  status: 'ok' | 'degraded'
  service: string
  version: string
  generated_at: string
  checks: HealthCheck[]
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', { signal })
}