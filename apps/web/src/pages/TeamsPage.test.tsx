/**
 * 建队页测试：队伍列表、新建、成员编辑（招式上限 / 推荐套用 / 道具重复提示）与保存校验。
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { TeamDetail, TeamListResponse, TeamMemberOptions } from '@/features/teams/api'

const formats = [
  {
    key: 'sv',
    label: '朱紫 · VGC',
    short_label: '朱紫',
    points_kind: 'ev' as const,
    trade_prefix: '!tradeSV',
    default_level: 50,
    month: '2026-04',
    cutoff: 1630,
  },
]

const list: TeamListResponse = {
  items: [
    {
      id: 3,
      name: '已有队伍',
      format_key: 'sv',
      format_label: '朱紫 · VGC',
      note: null,
      member_count: 2,
      updated_at: '2026-11-01T00:00:00',
    },
    {
      id: 4,
      name: '剑盾队伍',
      format_key: 'swsh',
      format_label: '剑盾 · VGC',
      note: null,
      member_count: 1,
      updated_at: '2026-11-01T00:00:00',
    },
  ],
  formats: [
    ...formats,
    {
      key: 'swsh',
      label: '剑盾 · VGC',
      short_label: '剑盾',
      points_kind: 'ev' as const,
      trade_prefix: '!tradeSWSH',
      default_level: 50,
      month: '2026-04',
      cutoff: 1630,
    },
  ],
}

const options: TeamMemberOptions = {
  dex_number: 6,
  showdown_name: 'Charizard',
  name_zh: '喷火龙',
  name_en: 'charizard',
  types: ['fire', 'flying'],
  artwork_url: null,
  sprite_url: '/media/sprites/6.png',
  gender_rate: 1,
  form: null,
  forms: [],
  legal_moves: [
    { slug: 'flamethrower', name: '喷射火焰', name_en: 'Flamethrower', type: 'fire', pct: 0 },
    { slug: 'air-slash', name: '空气斩', name_en: 'Air Slash', type: 'flying', pct: 0 },
    { slug: 'protect', name: '守住', name_en: 'Protect', type: 'normal', pct: 0 },
    { slug: 'roost', name: '羽栖', name_en: 'Roost', type: 'flying', pct: 0 },
    { slug: 'dragon-pulse', name: '龙之波动', name_en: 'Dragon Pulse', type: 'dragon', pct: 0 },
  ],
  legal_abilities: [
    { slug: 'blaze', name: '猛火', name_en: 'Blaze', pct: 0 },
    { slug: 'solar-power', name: '太阳之力', name_en: 'Solar Power', pct: 0 },
  ],
  legal_items: [
    {
      slug: 'life-orb',
      name: '生命宝珠',
      name_en: 'Life Orb',
      pct: 60,
      icon_url: '/media/items/life-orb.png',
    },
  ],
  recommended: {
    showdown_name: 'Charizard',
    rank: 10,
    usage: 12.5,
    abilities: [{ slug: 'solar-power', name: '太阳之力', name_en: 'Solar Power', pct: 96.3 }],
    items: [
      {
        slug: 'life-orb',
        name: '生命宝珠',
        name_en: 'Life Orb',
        pct: 60,
        icon_url: '/media/items/life-orb.png',
      },
    ],
    moves: [
      { slug: 'flamethrower', name: '喷射火焰', name_en: 'Flamethrower', type: 'fire', pct: 80 },
      { slug: 'air-slash', name: '空气斩', name_en: 'Air Slash', type: 'flying', pct: 40 },
    ],
    spread: { nature: 'timid', nature_label: '胆小', points: [4, 0, 0, 252, 0, 252], pct: 30 },
    spreads: [],
  },
  has_stats: true,
  can_gigantamax: true,
  gigantamax_move: 'G-Max Wildfire',
  gigantamax: false,
}

/** 雷丘的建队选项（导入单只时用；招式含从前代继承的 Fake Out）。 */
const raichuOptions: TeamMemberOptions = {
  dex_number: 26,
  showdown_name: 'Raichu',
  name_zh: '雷丘',
  name_en: 'raichu',
  types: ['electric'],
  artwork_url: null,
  sprite_url: '/media/sprites/26.png',
  gender_rate: 4,
  form: null,
  forms: [],
  legal_moves: [
    { slug: 'fake-out', name: '击掌奇袭', name_en: 'Fake Out', type: 'normal', pct: 0 },
    { slug: 'encore', name: '再来一次', name_en: 'Encore', type: 'normal', pct: 0 },
    { slug: 'protect', name: '守住', name_en: 'Protect', type: 'normal', pct: 0 },
  ],
  legal_abilities: [
    { slug: 'static', name: '静电', name_en: 'Static', pct: 0 },
    { slug: 'lightning-rod', name: '避雷针', name_en: 'Lightning Rod', pct: 0 },
  ],
  legal_items: [],
  recommended: null,
  has_stats: false,
  can_gigantamax: false,
  gigantamax_move: null,
  gigantamax: false,
}

