import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  OWNER_KEY_HEADER,
  getOwnerKey,
  regenerateOwnerKey,
  resetOwnerKeyCache,
} from './ownerKey'

const STORAGE_KEY = 'pokemon-lab:owner-key'

describe('ownerKey', () => {
  beforeEach(() => {
    window.localStorage.clear()
    resetOwnerKeyCache()
  })

  it('首次调用生成标识并持久化到 localStorage', () => {
    const key = getOwnerKey()

    expect(key).toBeTruthy()
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(key)
  })

  it('同一会话内重复调用返回同一个值', () => {
    expect(getOwnerKey()).toBe(getOwnerKey())
  })

  it('已存在持久化值时直接复用，不覆盖', () => {
    window.localStorage.setItem(STORAGE_KEY, 'existing-key')

    expect(getOwnerKey()).toBe('existing-key')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('existing-key')
  })

  it('持久化值为空白字符串时视为无效并重新生成', () => {
    window.localStorage.setItem(STORAGE_KEY, '   ')

    const key = getOwnerKey()

    expect(key.trim()).not.toBe('')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(key)
  })

  it('localStorage 不可写时降级为内存值且不抛异常', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })

    expect(() => getOwnerKey()).not.toThrow()
    expect(getOwnerKey()).toBeTruthy()
  })

  it('regenerateOwnerKey 生成不同的新值并写回存储', () => {
    const first = getOwnerKey()
    const second = regenerateOwnerKey()

    expect(second).not.toBe(first)
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(second)
    expect(getOwnerKey()).toBe(second)
  })

  it('请求头常量与后端约定保持一致', () => {
    expect(OWNER_KEY_HEADER).toBe('X-Owner-Key')
  })
})