/**
 * 图鉴详情页顶部的宝可梦搜索栏。
 *
 * 用途：浏览详情时不用先返回列表页，直接换个宝可梦继续看。
 * 交互：
 *   - 输入中文名 / 英文名 / 图鉴编号，300ms 防抖后请求 `/pokemon?q=…`；
 *   - 结果下拉显示小图标、中英文名、属性与编号，点击或回车跳转；
 *   - ↑ / ↓ 选择、Enter 打开第一条、Esc 收起。
 *
 * 空输入不发起请求（`usePokemonList` 的 `enabled=false`），避免每次进详情页都多一次查询。
 */

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { useDebouncedValue, usePokemonList } from '@/features/dex/hooks'
import { cn } from '@/lib/utils'

const RESULT_LIMIT = 8

export function PokemonSearchBar({ currentDex }: { currentDex?: number }) {
  const navigate = useNavigate()
  const listboxId = useId()
  const containerRef = useRef<HTMLDivElement>(null)

  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  const debounced = useDebouncedValue(query, 300)
  const term = debounced.trim()
  const list = usePokemonList(
    { page: 1, page_size: RESULT_LIMIT, q: term || undefined },
    { enabled: term.length > 0 },
  )

  const results = useMemo(
    () => (term ? (list.data?.items ?? []).filter((p) => p.dex_number !== currentDex) : []),
    [term, list.data, currentDex],
  )

  // 查询变化后重置高亮项，避免索引越界。
  // 用「渲染期根据上一次的 term 调整」而不是 effect：与 AbilitiesPage 同一写法，
  // 避免先渲染一次旧索引、再触发一轮多余渲染。
  const [syncedTerm, setSyncedTerm] = useState(term)
  if (syncedTerm !== term) {
    setSyncedTerm(term)
    setActive(0)
  }

  // 点击组件外部时收起下拉
  useEffect(() => {
    if (!open) return
    const handler = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const close = () => {
    setOpen(false)
    setActive(0)
  }

  const go = (dexNumber: number) => {
    close()
    setQuery('')
    navigate(`/dex/${dexNumber}`)
  }

  const showPanel = open && term.length > 0

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Search
          aria-hidden="true"
          className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              close()
              return
            }
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              if (results.length) setActive((index) => (index + 1) % results.length)
              return
            }
            if (event.key === 'ArrowUp') {
              event.preventDefault()
              if (results.length)
                setActive((index) => (index - 1 + results.length) % results.length)
              return
            }
            if (event.key === 'Enter') {
              event.preventDefault()
              const picked = results[active] ?? results[0]
              if (picked) go(picked.dex_number)
            }
          }}
          placeholder="搜索宝可梦（中文名 / 英文名 / 编号），随时切换…"
          className="h-9 pr-8 pl-8"
          aria-label="搜索宝可梦"
          role="combobox"
          aria-expanded={showPanel}
          aria-controls={listboxId}
          aria-autocomplete="list"
        />
        {query ? (
          <button
            type="button"
            onClick={() => {
              setQuery('')
              close()
            }}
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="清空搜索"
          >
            <X aria-hidden="true" className="size-3.5" />
          </button>
        ) : null}
      </div>

      {showPanel ? (
          <div
            className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border bg-popover shadow-lg"
            // 点击结果时 mousedown 会先于 click 触发；这里不阻止默认行为，
            // 让按钮的 onClick 正常执行（阻止默认在部分浏览器会让后续 click 丢失）。
          >
          {list.isPending && results.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">搜索中…</p>
          ) : list.isError ? (
            <p className="px-3 py-2 text-xs text-destructive">搜索失败，请稍后再试。</p>
          ) : results.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">
              没有匹配的宝可梦 —— 试试中文名、英文名或图鉴编号。
            </p>
          ) : (
            <ul id={listboxId} role="listbox" aria-label="宝可梦搜索结果">
              {results.map((pokemon, index) => {
                const name = pokemon.name_zh ?? pokemon.name_en
                return (
                  <li key={pokemon.dex_number} role="option" aria-selected={index === active}>
                    <button
                      type="button"
                      onClick={() => go(pokemon.dex_number)}
                      onMouseEnter={() => setActive(index)}
                      className={cn(
                        'flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors',
                        index === active ? 'bg-muted' : 'hover:bg-muted/60',
                      )}
                    >
                      <PokemonSprite
                        src={resolveMediaUrl(pokemon.sprite_url)}
                        alt={name}
                        type={pokemon.types[0]}
                        className="size-6"
                      />
                      <span className="w-11 shrink-0 text-[10px] text-muted-foreground tabular-nums">
                        #{String(pokemon.dex_number).padStart(4, '0')}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-xs">
                        <span className="font-medium">{name}</span>
                        {pokemon.name_zh ? (
                          <span className="ml-1.5 text-[10px] text-muted-foreground">
                            {pokemon.name_en}
                          </span>
                        ) : null}
                      </span>
                      <span className="flex shrink-0 gap-0.5">
                        {pokemon.types.map((type) => (
                          <TypeBadge key={type} type={type} className="px-1 py-0 text-[9px]" />
                        ))}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}