const state = vi.hoisted(() => ({
  created: [] as unknown[],
  validated: [] as unknown[],
  deleted: [] as number[],
  imported: [] as unknown[],
  batched: [] as unknown[],
  analyzed: [] as unknown[],
  reordered: [] as number[][],
  detail: null as TeamDetail | null,
}))

vi.mock('@/features/teams/hooks', () => ({
  useTeams: () => ({ isPending: false, isError: false, data: list }),
  useTeam: () => ({ isPending: false, isError: false, data: state.detail }),
  useTeamMemberOptions: (dex: number | null) => ({
    isPending: false,
    isError: false,
    data: dex === 26 ? raichuOptions : options,
  }),
  useCreateTeam: () => ({
    mutateAsync: async (payload: unknown) => {
      state.created.push(payload)
      return { id: 9, name: '新队伍', format_key: 'sv', members: [], member_count: 0 }
    },
    isPending: false,
  }),
  useUpdateTeam: () => ({ mutateAsync: async () => ({ id: 3 }), isPending: false }),
  useReorderTeams: () => ({
    mutate: (ids: number[]) => {
      state.reordered.push(ids)
    },
    isPending: false,
  }),
  useDeleteTeam: () => ({
    mutateAsync: async (id: number) => {
      state.deleted.push(id)
    },
    isPending: false,
  }),
  useValidateTeam: () => ({
    mutateAsync: async (payload: unknown) => {
      state.validated.push(payload)
      return { ok: true, issues: [], warnings: [] }
    },
    isPending: false,
  }),
  useBatchTeamMembers: () => ({
    mutateAsync: async (payload: unknown) => {
      state.batched.push(payload)
      return { members: [], skipped: [] }
    },
    isPending: false,
  }),
  useStreamTeamAnalysis: () => ({
    start: async (params: unknown) => {
      state.analyzed.push(params)
    },
    stop: () => {},
    running: false,
    coverage: null,
    text: '',
    model: null,
    llmError: null,
    error: null,
  }),
  useImportTeam: () => ({
    mutateAsync: async (payload: { text: string }) => {
      state.imported.push(payload)
      // 模拟后端：按文本里出现的物种名解析成成员，认不出的记问题
      const members: unknown[] = []
      if (payload.text.includes('Charizard')) {
        members.push({
          dex_number: 6,
          showdown_name: 'Charizard',
          item: 'Life Orb',
          ability: 'Blaze',
          nature: 'timid',
          evs: [4, 0, 0, 252, 0, 252],
          ivs: [31, 31, 31, 31, 31, 31],
          moves: ['Flamethrower'],
          tera_type: 'Fire',
          gender: 'F',
          shiny: true,
          level: null,
        })
      }
      if (payload.text.includes('Raichu')) {
        members.push({
          dex_number: 26,
          showdown_name: 'Raichu',
          item: 'Focus Sash',
          ability: 'Static',
          nature: 'timid',
          evs: [0, 0, 0, 252, 4, 252],
          ivs: null,
          moves: ['Fake Out', 'Encore'],
          tera_type: null,
          gender: null,
          shiny: false,
          level: null,
        })
      }
      const problems = payload.text.includes('Missingno')
        ? ['无法识别「Missingno」对应的图鉴编号，已跳过']
        : []
      return { format_key: 'sv', members, problems, warnings: [] }
    },
    isPending: false,
  }),
}))

