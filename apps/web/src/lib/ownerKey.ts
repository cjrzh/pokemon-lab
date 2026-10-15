/**
 * 匿名所有者标识（Owner Key）
 *
 * MVP 阶段不做登录：首次访问时在 localStorage 生成一个 UUID，之后所有请求通过
 * `X-Owner-Key` 头带上它，后端据此隔离「收藏 / 笔记 / 考试成绩」等个人数据。
 *
 * 边界（明确写入 README，避免误以为是账号系统）：
 *   - 数据只归属「当前浏览器」；清理浏览器数据或更换设备会得到一个新的空白身份。
 *   - 该标识不是凭证，不具备防伪造能力，仅用于单机个人数据的归属区分。
 *   - 后续接入真实账号体系时，只需替换本模块与后端依赖注入中的取 key 逻辑。
 */

const STORAGE_KEY = 'pokemon-lab:owner-key'

export const OWNER_KEY_HEADER = 'X-Owner-Key'

let cachedOwnerKey: string | null = null

/** localStorage 在隐私模式 / 禁用 Cookie 时可能抛异常，统一探测并降级为内存存储。 */
function safeStorage(): Storage | null {
  try {
    const storage = window.localStorage
    const probeKey = '__pokemon_lab_probe__'
    storage.setItem(probeKey, '1')
    storage.removeItem(probeKey)
    return storage
  } catch {
    return null
  }
}

function createOwnerKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // 退化实现：仅在缺少 crypto.randomUUID 的旧环境中使用
  const random = Math.random().toString(36).slice(2, 10)
  return `owner-${Date.now().toString(36)}-${random}`
}

/** 读取当前所有者标识；不存在时生成并持久化。 */
export function getOwnerKey(): string {
  if (cachedOwnerKey) {
    return cachedOwnerKey
  }

  const storage = safeStorage()
  const stored = storage?.getItem(STORAGE_KEY)

  if (stored && stored.trim().length > 0) {
    cachedOwnerKey = stored
    return stored
  }

  const created = createOwnerKey()
  storage?.setItem(STORAGE_KEY, created)
  cachedOwnerKey = created
  return created
}

/** 生成新的所有者标识（用于「重置本机数据归属」这类显式操作）。 */
export function regenerateOwnerKey(): string {
  const created = createOwnerKey()
  safeStorage()?.setItem(STORAGE_KEY, created)
  cachedOwnerKey = created
  return created
}

/** 仅供测试使用：清除模块级缓存，避免用例之间互相影响。 */
export function resetOwnerKeyCache(): void {
  cachedOwnerKey = null
}