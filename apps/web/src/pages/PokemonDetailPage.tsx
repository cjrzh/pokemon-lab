import { useMemo, useState } from 'react'
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  CircleAlert,
  BarChart3,
  BookOpen,
  Crown,
  Dna,
  Info,
  Languages,
  RefreshCw,
  Ruler,
  Shield,
  Sparkles,
  Star,
  Swords,
  Target,
  Users,
  Weight,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { PokemonArtwork } from '@/features/dex/components/PokemonArtwork'
import { StatsList, StatColorLegend, StatTotal } from '@/features/dex/components/StatsList'
import { GENERATION_REGION } from '@/features/dex/components/stats'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { TypeMatchup } from '@/features/dex/components/TypeMatchup'
import { DoublesCard } from '@/features/doubles/DoublesCard'
import type {
  EvolutionNode,
  PokemonDetail,
  PokemonMove,
  PokemonMoves,
} from '@/features/dex/api'
import { resolveMediaUrl } from '@/features/dex/api'
import {
  countByMethod,
  defaultVersionGroup,
  filterMoves,
  findVersionGroup,
  flattenMoveSections,
  MOVE_METHOD_LABEL,
  MOVE_METHOD_HINTS,
  MOVE_METHOD_ORDER,
  nextSort,
  sortMoves,
  uniqueMoveCount,
  type MoveRow,
  type MoveSort,
  type MoveSortKey,
} from '@/features/dex/moves'
import { abilityDetailLink } from '@/features/abilities/api'
import { moveDetailLink } from '@/features/moves/api'
import { useSTierAbilityNames } from '@/features/abilities/hooks'
import { usePokemonDetail } from '@/features/dex/hooks'
import { ZH as TYPE_ZH } from '@/features/type-chart/data'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const HABITAT_LABELS: Record<string, string> = {
  cave: '洞窟',
  forest: '森林',
  grassland: '草原',
  mountain: '山地',
  rare: '稀有',
  rough_terrain: '崎岖地形',
  sea: '海洋',
  urban: '城市',
  waters_edge: '水边',
}

const GROWTH_LABELS: Record<string, string> = {
  slow: '慢速',
  'medium-slow': '较慢',
  medium: '中速',
  'medium-fast': '较快',
  fast: '快速',
  'slow-then-very-fast': '先慢后快',
  'fast-then-very-slow': '先快后慢',
}

const EGG_GROUP_LABELS: Record<string, string> = {
  monster: '怪兽',
  water1: '水中1',
  water2: '水中2',
  water3: '水中3',
  bug: '虫',
  flying: '飞行',
  field: '陆上',
  fairy: '妖精',
  plant: '植物',
  humanlike: '人型',
  mineral: '矿物',
  amorphous: '无定形',
  ditto: '百变怪',
  dragon: '龙',
  undiscovered: '未发现',
}

const SHAPE_LABELS: Record<string, string> = {
  ball: '球形',
  squiggle: '蛇形',
  fish: '鱼形',
  arms: '双臂形',
  blob: '软体',
  upright: '直立形',
  legs: '双腿形',
  quadruped: '四足形',
  wings: '双翼形',
  tentacles: '触手形',
  heads: '多头形',
  humanoid: '人形',
  'bug-wings': '虫翼形',
  armor: '装甲形',
}

const COLOR_LABELS: Record<string, string> = {
  black: '黑',
  blue: '蓝',
  brown: '褐',
  gray: '灰',
  green: '绿',
  pink: '粉',
  purple: '紫',
  red: '红',
  white: '白',
  yellow: '黄',
}