/** 建队选择器的搜索目录（模拟后端 `GET /pokemon?q=…&prefix=true`）。 */
const catalog = [
  { dex_number: 6, name_en: 'charizard', name_zh: '喷火龙', types: ['fire', 'flying'] },
  { dex_number: 9, name_en: 'blastoise', name_zh: '水箭龟', types: ['water'] },
  { dex_number: 26, name_en: 'raichu', name_zh: '雷丘', types: ['electric'] },
]

vi.mock('@/features/dex/hooks', () => ({
  useDebouncedValue: (value: string) => value,
  usePokemonList: (params: { q?: string; enabled?: boolean }) => {
    const term = (params.q ?? '').trim().toLowerCase()
    const items = term
      ? catalog.filter(
          (item) =>
            item.name_zh.startsWith(term) ||
            item.name_en.startsWith(term) ||
            String(item.dex_number) === term,
        )
      : []
    return {
      isPending: false,
      isError: false,
      data: { items: items.map((item) => ({ ...item, sprite_url: null })), meta: null },
    }
  },
}))

/** 道具下拉框的全量目录（模拟道具百科；避免测试依赖 QueryClientProvider）。 */
vi.mock('@/features/teams/catalog', () => ({
  useItemCatalog: () => ({
    isPending: false,
    isError: false,
    data: [
      {
        name: 'leftovers',
        zh: '吃剩的东西',
        name_en: 'Leftovers',
        category: 'held-items',
        category_zh: '携带道具',
        effect_en: null,
        cost: null,
        icon_url: '/media/items/leftovers.png',
      },
    ],
  }),
  itemMatchesQuery: (
    item: { name: string; name_en?: string | null; zh?: string | null },
    term: string,
  ) => {
    const needle = term.trim().toLowerCase()
    if (!needle) return true
    return [item.zh, item.name_en, item.name]
      .filter((value): value is string => Boolean(value))
      .some((value) => value.toLowerCase().includes(needle))
  },
}))

const { TeamsPage } = await import('@/pages/TeamsPage')

function renderPage(initial = '/') {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <TeamsPage />
    </MemoryRouter>,
  )
}

/** 一支已保存的完整队伍（配置与推荐值一致）。 */
function savedTeam(): TeamDetail {
  return {
    id: 3,
    name: '已保存队',
    format_key: 'sv',
    format_label: '朱紫 · VGC',
    note: null,
    member_count: 1,
    updated_at: '2026-11-04T00:00:00',
    members: [
      {
        position: 0,
        dex_number: 6,
        showdown_name: 'Charizard',
        nickname: null,
        item: 'Life Orb',
        ability: 'Solar Power',
        nature: 'timid',
        evs: [4, 0, 0, 252, 0, 252],
        ivs: [31, 31, 31, 31, 31, 31],
        moves: ['Flamethrower', 'Air Slash'],
        tera_type: null,
        gender: 'F',
        shiny: false,
        level: null,
        language: 'CHS',
      },
    ],
    trade_prefix: '!tradeSV',
    default_level: 50,
    points_kind: 'ev',
    analysis: null,
  }
}

async function startNewTeam() {
  await userEvent.click(screen.getByRole('button', { name: /新建队伍/ }))
}

async function addCharizard() {
  await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), '喷火')
  await userEvent.click(screen.getByRole('button', { name: /加入队伍/ }))
}

beforeEach(() => {
  state.reordered = []
})

