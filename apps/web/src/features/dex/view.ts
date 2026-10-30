/**
 * 图鉴页的视图偏好：卡片 / 列表，以及卡片密度（决定一屏能放多少只）。
 *
 * 纯函数集中在这里，页面只负责渲染；偏好写入 localStorage，
 * 非法值一律回落到默认值（用户手改存储不会让页面崩）。
 */

export type DexView = 'card' | 'list'
export type DexDensity = 'compact' | 'normal' | 'large'

/**
 * 列表排序。编号与种族值合计各支持升降序；后端在筛选之后排序
 * （见 list_pokemon），所以属性 / 世代 / 搜索的结果子集会被整体重排。
 */
export type DexSort = 'dex' | 'dex_desc' | 'total_stats' | 'total_stats_asc'

export const DEFAULT_SORT: DexSort = 'dex'

export const SORT_LABEL: Record<DexSort, string> = {
  dex: '编号 · 升序',
  dex_desc: '编号 · 降序',
  total_stats: '种族值 · 高到低',
  total_stats_asc: '种族值 · 低到高',
}

export function isDexSort(value: unknown): value is DexSort {
  return value === 'dex' || value === 'dex_desc' || value === 'total_stats' || value === 'total_stats_asc'
}

/**
 * 表头点击后的下一档排序：点「编号」在升 / 降序之间切换，
 * 点「合计」在种族值降 / 升序之间切换；从其他排序切到该列时先给常用方向
 * （编号升序、种族值降序）。
 */
export function nextSort(current: DexSort, column: 'dex' | 'total_stats'): DexSort {
  if (column === 'dex') {
    return current === 'dex' ? 'dex_desc' : 'dex'
  }
  return current === 'total_stats' ? 'total_stats_asc' : 'total_stats'
}

export const DEFAULT_VIEW: DexView = 'card'
export const DEFAULT_DENSITY: DexDensity = 'normal'

export const DENSITY_LABEL: Record<DexDensity, string> = {
  compact: '紧凑',
  normal: '标准',
  large: '大图',
}

/**
 * 卡片网格列数。紧凑模式在宽屏最多 8 列，一屏可看约 48 只；
 * 大图模式放大立绘，适合逐只看。
 */
export const GRID_CLASSES: Record<DexDensity, string> = {
  compact: 'grid-cols-3 sm:grid-cols-5 md:grid-cols-6 xl:grid-cols-8',
  normal: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5',
  large: 'grid-cols-2 sm:grid-cols-2 lg:grid-cols-3',
}

export function isDexView(value: unknown): value is DexView {
  return value === 'card' || value === 'list'
}

export function isDexDensity(value: unknown): value is DexDensity {
  return value === 'compact' || value === 'normal' || value === 'large'
}

/** 密度顺序：紧凑 → 标准 → 大图。 */
const DENSITY_ORDER: DexDensity[] = ['compact', 'normal', 'large']

/** 放大 / 缩小一档；到边界时保持不变。 */
export function shiftDensity(current: DexDensity, step: 1 | -1): DexDensity {
  const index = DENSITY_ORDER.indexOf(current)
  const next = Math.min(DENSITY_ORDER.length - 1, Math.max(0, index + step))
  return DENSITY_ORDER[next]
}

/** 列表模式可选的每页条数（后端上限 200）。 */
export const LIST_PAGE_SIZES = [25, 50, 100, 200] as const
export type ListPageSize = (typeof LIST_PAGE_SIZES)[number]
export const DEFAULT_LIST_PAGE_SIZE: ListPageSize = 50

export function isListPageSize(value: unknown): value is ListPageSize {
  return (LIST_PAGE_SIZES as readonly unknown[]).includes(value)
}

/**
 * 每页条数：
 *   - 列表模式用用户选定的 25 / 50 / 100 / 200（一行一只）；
 *   - 卡片模式由密度决定：紧凑 48、标准 24、大图 18。
 * 调整视图时页码会重置到第 1 页，避免「最后一页只剩 2 条」。
 */
export function pageSizeFor(view: DexView, density: DexDensity, listSize: number): number {
  if (view === 'list') {
    return isListPageSize(listSize) ? listSize : DEFAULT_LIST_PAGE_SIZE
  }
  if (density === 'compact') return 48
  if (density === 'large') return 18
  return 24
}

export interface DexPrefs {
  view: DexView
  density: DexDensity
  /** 列表模式每页条数；卡片模式不使用。 */
  listSize: ListPageSize
  /** 排序方式；卡片与列表模式共用。 */
  sort: DexSort
}

const STORAGE_KEY = 'pokemon-lab:dex-view'

export function defaultPrefs(): DexPrefs {
  return {
    view: DEFAULT_VIEW,
    density: DEFAULT_DENSITY,
    listSize: DEFAULT_LIST_PAGE_SIZE,
    sort: DEFAULT_SORT,
  }
}

export function parsePrefs(raw: string | null): DexPrefs {
  if (!raw) return defaultPrefs()
  try {
    const parsed: unknown = JSON.parse(raw)
    if (parsed === null || typeof parsed !== 'object') {
      return defaultPrefs()
    }
    const record = parsed as Record<string, unknown>
    return {
      view: isDexView(record.view) ? record.view : DEFAULT_VIEW,
      density: isDexDensity(record.density) ? record.density : DEFAULT_DENSITY,
      listSize: isListPageSize(record.listSize) ? record.listSize : DEFAULT_LIST_PAGE_SIZE,
      sort: isDexSort(record.sort) ? record.sort : DEFAULT_SORT,
    }
  } catch {
    return defaultPrefs()
  }
}

export function loadPrefs(): DexPrefs {
  if (typeof window === 'undefined') {
    return defaultPrefs()
  }
  try {
    return parsePrefs(window.localStorage.getItem(STORAGE_KEY))
  } catch {
    // 隐私模式 / 存储被禁用：用默认值，不影响浏览
    return defaultPrefs()
  }
}

export function savePrefs(prefs: DexPrefs): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  } catch {
    // 写不进去就算了，本次会话内仍然生效
  }
}