export function PokemonDetailPage() {
  const { dexNumber } = useParams<{ dexNumber: string }>()
  const parsed = Number(dexNumber)
  const detail = usePokemonDetail(Number.isInteger(parsed) && parsed > 0 ? parsed : -1)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Button asChild size="sm" variant="ghost" className="-ml-2">
          <Link to="/dex">
            <ArrowLeft aria-hidden="true" />
            返回图鉴
          </Link>
        </Button>

        {detail.data ? (
          <div className="flex items-center gap-1.5">
            <Button
              asChild={detail.data.prev != null}
              size="sm"
              variant="outline"
              disabled={detail.data.prev == null}
              className={detail.data.prev == null ? 'opacity-50' : undefined}
            >
              {detail.data.prev ? (
                <Link to={`/dex/${detail.data.prev.dex_number}`}>
                  <ChevronLeft aria-hidden="true" />
                  #{String(detail.data.prev.dex_number).padStart(4, '0')}
                </Link>
              ) : (
                <span>
                  <ChevronLeft aria-hidden="true" />
                  上一只
                </span>
              )}
            </Button>
            <Button
              asChild={detail.data.next != null}
              size="sm"
              variant="outline"
              disabled={detail.data.next == null}
              className={detail.data.next == null ? 'opacity-50' : undefined}
            >
              {detail.data.next ? (
                <Link to={`/dex/${detail.data.next.dex_number}`}>
                  #{String(detail.data.next.dex_number).padStart(4, '0')}
                  <ChevronRight aria-hidden="true" />
                </Link>
              ) : (
                <span>
                  下一只
                  <ChevronRight aria-hidden="true" />
                </span>
              )}
            </Button>
          </div>
        ) : null}
      </div>

      {detail.isPending ? (
        <DetailSkeleton />
      ) : detail.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>无法加载图鉴详情</AlertTitle>
          <AlertDescription>{describeApiError(detail.error)}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void detail.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      ) : (
        <DetailBody detail={detail.data} />
      )}
    </div>
  )
}