describe('TeamsPage', () => {
  it('列出已有队伍并显示版本与数量', () => {
    renderPage()

    expect(screen.getByText('已有队伍')).toBeInTheDocument()
    expect(screen.getByText(/朱紫 · VGC · 2 只/)).toBeInTheDocument()
  })

  it('新建队伍后可命名并加入宝可梦', async () => {
    renderPage()
    await startNewTeam()

    expect(screen.getByRole('textbox', { name: '队伍名称' })).toHaveValue('新队伍')

    await addCharizard()
    expect(screen.getByText('喷火龙')).toBeInTheDocument()
    expect(screen.getByText(/1\/6 只/)).toBeInTheDocument()
  })

  it('加入的宝可梦自动套用使用率推荐（特性 / 道具 / 招式 / 配点）', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    // 推荐：太阳之力（使用率最高）+ 生命宝珠 + 喷射火焰 / 空气斩 + 胆小 4/0/0/252/0/252
    expect(screen.getByLabelText('特性')).toHaveValue('Solar Power')
    expect(screen.getByLabelText('道具')).toHaveTextContent('生命宝珠')
    expect(screen.getByLabelText('性格')).toHaveValue('timid')
    expect(screen.getByLabelText('特攻 EV')).toHaveValue(252)
    expect(screen.getByRole('button', { name: /喷射火焰/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('特性下拉框列出全部合法特性，推荐项靠前并标注', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    const options = screen.getByLabelText('特性').querySelectorAll('option')
    // 使用率最高的排在第一个（猛火没有统计，按字母序排在后面）
    expect([...options].map((option) => option.textContent)).toEqual([
      '（不选）',
      '太阳之力 · 96.3%　★推荐',
      '猛火',
    ])
  })

  it('招式最多选 4 个', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    // 推荐已经预选了前两个（喷射火焰 / 空气斩），再补两个到 4 个
    for (const name of ['守住', '羽栖']) {
      await userEvent.click(screen.getByRole('button', { name: new RegExp(name) }))
    }
    // 第 5 个应被禁用
    expect(screen.getByRole('button', { name: /龙之波动/ })).toBeDisabled()
  })

  it('保存前校验并提交整队', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()
    await userEvent.click(screen.getByRole('button', { name: /^保存$/ }))

    expect(state.validated).toHaveLength(1)
    expect(state.created).toHaveLength(1)
    const payload = state.created[0] as { members: { dex_number: number }[] }
    expect(payload.members[0].dex_number).toBe(6)
  })

  it('重复编号会被拒绝加入', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()
    await addCharizard()

    expect(screen.getByText(/已经在队伍里/)).toBeInTheDocument()
  })

  it('支持中文名前缀搜索并点击加入', async () => {
    renderPage()
    await startNewTeam()

    await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), '喷火')
    await userEvent.click(await screen.findByRole('button', { name: /喷火龙/ }))

    expect(screen.getByText('喷火龙')).toBeInTheDocument()
    expect(screen.getByText(/1\/6 只/)).toBeInTheDocument()
  })

  it('搜索无结果时给出提示', async () => {
    renderPage()
    await startNewTeam()

    await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), '不存在的宝可梦')
    await userEvent.click(screen.getByRole('button', { name: /加入队伍/ }))

    expect(screen.getByText(/没有找到匹配的宝可梦/)).toBeInTheDocument()
  })

  it('已在队伍的宝可梦在下拉里标记出来', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), '喷火')

    expect(await screen.findByText('已在队伍')).toBeInTheDocument()
  })

  it('删除队伍调用接口', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: '删除 已有队伍' }))

    expect(state.deleted).toEqual([3])
  })

  it('按游戏版本筛选队伍列表', async () => {
    renderPage()
    // 默认「全部」：两个版本的队伍都在
    expect(screen.getByText('已有队伍')).toBeInTheDocument()
    expect(screen.getByText('剑盾队伍')).toBeInTheDocument()

    const filters = screen.getByRole('group', { name: '按版本筛选队伍' })
    await userEvent.click(within(filters).getByRole('button', { name: /剑盾/ }))
    expect(screen.queryByText('已有队伍')).not.toBeInTheDocument()
    expect(screen.getByText('剑盾队伍')).toBeInTheDocument()
  })

  it('每只宝可梦后面有一键复制 Showdown 代码的按钮（不带交易前缀）', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    renderPage()
    await startNewTeam()
    await addCharizard()

    const button = screen.getByRole('button', { name: '复制 喷火龙 的 Showdown 代码' })
    await userEvent.click(button)

    expect(writeText).toHaveBeenCalledTimes(1)
    const copied = writeText.mock.calls[0][0] as string
    // 建队页只复制队伍本体：没有 !trade 交易前缀行
    expect(copied).not.toContain('!trade')
    expect(copied.startsWith('Charizard')).toBe(true)
  })

  it('整队一键复制：只有队伍本体，不带交易前缀，每只之间空一行', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    renderPage()
    await startNewTeam()
    await addCharizard()

    await userEvent.click(screen.getByRole('button', { name: /复制整队 Showdown 代码/ }))

    expect(writeText).toHaveBeenCalledTimes(1)
    const copied = writeText.mock.calls[0][0] as string
    expect(copied).not.toContain('!trade')
    expect(copied.startsWith('Charizard')).toBe(true)
  })

  it('剑盾队伍的单只复制不带 Language 行', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    renderPage()
    await startNewTeam()
    await userEvent.selectOptions(screen.getByLabelText('队伍版本'), 'swsh')
    await addCharizard()

    await userEvent.click(
      screen.getByRole('button', { name: /复制 喷火龙 的 Showdown 代码/ }),
    )
    const copied = writeText.mock.calls[0][0] as string
    expect(copied).not.toContain('Language:')
  })

  it('打开了已保存队伍时，点一次「新建队伍」就切到空白草稿', async () => {
    state.detail = savedTeam()
    renderPage('/teams?team=3')
    expect(screen.getByRole('textbox', { name: '队伍名称' })).toHaveValue('已保存队')

    // 回归：旧实现点一次会先切到空白，随后被「打开队伍」的回填逻辑覆盖回去，
    // 用户必须点第二次才生效。
    await userEvent.click(screen.getByRole('button', { name: /新建队伍/ }))

    expect(screen.getByRole('textbox', { name: '队伍名称' })).toHaveValue('新队伍')
    expect(screen.queryByText('已保存队')).not.toBeInTheDocument()
  })

  it('打开已保存的队伍不会误报「有未保存改动」（自动填充推荐值不算改动）', async () => {
    state.detail = savedTeam()
    renderPage('/teams?team=3')

    expect(screen.getByRole('textbox', { name: '队伍名称' })).toHaveValue('已保存队')
    expect(screen.queryByText('有未保存改动')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '恢复' })).toBeDisabled()
  })

  it('改动后可以一键恢复到上次保存的状态', async () => {
    state.detail = savedTeam()
    renderPage('/teams?team=3')

    const name = screen.getByRole('textbox', { name: '队伍名称' })
    await userEvent.clear(name)
    await userEvent.type(name, '改过的名字')
    expect(screen.getByText('有未保存改动')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '恢复' }))
    expect(screen.getByRole('textbox', { name: '队伍名称' })).toHaveValue('已保存队')
    expect(screen.queryByText('有未保存改动')).not.toBeInTheDocument()
  })

  it('每只成员有拖动手柄与上下移动按钮', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()
    await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), '水箭龟')
    await userEvent.click(screen.getByRole('button', { name: /加入队伍/ }))

    // 两只成员各有一个拖动手柄
    // 队伍列表 2 个 + 成员 2 个
    expect(screen.getAllByLabelText(/调整顺序/)).toHaveLength(4)
    // 第一只不能上移，最后一只不能下移
    const ups = screen.getAllByRole('button', { name: '上移这一只' })
    const downs = screen.getAllByRole('button', { name: '下移这一只' })
    expect(ups[0]).toBeDisabled()
    expect(downs[downs.length - 1]).toBeDisabled()
  })

  it('上移 / 下移会改变成员顺序并反映到保存内容', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()
    await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), '水箭龟')
    await userEvent.click(screen.getByRole('button', { name: /加入队伍/ }))

    // 调试：看是否被重复拒绝
    expect(screen.queryByText(/已经在队伍里/)).not.toBeInTheDocument()
    expect(screen.getByText(/2\/6 只/)).toBeInTheDocument()
    // 初始顺序：喷火龙(6) → 水箭龟(9)；把第二只上移
    await userEvent.click(screen.getAllByRole('button', { name: '上移这一只' })[1])

    // 顺序断言用保存后的 content（mock 对所有 dex 都返回同一套选项，展示名不可靠）
    const handles = screen.getAllByLabelText(/调整顺序/)
    expect(handles).toHaveLength(4)

    expect(screen.getByText(/2\/6 只/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^保存$/ }))
    // state.created 跨用例累积，取最后一次
    const payload = state.created.at(-1) as {
      members: { dex_number: number; position: number }[]
    }
    expect(payload.members.map((m) => m.dex_number)).toEqual([9, 6])
  })

  it('搜索加入的宝可梦默认闪光、100 级、雌性', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    expect(screen.getByLabelText('闪光')).toHaveValue('yes')
    // 「等级」也匹配批量设置里的「批量等级」，用精确匹配
    expect(
      screen.getByLabelText((_, el) => el?.getAttribute('aria-label') === '等级'),
    ).toHaveValue(100)
    expect(screen.getByLabelText('性别')).toHaveValue('F')
  })

  it('EV 可以手动输入任意数字，超出范围时提示但不自动改写', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    const hp = screen.getByLabelText('HP EV')
    await userEvent.clear(hp)
    await userEvent.type(hp, '999')

    // 原样保留用户输入（不偷偷夹到 252）
    expect(hp).toHaveValue(999)
    expect(screen.getByText(/单项不能超过 252/)).toBeInTheDocument()
  })

  it('EV 合计超过 508 时给出提示', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    for (const [label, value] of [
      ['HP EV', '252'],
      ['攻击 EV', '252'],
      ['防御 EV', '8'],
    ] as const) {
      const input = screen.getByLabelText(label)
      await userEvent.clear(input)
      await userEvent.type(input, value)
    }

    expect(screen.getByText(/合计不能超过 508/)).toBeInTheDocument()
  })

  it('性格下拉标注增减效果，选中后显示 ▲▼', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    const nature = screen.getByLabelText('性格')
    // 下拉选项带效果说明
    expect(nature).toHaveTextContent(/固执（Adamant）\s*·\s*攻击 ↑ \/ 特攻 ↓/)
    await userEvent.selectOptions(nature, 'adamant')
    expect(screen.getByText('▲ 攻击')).toBeInTheDocument()
    expect(screen.getByText('▼ 特攻')).toBeInTheDocument()
  })

  it('成员编辑器可以选导出语言', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    const language = screen.getByLabelText('语言')
    expect(language).toHaveValue('CHS')
    await userEvent.selectOptions(language, 'ENG')
    expect(language).toHaveValue('ENG')
  })

  it('剑盾成员有极巨化等级，默认 10 并可保存', async () => {
    renderPage()
    await startNewTeam()
    // 切到剑盾
    await userEvent.selectOptions(screen.getByLabelText('队伍版本'), 'swsh')
    await addCharizard()

    const dynamax = screen.getByLabelText('极巨化等级')
    expect(dynamax).toHaveValue(10)

    await userEvent.clear(dynamax)
    await userEvent.type(dynamax, '7')
    await userEvent.click(screen.getByRole('button', { name: /^保存$/ }))

    const payload = state.created.at(-1) as { members: { dynamax_level: number | null }[] }
    expect(payload.members[0].dynamax_level).toBe(7)
  })

  it('朱紫队伍没有极巨化等级（朱紫没有极巨化）', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    expect(screen.queryByLabelText('极巨化等级')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('超极巨化')).not.toBeInTheDocument()
  })

  it('剑盾的喷火龙可以开启超极巨化并保存', async () => {
    renderPage()
    await startNewTeam()
    await userEvent.selectOptions(screen.getByLabelText('队伍版本'), 'swsh')
    await addCharizard()

    // 喷火龙有 G 形态：显示开关与 G 招式说明
    expect(screen.getByText('G-Max Wildfire')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('超极巨化'))
    await userEvent.click(screen.getByRole('button', { name: /^保存$/ }))

    const payload = state.created.at(-1) as {
      members: { gigantamax: boolean; dynamax_level: number | null }[]
    }
    expect(payload.members[0].gigantamax).toBe(true)
    expect(payload.members[0].dynamax_level).toBe(10)
  })

  it('没有 G 形态的剑盾成员：超极巨化开关禁用并说明', async () => {
    renderPage()
    await startNewTeam()
    await userEvent.selectOptions(screen.getByLabelText('队伍版本'), 'swsh')
    // 雷丘（#26）没有超极巨化形态
    await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), '雷丘')
    await userEvent.click(screen.getByRole('button', { name: /加入队伍/ }))

    // 两个参数都在页面上，只是无 G 形态时开关不可用
    expect(screen.getByLabelText('极巨化等级')).toBeInTheDocument()
    expect(screen.getByLabelText('超极巨化')).toBeDisabled()
    expect(screen.getByText('无 G 形态')).toBeInTheDocument()
  })
})

