/**
 * API 客户端
 *
 * 统一处理三件事，避免每个页面组件各写一遍：
 *   1. 超时（AbortController + setTimeout，默认 10s）
 *   2. 失败分类（超时 / 网络不可达 / HTTP 错误 / 响应无法解析 / 主动取消）
 *   3. 返回值的空响应与 JSON 兼容
 *
 * 外部 API（PokéAPI）的超时、重试与缓存由后端负责，前端只面对自己的后端。
 */

export type ApiErrorKind = 'timeout' | 'network' | 'http' | 'parse' | 'aborted' | 'unknown'

export interface ApiErrorInit {
  kind: ApiErrorKind
  url: string
  status?: number
  detail?: string
}

function describe(init: ApiErrorInit): string {
  switch (init.kind) {
    case 'timeout':
      return `请求超时，请稍后重试（${init.url}）`
    case 'network':
      return `无法连接到服务，请确认后端已启动（${init.url}）`
    case 'aborted':
      return '请求已取消'
    case 'parse':
      return `服务返回的数据无法解析（${init.url}）`
    case 'http':
      return init.detail
        ? `服务返回错误 ${init.status}：${init.detail}`
        : `服务返回错误 ${init.status}`
    default:
      return `请求失败（${init.url}）`
  }
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly url: string
  readonly status: number | undefined
  readonly detail: string | undefined

  constructor(init: ApiErrorInit) {
    super(describe(init))
    this.name = 'ApiError'
    this.kind = init.kind
    this.url = init.url
    this.status = init.status
    this.detail = init.detail
  }

  /** 该错误是否值得自动重试。4xx 与解析失败属于确定性错误，重试无意义。 */
  get retryable(): boolean {
    if (this.kind === 'timeout' || this.kind === 'network') {
      return true
    }
    if (this.kind === 'http') {
      return this.status !== undefined && this.status >= 500
    }
    return false
  }
}

function normalizeBaseUrl(value: string | undefined): string {
  const base = (value ?? '/api/v1').trim()
  const withoutTrailingSlash = base.endsWith('/') ? base.slice(0, -1) : base
  return withoutTrailingSlash.length > 0 ? withoutTrailingSlash : '/api/v1'
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL)

export const DEFAULT_TIMEOUT_MS = 10_000

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
  headers?: Record<string, string>
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    (error as { name?: unknown }).name === 'AbortError'
  )
}

async function readErrorDetail(response: Response): Promise<string | undefined> {
  try {
    const text = await response.text()
    if (text.trim().length === 0) {
      return undefined
    }
    try {
      const parsed: unknown = JSON.parse(text)
      if (parsed !== null && typeof parsed === 'object' && 'detail' in parsed) {
        const detail = (parsed as { detail: unknown }).detail
        return typeof detail === 'string' ? detail : JSON.stringify(detail)
      }
      return text.slice(0, 300)
    } catch {
      return text.slice(0, 300)
    }
  } catch {
    return undefined
  }
}

/**
 * 发起一次 API 请求。
 *
 * @throws {ApiError} 所有失败路径统一抛出该类，调用方只需判断 `error.retryable`。
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, timeoutMs = DEFAULT_TIMEOUT_MS, headers } = options
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const forwardAbort = () => controller.abort()
  signal?.addEventListener('abort', forwardAbort)

  try {
    const response = await fetch(url, {
      method,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })

    if (!response.ok) {
      throw new ApiError({
        kind: 'http',
        url,
        status: response.status,
        detail: await readErrorDetail(response),
      })
    }

    // 204 与空响应体视为无返回值
    if (response.status === 204) {
      return undefined as T
    }

    const text = await response.text()
    if (text.trim().length === 0) {
      return undefined as T
    }

    try {
      return JSON.parse(text) as T
    } catch {
      throw new ApiError({ kind: 'parse', url, detail: '响应不是合法 JSON' })
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    if (isAbortError(error)) {
      throw new ApiError({ kind: timedOut ? 'timeout' : 'aborted', url })
    }
    throw new ApiError({
      kind: 'network',
      url,
      detail: error instanceof Error ? error.message : String(error),
    })
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forwardAbort)
  }
}

/** 把任意异常转成可直接展示给用户的中文文案。 */
export function describeApiError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return '发生未知错误'
}

// ---------------------------- SSE（流式） ----------------------------

export interface StreamOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  /** 连接超时秒数（只约束「迟迟没有任何数据」；有数据在流动就继续等）。 */
  idleTimeoutMs?: number
  headers?: Record<string, string>
}

/**
 * 读取一个 SSE 响应，把每个 `data: {...}` 事件交给 `onEvent`。
 *
 * 与 `apiRequest` 的区别：**没有总时长上限**。LLM 生成一段回答可能要几十秒，
 * 而 10 秒的普通请求超时必然失败。这里只约束「多久没收到任何字节」，
 * 只要服务端还在推增量就一直读下去。
 */
export async function streamSse(
  path: string,
  onEvent: (event: Record<string, unknown>) => void,
  options: StreamOptions = {},
): Promise<void> {
  const {
    method = 'POST',
    body,
    signal,
    idleTimeoutMs = 90_000,
    headers,
  } = options
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`

  const controller = new AbortController()
  let idleTimer: ReturnType<typeof setTimeout> | undefined
  const resetIdle = () => {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => controller.abort(), idleTimeoutMs)
  }
  const forwardAbort = () => controller.abort()
  signal?.addEventListener('abort', forwardAbort)
  resetIdle()

  try {
    const response = await fetch(url, {
      method,
      signal: controller.signal,
      headers: {
        Accept: 'text/event-stream',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })

    if (!response.ok) {
      throw new ApiError({
        kind: 'http',
        url,
        status: response.status,
        detail: await readErrorDetail(response),
      })
    }
    if (!response.body) {
      throw new ApiError({ kind: 'parse', url, detail: '响应没有可读取的流' })
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      resetIdle()
      buffer += decoder.decode(value, { stream: true })

      // SSE 事件以空行分隔；同时兼容 \r\n
      let boundary = buffer.search(/\r?\n\r?\n/)
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + (buffer[boundary] === '\r' ? 4 : 2))
        const data = raw
          .split(/\r?\n/)
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).trim())
          .join('\n')
        if (data) {
          try {
            onEvent(JSON.parse(data) as Record<string, unknown>)
          } catch {
            // 单条事件坏了不影响后续；服务端若整体失败会另发 error 事件
          }
        }
        boundary = buffer.search(/\r?\n\r?\n/)
      }
    }
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (isAbortError(error)) {
      throw new ApiError({ kind: signal?.aborted ? 'aborted' : 'timeout', url })
    }
    throw new ApiError({
      kind: 'network',
      url,
      detail: error instanceof Error ? error.message : String(error),
    })
  } finally {
    if (idleTimer) clearTimeout(idleTimer)
    signal?.removeEventListener('abort', forwardAbort)
  }
}