function DetailBody({ detail }: { detail: PokemonDetail }) {
  // S 级特性名集合（图鉴页标红加粗）；查询失败时静默降级为普通显示。
  const sTierQuery = useSTierAbilityNames()
  const sTierNames = sTierQuery.data ?? new Set<string>()
  const heightM = detail.height_dm != null ? detail.height_dm / 10 : null
  const weightKg = detail.weight_hg != null ? detail.weight_hg / 10 : null
  const displayName = detail.name_zh ?? detail.name_en
  const primaryType = detail.types[0] ?? 'normal'
  const secondaryType = detail.types[1] ?? primaryType
  const badges = [
    detail.is_legendary ? { label: '传说的宝可梦', icon: Star } : null,
    detail.is_mythical ? { label: '幻之宝可梦', icon: Sparkles } : null,
    detail.is_baby ? { label: '幼年宝可梦', icon: Sparkles } : null,
  ].filter(Boolean) as { label: string; icon: typeof Star }[]

  return (
    <div className="space-y-4">
      {/* ---------- Hero：属性渐变底 + 立绘 + 名称 / 档案 ---------- */}
      <Card className="relative overflow-hidden">
        {/* 双属性渐变背景：让不同宝可梦的详情页有各自的「性格色」 */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.55]"
          style={{
            background: `radial-gradient(120% 90% at 8% 0%, color-mix(in oklab, var(--type-${primaryType}) 26%, transparent), transparent 62%), radial-gradient(90% 80% at 100% 100%, color-mix(in oklab, var(--type-${secondaryType}) 18%, transparent), transparent 68%)`,
          }}
        />
        <div className="relative grid gap-6 p-4 sm:grid-cols-[minmax(0,17rem)_minmax(0,1fr)] sm:p-6">
          <div className="relative">
            <PokemonArtwork
              src={resolveMediaUrl(detail.artwork_url)}
              fallbackSrc={resolveMediaUrl(detail.artwork_fallback_url ?? detail.sprite_url)}
              alt={displayName}
              variant="hero"
              className="mx-auto aspect-square w-full max-w-68 bg-transparent sm:max-w-none"
            />
            {/* 六项种族值的迷你条形图：Hero 里就能看出强度分布 */}
            <div className="mx-auto mt-1 w-full max-w-68 sm:max-w-none">
              <StatsList stats={detail.stats} compact />
            </div>
          </div>

          <div className="flex min-w-0 flex-col">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-mono text-xs font-medium text-muted-foreground tabular-nums">
                  #{String(detail.dex_number).padStart(4, '0')}
                </p>
                <h1 className="font-heading mt-1 text-[2rem] leading-none font-semibold tracking-tight">
                  {displayName}
                </h1>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  {[detail.name_en, detail.name_ja].filter(Boolean).join(' · ')}
                  {detail.genus_zh ? (
                    <span className="ml-2 text-xs">· {detail.genus_zh}</span>
                  ) : null}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                {detail.is_demo ? <Badge variant="secondary">演示数据</Badge> : null}
                <Badge variant="outline">{detail.source_label}</Badge>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {detail.types.map((t) => (
                <TypeBadge key={t} type={t} className="px-2.5 py-1 text-sm shadow-sm" />
              ))}
              {badges.map(({ label, icon: Icon }) => (
                <Badge key={label} variant="secondary" className="gap-1 backdrop-blur">
                  <Icon aria-hidden="true" />
                  {label}
                </Badge>
              ))}
            </div>

            {detail.genus_zh && detail.genus_zh_source === 'project' ? (
              <p className="mt-2">
                <TranslationBadge label="分类为项目自译" />
              </p>
            ) : null}

            {/* 图鉴描述：引号式排版，突出「图鉴原文」的质感 */}
            {detail.flavor_zh || detail.flavor_en ? (
              <figure className="mt-4 rounded-xl border border-border/70 bg-card/70 p-3.5 shadow-sm backdrop-blur-sm">
                <blockquote className="text-sm leading-relaxed">
                  {detail.flavor_zh ?? detail.flavor_en}
                </blockquote>
                <figcaption className="mt-1.5 text-[10px] text-muted-foreground">
                  {detail.flavor_zh && detail.flavor_zh_source === 'project' ? (
                    <span className="inline-flex items-center gap-1">
                      <Languages aria-hidden="true" className="size-3" />
                      项目自译 · 上游无官方中文文本，仅供参考
                    </span>
                  ) : detail.flavor_zh ? (
                    '图鉴描述 · 官方中文'
                  ) : (
                    '英文原文 · 该条目暂无中文图鉴文本'
                  )}
                </figcaption>
              </figure>
            ) : null}

            {/* 基础档案：图标化，四列在桌面一行排开 */}
            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
              <Meta
                icon={Ruler}
                label="身高"
                value={heightM != null ? `${heightM.toFixed(1)} m` : '—'}
              />
              <Meta
                icon={Weight}
                label="体重"
                value={weightKg != null ? `${weightKg.toFixed(1)} kg` : '—'}
              />
              <Meta icon={Target} label="捕捉率" value={detail.capture_rate ?? '—'} />
              <Meta icon={Users} label="性别" value={<GenderRatio rate={detail.gender_rate} />} />
            </dl>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ---------- 种族值 ---------- */}
        <Card>
          <CardHeader className="flex-row items-baseline justify-between">
            <CardTitle className="flex items-center gap-2">
              <BarChart3 aria-hidden="true" className="size-4 text-muted-foreground" />
              种族值
            </CardTitle>
            <StatTotal stats={detail.stats} />
          </CardHeader>
          <CardContent className="space-y-3">
            <StatsList stats={detail.stats} />
            <StatColorLegend />
          </CardContent>
        </Card>

        {/* ---------- 图鉴档案 ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen aria-hidden="true" className="size-4 text-muted-foreground" />
              图鉴档案
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <Meta
                label="登场世代"
                value={
                  detail.generation_introduced
                    ? `第 ${detail.generation_introduced} 世代（${GENERATION_REGION[detail.generation_introduced] ?? '—'}）`
                    : '—'
                }
              />
              <Meta label="成长速度" value={detail.growth_rate ? GROWTH_LABELS[detail.growth_rate] ?? detail.growth_rate : '—'} />
              <Meta label="孵化周期" value={detail.hatch_counter != null ? `${detail.hatch_counter} 步数 × 255` : '—'} />
              <Meta label="基础亲密度" value={detail.base_happiness ?? '—'} />
              <Meta label="栖息地" value={detail.habitat ? HABITAT_LABELS[detail.habitat] ?? detail.habitat : '—'} />
              <Meta label="颜色" value={detail.color ? COLOR_LABELS[detail.color] ?? detail.color : '—'} />
              <Meta
                label="蛋群"
                value={
                  detail.egg_groups.length > 0
                    ? detail.egg_groups.map((g) => EGG_GROUP_LABELS[g] ?? g).join(' / ')
                    : '—'
                }
              />
              <Meta
                label="形态"
                value={detail.shape ? SHAPE_LABELS[detail.shape] ?? detail.shape : '—'}
              />
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* ---------- 特性 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles aria-hidden="true" className="size-4 text-muted-foreground" />
            特性
          </CardTitle>
        </CardHeader>
        <CardContent>
          {detail.abilities.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无特性数据。</p>
          ) : (
            <ul className="space-y-3">
              {detail.abilities.map((ability) => {
                const isS = sTierNames.has(ability.name)
                return (
                <li key={ability.name} className="text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={ability.is_hidden ? 'outline' : 'secondary'}>
                      {ability.is_hidden ? '隐藏特性' : '普通特性'}
                    </Badge>
                    <Link
                      to={abilityDetailLink(ability.name)}
                      className={cn(
                        'font-medium underline-offset-4 hover:underline',
                        isS && 'font-bold text-destructive',
                      )}
                    >
                      {ability.zh ?? ability.name}
                    </Link>
                    {ability.zh ? (
                      <span className="text-xs text-muted-foreground">{ability.name}</span>
                    ) : null}
                    {isS ? (
                      <Badge className="gap-1 bg-destructive text-white">
                        <Crown aria-hidden="true" className="size-3" />
                        S 级
                      </Badge>
                    ) : null}
                  </div>
                  {ability.effect_zh ? (
                    <p className="mt-1 text-muted-foreground">{ability.effect_zh}</p>
                  ) : ability.effect_en ? (
                    <p className="mt-1 text-muted-foreground">{ability.effect_en}</p>
                  ) : null}
                </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* ---------- 属性相性 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield aria-hidden="true" className="size-4 text-muted-foreground" />
            属性相性
          </CardTitle>
          <CardDescription>
            {detail.types.map((t) => TYPE_ZH[t] ?? t).join(' / ')} 的攻防倍率：
            「受击」看被各属性攻击时的伤害倍率，「出击」看用自身属性招式攻击各属性时的倍率。
            与属性克制计算器共用同一份规范克制表。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TypeMatchup types={detail.types} />
        </CardContent>
      </Card>

      {/* ---------- 双打对战辅助（BDSP / 剑盾 / 朱紫 / 冠军） ---------- */}
      <DoublesCard dexNumber={detail.dex_number} genderRate={detail.gender_rate} />


      {/* ---------- 进化链 ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Dna aria-hidden="true" className="size-4 text-muted-foreground" />
            进化链
          </CardTitle>
        </CardHeader>
        <CardContent>
          {detail.evolution.chain ? (
            <EvolutionTree node={detail.evolution.chain} currentDex={detail.dex_number} />
          ) : (
            <p className="text-sm text-muted-foreground">暂无进化信息（该宝可梦不进化）。</p>
          )}
        </CardContent>
      </Card>

      {/* ---------- 招式 ---------- */}
      <MovesCard moves={detail.moves} />

      <p className="text-center text-[11px] text-muted-foreground">
        {detail.synced_at
          ? `数据同步于 ${new Date(detail.synced_at).toLocaleString()} · `
          : ''}
        来源：{detail.source_label}（PokéAPI / pokemon.com 公开图鉴资源）
      </p>
    </div>
  )
}