describe('TeamsPage 队伍列表排序', () => {
  it('每支队伍都有拖动手柄与上移 / 下移按钮', () => {
    renderPage()

    expect(screen.getByLabelText('拖动 已有队伍 调整顺序')).toBeInTheDocument()
    expect(screen.getByLabelText('拖动 剑盾队伍 调整顺序')).toBeInTheDocument()
  })

  it('上移队伍会提交完整的新顺序', async () => {
    renderPage()
    // 列表初始：已有队伍(3) → 剑盾队伍(4)
    await userEvent.click(screen.getByRole('button', { name: '上移 剑盾队伍' }))

    expect(state.reordered.at(-1)).toEqual([4, 3])
  })

  it('下移第一支队伍同样提交新顺序', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: '下移 已有队伍' }))

    expect(state.reordered.at(-1)).toEqual([4, 3])
  })

  it('第一支的上移与最后一支的下移禁用', () => {
    renderPage()

    expect(screen.getByRole('button', { name: '上移 已有队伍' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '下移 剑盾队伍' })).toBeDisabled()
  })

  it('筛选状态下排序只调整可见队伍，完整顺序仍然正确', async () => {
    renderPage()
    const filters = screen.getByRole('group', { name: '按版本筛选队伍' })
    // 只看队伍 3（朱紫）：此时唯一可见，上移禁用
    await userEvent.click(within(filters).getByRole('button', { name: /剑盾/ }))

    // 剑盾筛选下只有 id=4 一支
    expect(screen.queryByLabelText('拖动 已有队伍 调整顺序')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '上移 剑盾队伍' })).toBeDisabled()
  })
})

