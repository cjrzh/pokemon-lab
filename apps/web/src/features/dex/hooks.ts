/**
 * 图鉴数据 hooks：TanStack Query 封装。
 *
 * 搜索防抖在 hooks 内完成（useDeferredValue 不适合异步请求，自实现 300ms 防抖），
 * 页面组件只管消费 query 状态，四态（加载/空/错/过期）由组件层渲染。
 */

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  fetchPokemonDetail,
  fetchPokemonList,
  type PokemonListParams,
} from './api'

export const pokemonListKey = (params: PokemonListParams) =>
  ['pokemon', 'list', params] as const

export const pokemonDetailKey = (dexNumber: number) =>
  ['pokemon', 'detail', dexNumber] as const

/** 300ms 防抖：搜索输入连续变化只在停顿后触发请求。 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}

export function usePokemonList(params: PokemonListParams) {
  return useQuery({
    queryKey: pokemonListKey(params),
    queryFn: ({ signal }) => fetchPokemonList(params, signal),
    staleTime: 60_000,
    placeholderData: (previous) => previous, // 翻页/筛选时保留旧数据避免闪烁
  })
}

export function usePokemonDetail(dexNumber: number) {
  return useQuery({
    queryKey: pokemonDetailKey(dexNumber),
    queryFn: ({ signal }) => fetchPokemonDetail(dexNumber, signal),
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
