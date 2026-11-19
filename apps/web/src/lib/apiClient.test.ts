import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiRequest, describeApiError, streamSse } from './apiClient'

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

/** 构造一个「永不 resolve，但会在 signal 中止时 reject AbortError」的 fetch，用于测试超时与取消。 */
function hangingFetch() {
  return vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => {
        const error = new Error('The operation was aborted.')
        error.name = 'AbortError'
        reject(error)
      })
    })
  })
}

describe('apiRequest', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('成功时解析 JSON，且不注入身份请求头', async () => {
    let capturedHeaders: HeadersInit | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        capturedHeaders = init?.headers
        return jsonResponse({ status: 'ok', checks: [] })
      }),
    )

    const result = await apiRequest<{ status: string }>('/health')

    expect(result).toEqual({ status: 'ok', checks: [] })
    // 个人项目不做浏览器隔离：请求不带 X-Owner-Key
    expect(capturedHeaders).not.toHaveProperty('X-Owner-Key')
  })

  it('204 无内容时返回 undefined', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))

    await expect(apiRequest('/collection/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('4xx 抛出 ApiError，kind=http，提取 FastAPI 的 detail，且不可重试', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ detail: '宝可梦不存在' }, { status: 404 })),
    )

    const error = await apiRequest('/pokemon/99999').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ kind: 'http', status: 404, retryable: false })
    expect((error as ApiError).message).toContain('宝可梦不存在')
  })

  it('5xx 标记为可重试', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'upstream' }, { status: 503 })))

    const error = await apiRequest('/pokemon').catch((caught: unknown) => caught)

    expect(error).toMatchObject({ kind: 'http', status: 503, retryable: true })
  })

  it('响应不是 JSON 时抛出 kind=parse', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<html>oops</html>', { status: 200 })),
    )

    await expect(apiRequest('/health')).rejects.toMatchObject({ kind: 'parse' })
  })

  it('超过 timeoutMs 抛出 kind=timeout', async () => {
    vi.stubGlobal('fetch', hangingFetch())

    await expect(apiRequest('/health', { timeoutMs: 20 })).rejects.toMatchObject({
      kind: 'timeout',
    })
  })

  it('外部 signal 主动取消时抛出 kind=aborted', async () => {
    vi.stubGlobal('fetch', hangingFetch())
    const controller = new AbortController()

    const pending = apiRequest('/health', { timeoutMs: 5_000, signal: controller.signal })
    controller.abort()

    await expect(pending).rejects.toMatchObject({ kind: 'aborted' })
  })

  it('网络异常（fetch reject 非 AbortError）归类为 kind=network', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    await expect(apiRequest('/health')).rejects.toMatchObject({
      kind: 'network',
      retryable: true,
    })
  })
})

describe('describeApiError', () => {
  it('ApiError 返回其 message', () => {
    const error = new ApiError({ kind: 'timeout', url: '/health' })
    expect(describeApiError(error)).toBe(error.message)
  })

  it('普通 Error 返回其 message', () => {
    expect(describeApiError(new Error('boom'))).toBe('boom')
  })

  it('非 Error 值返回兜底文案', () => {
    expect(describeApiError('boom')).toBe('发生未知错误')
    expect(describeApiError(null)).toBe('发生未知错误')
  })
})
describe('streamSse', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /** 造一个按块吐字节的 ReadableStream，模拟 SSE 分片到达。 */
  function sseResponse(chunks: string[], init?: ResponseInit): Response {
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk))
        }
        controller.close()
      },
    })
    return new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      ...init,
    })
  }

  it('逐条解析 data 事件，跨块分片也能正确拼回', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse([
          'data: {"event": "coverage", "data": {}}\n\n',
          // 一个事件被拆到两个块里
          'data: {"event": "del',
          'ta", "text": "你好"}\n\n',
          'data: {"event": "done", "text": "你好"}\n\n',
        ]),
      ),
    )

    const events: Record<string, unknown>[] = []
    await streamSse('/teams/analyze/stream', (event) => events.push(event), {
      body: { members: [] },
    })

    expect(events.map((event) => event.event)).toEqual(['coverage', 'delta', 'done'])
    expect(events[1].text).toBe('你好')
  })

  it('忽略非 data 行与无法解析的帧', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse([
          ': keep-alive\n\n',
          'data: not-json\n\n',
          'data: {"event": "done", "text": ""}\n\n',
        ]),
      ),
    )

    const events: Record<string, unknown>[] = []
    await streamSse('/x', (event) => events.push(event))

    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('done')
  })

  it('HTTP 错误抛出 ApiError（kind=http）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ detail: '队伍不存在' }), { status: 404 })),
    )

    await expect(streamSse('/x', () => {})).rejects.toMatchObject({
      kind: 'http',
      status: 404,
    })
  })
})
