import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PokemonDetail } from '@/features/dex/api'

const detail: PokemonDetail = {
  dex_number: 906,
  name_en: 'sprigatito',
  name_zh: '新叶喵',
  name_ja: null,
  types: ['grass'],
  stats: { hp: 40, attack: 61, defense: 54, 'special-attack': 45, 'special-defense': 45, speed: 65 },
  total_stats: 310,
  abilities: [],
  evolution: {},
  moves: { default_version_group: null, version_groups: [] },
  genus_zh: '草猫宝可梦',
  genus_en: 'Grass Cat Pokémon',
  flavor_zh: '身体散发出的甜香会让周围的人陶醉。',
  flavor_en: 'The sweet scent its body gives off mesmerizes those around it.',
  flavor_zh_source: 'project',
  genus_zh_source: 'pokeapi',
  artwork_url: null,
  artwork_fallback_url: null,
  sprite_url: null,
  is_legendary: false,
  is_mythical: false,
  is_baby: false,
  gender_rate: 1,
  capture_rate: 45,
  base_happiness: 50,
  hatch_counter: 20,
  growth_rate: 'medium-slow',
  habitat: null,
  color: 'green',
  shape: 'quadruped',
  egg_groups: ['field', 'plant'],
  generation_introduced: 9,
  height_dm: 4,
  weight_hg: 41,
  prev: null,
  next: null,
  source: 'pokeapi',
  source_label: 'PokéAPI 同步',
  is_demo: false,
  synced_at: null,
}

vi.mock('@/features/dex/hooks', () => ({
  usePokemonDetail: () => ({ isPending: false, isError: false, data: detail, refetch: vi.fn() }),
}))

vi.mock('@/features/abilities/hooks', () => ({
  useSTierAbilityNames: () => ({ data: new Set<string>() }),
}))

vi.mock('@/features/doubles/hooks', () => ({
  useDoubles: () => ({
    isPending: false,
    isError: false,
    data: { dex_number: 906, formats: [], has_data: false },
    refetch: vi.fn(),
  }),
}))

const { PokemonDetailPage } = await import('@/pages/PokemonDetailPage')

describe('PokemonDetailPage 译文来源标注', () => {
  it('项目自译的中文描述会标注来源', () => {
    render(
      <MemoryRouter initialEntries={['/dex/906']}>
        <Routes>
          <Route path="/dex/:dexNumber" element={<PokemonDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText(/身体散发出的甜香/)).toBeInTheDocument()
    expect(screen.getByText(/项目自译/)).toBeInTheDocument()
  })

  it('特性链接带 slug 与 expand 参数，能精确定位到特性页', () => {
    detail.abilities = [
      {
        name: 'overgrow',
        zh: '茂盛',
        is_hidden: false,
        effect_zh: '体力减少时草属性招式变强。',
        effect_en: null,
        tier: 'normal',
        is_s_tier: false,
      },
    ]
    render(
      <MemoryRouter initialEntries={['/dex/906']}>
        <Routes>
          <Route path="/dex/:dexNumber" element={<PokemonDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '茂盛' })).toHaveAttribute(
      'href',
      '/abilities?q=overgrow&expand=overgrow',
    )
  })
})
