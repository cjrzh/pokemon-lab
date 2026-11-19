/**
 * 图鉴数据 hooks：TanStack Query 封装。
 *
 * 搜索防抖在 hooks 内完成（useDeferredValue 不适合异步请求，自实现 300ms 防抖），
 * 页面组件只管消费 query 状态，四态（加载/空/错/过期）由组件层渲染。
 */

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  DEFAULT_FORM_NAME,
  fetchPokemonDetail,
  fetchPokemonForm,
  fetchPokemonList,
  type PokemonListParams,
} from './api'

export const pokemonListKey = (params: PokemonListParams) =>
  ['pokemon', 'list', params] as const

export const pokemonDetailKey = (dexNumber: number) =>
  ['pokemon', 'detail', dexNumber] as const

export const pokemonFormKey = (dexNumber: number, formName: string) =>
  ['pokemon', 'form', dexNumber, formName] as const

/** 300ms 防抖：搜索输入连续变化只在停顿后触发请求。 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}

/**
 * @param options.enabled 为 false 时不发请求（如详情页搜索栏在空输入时）。
 *                        仍保留上一次成功的数据，避免下拉内容闪空。
 */
export function usePokemonList(
  params: PokemonListParams,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: pokemonListKey(params),
    queryFn: ({ signal }) => fetchPokemonList(params, signal),
    staleTime: 60_000,
    placeholderData: (previous) => previous, // 翻页/筛选时保留旧数据避免闪烁
    enabled: options.enabled ?? true,
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

/**
 * 非默认形态的详情。默认形态不调用它（直接用 `usePokemonDetail` 的数据），
 * 避免进详情页时多一次无意义请求。
 */
export function usePokemonForm(dexNumber: number, formName: string | null) {
  const enabled = Boolean(formName) && formName !== DEFAULT_FORM_NAME
  return useQuery({
    queryKey: pokemonFormKey(dexNumber, formName ?? ''),
    queryFn: ({ signal }) => fetchPokemonForm(dexNumber, formName as string, signal),
    enabled: Number.isInteger(dexNumber) && dexNumber > 0 && enabled,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
