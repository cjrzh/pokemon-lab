/**
 * 携带道具选择器。
 *
 * 候选取两处的并集，去重后按使用率降序：
 *   1. `/pokemon/{dex}/team-options` 的 `legal_items` —— 该格式统计里这只宝可梦
 *      实际用过的道具，带使用率与图标，是首选；
 *   2. 道具百科全量列表（`item_ref`）—— 兜底，让用户能选统计里没出现的道具。
 *
 * 值统一存 Showdown 英文名（`Life Orb`），与导出格式一致；展示时优先中文名。
 * 输入框可当普通文本框用：找不到的道具也能直接手输英文名。
 */

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, Search, X } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { ItemIcon } from '@/features/dex/components/ItemIcon'
import { resolveMediaUrl } from '@/features/dex/api'
import { itemMatchesQuery, useItemCatalog } from '@/features/teams/catalog'
import type { TeamOptionUsage } from '@/features/teams/api'
import { cn } from '@/lib/utils'

/** 下拉框里的一行（已归一成「值 + 展示名 + 图标」）。 */
interface ItemOption {
  value: string
  label: string
  iconUrl: string | null
  pct: number | null
}

export function ItemPicker({
  value,
  onChange,
  suggestions,
  conflict,
}: {
  value: string | null
  onChange: (next: string | null) => void
  /** 统计推荐（带使用率与图标），排在候选最前。 */
  suggestions: TeamOptionUsage[]
  /** 与队友重复时为 true，边框标红。 */
  conflict?: boolean
}) {
  const listboxId = useId()
  const containerRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const catalog = useItemCatalog()

  const options = useMemo<ItemOption[]>(() => {
    const seen = new Map<string, ItemOption>()
    // 统计里的道具优先（有使用率与图标）
    for (const item of suggestions) {
      const optionValue = item.name_en ?? item.name
      seen.set(optionValue, {
        value: optionValue,
        label: item.name,
        iconUrl: item.icon_url ?? null,
        pct: item.pct,
      })
    }
    for (const item of catalog.data ?? []) {
      const optionValue = item.name_en ?? item.name
      if (seen.has(optionValue)) continue
      seen.set(optionValue, {
        value: optionValue,
        label: item.zh ?? item.name_en ?? item.name,
        iconUrl: item.icon_url,
        pct: null,
      })
    }
    return [...seen.values()]
  }, [suggestions, catalog.data])

  const filtered = useMemo(
    () =>
      options.filter((option) =>
        itemMatchesQuery(
          { name: option.value, name_en: option.value, zh: option.label },
          query,
        ),
      ),
    [options, query],
  )

  const byValue = useMemo(
    () => new Map(options.map((option) => [option.value, option])),
    [options],
  )
  const selected = value ? byValue.get(value) : undefined

  useEffect(() => {
    if (!open) return
    const handler = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const pick = (next: string | null) => {
    onChange(next)
    setQuery('')
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-label="道具"
        className={cn(
          'flex h-8 w-full items-center gap-1.5 rounded-md border bg-background px-2 text-left text-xs transition-colors',
          conflict ? 'border-destructive' : 'border-input hover:bg-muted/60',
        )}
      >
        {selected ? (
          <>
            <ItemIcon src={resolveMediaUrl(selected.iconUrl)} alt={selected.label} />
            <span className="min-w-0 flex-1 truncate">{selected.label}</span>
          </>
        ) : (
          <span className="min-w-0 flex-1 truncate text-muted-foreground">
            {value || '（不携带）'}
          </span>
        )}
        <ChevronDown
          aria-hidden="true"
          className={cn(
            'size-3.5 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>

      {open ? (
        <div className="absolute z-40 mt-1 w-full min-w-56 overflow-hidden rounded-lg border bg-popover shadow-lg">
          <div className="relative border-b">
            <Search
              aria-hidden="true"
              className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') setOpen(false)
                if (event.key === 'Enter') {
                  event.preventDefault()
                  const picked = filtered[0]
                  if (query.trim() && !picked) pick(query.trim())
                  else if (picked) pick(picked.value)
                }
              }}
              placeholder="搜索道具（中文名 / 英文名）…"
              className="h-8 rounded-none border-0 pl-7 text-xs shadow-none focus-visible:ring-0"
              aria-label="搜索道具"
              autoFocus
            />
          </div>

          <ul id={listboxId} role="listbox" aria-label="道具候选" className="max-h-56 overflow-auto py-1">
            {value ? (
              <li>
                <button
                  type="button"
                  onClick={() => pick(null)}
                  className="flex w-full items-center gap-1.5 px-2.5 py-1 text-left text-xs text-muted-foreground hover:bg-muted"
                >
                  <X aria-hidden="true" className="size-3.5" />
                  不携带道具
                </button>
              </li>
            ) : null}
            {filtered.length === 0 ? (
              <li className="px-2.5 py-1.5 text-[11px] text-muted-foreground">
                没有匹配的道具 —— 直接回车可手输这个英文名。
              </li>
            ) : (
              filtered.slice(0, 60).map((option) => (
                <li key={option.value} role="option" aria-selected={option.value === value}>
                  <button
                    type="button"
                    onClick={() => pick(option.value)}
                    className={cn(
                      'flex w-full items-center gap-1.5 px-2.5 py-1 text-left text-xs transition-colors',
                      option.value === value ? 'bg-primary/10 font-medium' : 'hover:bg-muted',
                    )}
                  >
                    <ItemIcon src={resolveMediaUrl(option.iconUrl)} alt={option.label} />
                    <span className="min-w-0 flex-1 truncate">{option.label}</span>
                    {option.pct != null ? (
                      <span className="shrink-0 text-[9px] text-muted-foreground tabular-nums">
                        {option.pct.toFixed(1)}%
                      </span>
                    ) : null}
                    {option.value === value ? (
                      <Check aria-hidden="true" className="size-3.5 shrink-0 text-primary" />
                    ) : null}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