describe('TeamsPage 导入 Showdown 代码', () => {
  async function openImport() {
    await userEvent.click(screen.getByRole('button', { name: /导入代码/ }))
  }

  it('粘贴代码解析后把成员导入编辑器', async () => {
    renderPage()
    await startNewTeam()
    await openImport()

    await userEvent.type(
      screen.getByRole('textbox', { name: 'Showdown 队伍代码' }),
      'Charizard (F) @ Life Orb',
    )
    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))

    // 解析结果先展示识别到的成员，确认后才进编辑器
    expect(await screen.findByText(/识别到 1 只，可加入 1 只/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /加入队伍（1 只）/ }))

    expect(state.imported).toHaveLength(1)
    expect(screen.getByText('喷火龙')).toBeInTheDocument()
    expect(screen.getByText(/1\/6 只/)).toBeInTheDocument()
  })

  it('新建队伍可以单独导入一只宝可梦', async () => {
    renderPage()
    await startNewTeam()
    await openImport()

    await userEvent.type(
      screen.getByRole('textbox', { name: 'Showdown 队伍代码' }),
      'Raichu @ Focus Sash{enter}Ability: Static{enter}- Fake Out{enter}- Encore',
    )
    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))
    await userEvent.click(await screen.findByRole('button', { name: /加入队伍（1 只）/ }))

    // 请求文本原样送给后端；导入的一只进了编辑器并保留代码里的招式
    expect(state.imported.at(-1)).toMatchObject({
      text: 'Raichu @ Focus Sash\nAbility: Static\n- Fake Out\n- Encore',
    })
    expect(screen.getByText('雷丘')).toBeInTheDocument()
    expect(screen.getByText(/1\/6 只/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /击掌奇袭/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('导入追加到已有成员之后，不覆盖', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()
    await openImport()

    await userEvent.type(
      screen.getByRole('textbox', { name: 'Showdown 队伍代码' }),
      'Raichu @ Focus Sash',
    )
    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))
    await userEvent.click(await screen.findByRole('button', { name: /加入队伍（1 只）/ }))

    expect(screen.getByText(/2\/6 只/)).toBeInTheDocument()
    expect(screen.getByText(/已加入 1 只/)).toBeInTheDocument()
  })

  it('无法识别的条目列在提示里，仍能导入其余成员', async () => {
    renderPage()
    await startNewTeam()
    await openImport()

    await userEvent.type(
      screen.getByRole('textbox', { name: 'Showdown 队伍代码' }),
      'Charizard @ Life Orb{enter}{enter}Missingno',
    )
    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))

    expect(await screen.findByText(/Missingno.*已跳过/)).toBeInTheDocument()
    expect(screen.getByText(/部分条目被跳过/)).toBeInTheDocument()
  })

  it('解析不出任何宝可梦时给出错误提示', async () => {
    renderPage()
    await startNewTeam()
    await openImport()

    await userEvent.type(screen.getByRole('textbox', { name: 'Showdown 队伍代码' }), '??')
    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))

    expect(await screen.findByText(/没有解析出任何宝可梦/)).toBeInTheDocument()
  })

  it('解析前解析按钮不可点', async () => {
    renderPage()
    await startNewTeam()
    await openImport()

    expect(screen.getByRole('button', { name: /^解析$/ })).toBeDisabled()
  })

  it('导入剩下的空位不够时只加入放得下的部分', async () => {
    renderPage()
    await startNewTeam()
    // 先塞满 5 只，只留 1 个空位（用编号直接加，避开搜索交互）
    for (const dex of [1, 4, 7, 25, 150]) {
      await userEvent.type(screen.getByRole('combobox', { name: '添加宝可梦' }), `${dex}`)
      await userEvent.click(screen.getByRole('button', { name: /加入队伍/ }))
    }
    await openImport()

    await userEvent.type(
      screen.getByRole('textbox', { name: 'Showdown 队伍代码' }),
      'Charizard @ Life Orb{enter}{enter}Raichu @ Focus Sash',
    )
    await userEvent.click(screen.getByRole('button', { name: /^解析$/ }))

    // 只剩 1 个空位 → 只能加入 1 只，多出的如实提示
    expect(await screen.findByText(/识别到 2 只，可加入 1 只/)).toBeInTheDocument()
    expect(screen.getByText(/剩 1 个空位/)).toBeInTheDocument()
  })
})

describe('TeamsPage 成员摘要', () => {
  it('摘要行显示特性 / 道具 / 招式数', async () => {
    renderPage()
    await startNewTeam()
    await addCharizard()

    expect(screen.getAllByText(/Solar Power/).length).toBeGreaterThan(0)
  })
})
