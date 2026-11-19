/**
 * 建队候选目录：道具下拉框的数据来源。
 *
 * 两处来源用途不同：
 *   - `useTeamMemberOptions`（单个宝可梦）给的是「该格式统计里出现过的道具」，
 *     按使用率降序 —— 建队时的首选，直接带图标；
 *   - `useItemCatalog`（道具百科全量）作为兜底，让用户能选统计里没出现的道具
 *     （冷门配置、队友配合道具），并可手输英文名。
 */

import { useQuery } from '@tanstack/react-query'

import { fetchItemList, type ItemListResponse, type ItemSummary } from '@/features/items/api'

/** 后端单页上限是 200，道具表目前约 260 条，所以按页取完。 */
const PAGE_SIZE = 200
const MAX_PAGES = 5

export const itemCatalogKey = () => ['teams', 'item-catalog'] as const

async function fetchAllItems(signal?: AbortSignal): Promise<ItemSummary[]> {
  const items: ItemSummary[] = []
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const data: ItemListResponse = await fetchItemList(
      { page, page_size: PAGE_SIZE },
      signal,
    )
    items.push(...data.items)
    if (page >= data.meta.total_pages || data.items.length === 0) break
  }
  return items
}

/** 一次拉全量道具，供建队下拉框本地筛选。 */
export function useItemCatalog() {
  return useQuery({
    queryKey: itemCatalogKey(),
    queryFn: ({ signal }) => fetchAllItems(signal),
    staleTime: 30 * 60_000,
  })
}

/** 中文名 / 英文名 / slug 任一命中即算匹配（大小写不敏感）。 */
export function itemMatchesQuery(
  item: Pick<ItemSummary, 'name' | 'name_en' | 'zh'>,
  term: string,
): boolean {
  const needle = term.trim().toLowerCase()
  if (!needle) return true
  return [item.zh, item.name_en, item.name]
    .filter((value): value is string => Boolean(value))
    .some((value) => value.toLowerCase().includes(needle))
}