/** 译文来源标记：小号、低对比度，避免喧宾夺主但保证可追溯。 */
function TranslationBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-0.5 rounded-full border border-border px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground">
      <Languages aria-hidden="true" className="size-2.5" />
      {label}
    </span>
  )
}

function Meta({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: React.ReactNode
  icon?: typeof Ruler
}) {
  return (
    <div>
      <dt className="flex items-center gap-1 text-[11px] text-muted-foreground">
        {Icon ? <Icon aria-hidden="true" className="size-3" /> : null}
        {label}
      </dt>
      <dd className="mt-0.5 font-medium tabular-nums">{value}</dd>
    </div>
  )
}

function GenderRatio({ rate }: { rate: number | null }) {
  if (rate == null) return <span>—</span>
  if (rate < 0) return <span className="text-muted-foreground">无性别</span>
  const female = (rate / 8) * 100
  const male = 100 - female
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="text-type-water">♂ {male.toFixed(0)}%</span>
      <span className="text-type-psychic">♀ {female.toFixed(0)}%</span>
    </span>
  )
}

function EvolutionTree({ node, currentDex }: { node: EvolutionNode; currentDex: number }) {
  const isCurrent = node.dex === currentDex

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link
        to={`/dex/${node.dex}`}
        className={cn(
          'rounded-lg px-3 py-2 text-sm transition-colors',
          isCurrent
            ? 'bg-primary/10 font-medium text-primary ring-1 ring-primary/30'
            : 'bg-muted hover:bg-muted/70',
        )}
      >
        <span className="block text-[10px] text-muted-foreground tabular-nums">
          #{String(node.dex).padStart(4, '0')}
        </span>
        {node.zh ?? node.name}
      </Link>
      {node.evolves_to.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span aria-hidden="true" className="text-muted-foreground">
            →
          </span>
          {node.evolves_to.map((child, index) => (
            <div key={child.dex + index} className="flex flex-wrap items-center gap-2">
              {index > 0 ? (
                <span aria-hidden="true" className="text-xs text-muted-foreground">
                  或
                </span>
              ) : null}
              <div className="flex flex-col gap-1">
                {child.detail ? (
                  <span className="text-[10px] text-muted-foreground">{child.detail}</span>
                ) : null}
                <EvolutionTree node={child} currentDex={currentDex} />
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function MovesCard({ moves }: { moves: PokemonMoves }) {
  const [versionGroup, setVersionGroup] = useState<string | null>(() =>
    defaultVersionGroup(moves),
  )
  const [method, setMethod] = useState('all')
  const [query, setQuery] = useState('')

  const group = findVersionGroup(moves, versionGroup)
  const counts = countByMethod(group)
  const sections = filterMoves(group, { method, query })
  const shown = sections.reduce((sum, section) => sum + section.moves.length, 0)

  if (moves.version_groups.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Swords aria-hidden="true" className="size-4 text-muted-foreground" />
            招式
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">暂无招式数据。</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-row flex-wrap items-baseline justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Swords aria-hidden="true" className="size-4 text-muted-foreground" />
            招式
          </CardTitle>
          <p className="text-xs text-muted-foreground tabular-nums">
            {group?.label} · 共 {uniqueMoveCount(group)} 个招式
          </p>
        </div>

        {/* 版本组切换：数据完整保留全部版本，默认选中最新收录的作品 */}
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1" role="group" aria-label="选择版本">
          {moves.version_groups.map((vg) => {
            const active = vg.version_group === group?.version_group
            return (
              <button
                key={vg.version_group}
                type="button"
                onClick={() => {
                  setVersionGroup(vg.version_group)
                  setMethod('all')
                }}
                aria-pressed={active}
                className={cn(
                  'shrink-0 rounded-full border px-2.5 py-1 text-xs transition-colors',
                  active
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {vg.label}
              </button>
            )
          })}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* 学习方式 + 名称筛选 */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-1" role="group" aria-label="按学习方式筛选">
            <button
              type="button"
              onClick={() => setMethod('all')}
              aria-pressed={method === 'all'}
              className={cn(
                'rounded-md px-2 py-1 text-xs transition-colors',
                method === 'all'
                  ? 'bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              全部 {uniqueMoveCount(group)}
            </button>
            {MOVE_METHOD_ORDER.filter((key) => counts[key]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setMethod(method === key ? 'all' : key)}
                aria-pressed={method === key}
                title={MOVE_METHOD_HINTS[key]}
                className={cn(
                  'rounded-md px-2 py-1 text-xs transition-colors',
                  method === key
                    ? 'bg-primary/10 font-medium text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {MOVE_METHOD_LABEL[key] ?? key} {counts[key]}
              </button>
            ))}
          </div>

          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="筛选招式名…"
            className="h-8 w-full max-w-48 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            aria-label="筛选招式"
          />
          {shown !== uniqueMoveCount(group) ? (
            <span className="text-xs text-muted-foreground tabular-nums">{shown} 条</span>
          ) : null}
        </div>

        {sections.length === 0 ? (
          <p className="text-sm text-muted-foreground">没有匹配的招式。</p>
        ) : method === 'all' ? (
          // 「全部」视图：合并成一张表，所有招式共同参与排序（去重，附学习方式列）
          <MoveTable rows={flattenMoveSections(sections)} mode="merged" />
        ) : (
          sections.map((section) => (
            <div key={section.method}>
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium">
                <span className="rounded bg-muted px-1.5 py-0.5">{section.label}</span>
                <span className="text-muted-foreground">
                  {MOVE_METHOD_HINTS[section.method] ?? ''}
                </span>
                <span className="text-muted-foreground tabular-nums">
                  {section.moves.length}
                </span>
              </p>
              <MoveTable rows={section.moves} mode={section.method} />
            </div>
          ))
        )}

        <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
          <Info aria-hidden="true" className="size-3" />
          覆盖升级、招式学习器、教学与蛋招式等全部学习方式；数值来自 PokéAPI 的招式数据。
        </p>
      </CardContent>
    </Card>
  )
}

/**
 * 可排序表头：点击升序 → 再点降序 → 第三次恢复默认顺序。
 * 用 aria-sort 告诉屏幕阅读器当前排序状态。
 */
function SortableHeader({
  column,
  label,
  align,
  sort,
  onSort,
}: {
  column: MoveSortKey
  label: string
  align: 'left' | 'right'
  sort: MoveSort | null
  onSort: () => void
}) {
  const active = sort?.key === column
  const direction = active ? sort.direction : null
  const ariaSort = direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none'

  return (
    <th
      aria-sort={ariaSort}
      className={cn('px-3 py-2 font-medium whitespace-nowrap', align === 'right' ? 'text-right' : 'text-left')}
    >
      <button
        type="button"
        onClick={onSort}
        title={direction === 'asc' ? '点击降序' : direction === 'desc' ? '点击恢复默认' : '点击升序'}
        className={cn(
          'inline-flex items-center gap-1 rounded-md px-1 py-0.5 -mx-1 transition-colors',
          'hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none',
          'cursor-pointer select-none',
          align === 'right' && 'flex-row-reverse',
          active ? 'text-foreground' : 'text-muted-foreground',
        )}
      >
        <span>{label}</span>
        <span aria-hidden="true" className="inline-flex w-3 justify-center">
          {direction === 'asc' ? (
            <ArrowUp className="size-3" />
          ) : direction === 'desc' ? (
            <ArrowDown className="size-3" />
          ) : (
            <ChevronsUpDown className="size-3 opacity-40" />
          )}
        </span>
      </button>
    </th>
  )
}

/**
 * 招式表。
 *
 * mode:
 *   - 'merged'：选择「全部」时的合并视图，额外显示「学习方式」列，等级列始终显示
 *     （非升级招式显示「—」）；
 *   - 其他值：单个学习方式，等级列只在 level-up 时显示。
 */
function MoveTable({
  rows,
  mode,
}: {
  rows: MoveRow[] | PokemonMove[]
  mode: 'merged' | string
}) {
  const [sort, setSort] = useState<MoveSort | null>(null)
  const merged = mode === 'merged'
  // 单学习方式视图的每一行只有一种学习方式，这里统一成 MoveRow 便于共用表格。
  const normalized = useMemo<MoveRow[]>(
    () =>
      rows.map((row) =>
        'learn_methods' in row ? row : { ...row, learn_methods: [mode] },
      ),
    [rows, mode],
  )
  const sorted = useMemo(() => sortMoves(normalized, sort), [normalized, sort])
  const showLevel = merged || mode === 'level-up'

  const columns: {
    key: MoveSortKey
    label: string
    align: 'left' | 'right'
    show: boolean
  }[] = [
    { key: 'level', label: '等级', align: 'left', show: showLevel },
    { key: 'name', label: '招式', align: 'left', show: true },
    { key: 'method', label: '学习方式', align: 'left', show: merged },
    { key: 'type', label: '属性', align: 'left', show: true },
    { key: 'damageClass', label: '分类', align: 'left', show: true },
    { key: 'power', label: '威力', align: 'right', show: true },
    { key: 'accuracy', label: '命中', align: 'right', show: true },
    { key: 'pp', label: 'PP', align: 'right', show: true },
  ]

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full min-w-[30rem] text-sm">
        <thead className="bg-muted/60 text-xs text-muted-foreground">
          <tr>
            {columns
              .filter((column) => column.show)
              .map((column) => (
                <SortableHeader
                  key={column.key}
                  column={column.key}
                  label={column.label}
                  align={column.align}
                  sort={sort}
                  onSort={() => setSort((current) => nextSort(current, column.key))}
                />
              ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((move) => (
            <tr key={move.name} className="border-t">
              {showLevel ? (
                <td className="px-3 py-1.5 text-muted-foreground tabular-nums">
                  {move.level > 0 ? move.level : '—'}
                </td>
              ) : null}
              <td className="px-3 py-1.5">
                <Link
                  to={moveDetailLink(move.name)}
                  className="font-medium underline-offset-4 hover:text-primary hover:underline"
                >
                  {move.zh ?? move.name}
                </Link>
                {move.zh && move.name !== move.zh ? (
                  <span className="ml-1.5 text-[10px] text-muted-foreground">{move.name}</span>
                ) : null}
                {move.description_zh ? (
                  <span className="mt-0.5 block text-[10px] text-muted-foreground">
                    {move.description_zh}
                  </span>
                ) : null}
              </td>
              {merged ? (
                <td className="px-3 py-1.5 align-top">
                  <span className="flex flex-wrap gap-1">
                    {move.learn_methods.map((method) => (
                      <span
                        key={method}
                        className="rounded bg-muted px-1.5 py-0 text-[10px] whitespace-nowrap text-muted-foreground"
                      >
                        {MOVE_METHOD_LABEL[method] ?? method}
                      </span>
                    ))}
                  </span>
                </td>
              ) : null}
              <td className="px-3 py-1.5 align-top">
                {move.type ? (
                  <TypeBadge type={move.type} className="px-1.5 py-0 text-[10px]" />
                ) : (
                  '—'
                )}
              </td>
              <td className="px-3 py-1.5 align-top text-muted-foreground">
                {move.damage_class_zh ?? move.damage_class ?? '—'}
              </td>
              <td className="px-3 py-1.5 text-right align-top tabular-nums">
                {move.power ?? '—'}
              </td>
              <td className="px-3 py-1.5 text-right align-top tabular-nums">
                {move.accuracy ?? '—'}
              </td>
              <td className="px-3 py-1.5 text-right align-top tabular-nums">
                {move.pp ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Card>
        <div className="grid gap-5 p-4 sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] sm:p-6">
          <Skeleton className="mx-auto aspect-square w-full max-w-64 rounded-xl" />
          <div className="space-y-3">
            <Skeleton className="h-3 w-14" />
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-4 w-32" />
            <div className="flex gap-1.5">
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-6 w-16" />
            </div>
            <Skeleton className="h-16 w-full" />
          </div>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }, (_, i) => (
          <Card key={i}>
            <CardContent className="space-y-3 pt-6">
              {Array.from({ length: 6 }, (_, j) => (
                <div key={j} className="flex items-center gap-3">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-2 flex-1" />
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
