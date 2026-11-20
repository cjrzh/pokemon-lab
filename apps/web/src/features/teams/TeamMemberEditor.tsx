/**
 * 队伍成员编辑器（建队页 / 导出页共用）。
 *
 * 一只宝可梦的可编辑配置：
 *   - 招式：从「该版本合法招式」里选（最多 4 个），按使用率排序，右侧链到招式详情页；
 *   - 特性：下拉框，按使用率降序，默认选中使用率最高的那一个；
 *   - 道具：下拉框（统计推荐 + 道具百科全量），带图标，也可手输英文名；
 *   - 性格、EV（或能力点）、IV：默认取统计推荐配点，可逐项改；
 *   - 太晶属性（仅朱紫）、极巨化等级 / 超极巨化（仅剑盾）、闪光、性别、等级。
 *
 * 首次拿到 `/team-options` 时用推荐值填充（用户已经改过的不覆盖）。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ExternalLink,
  GripVertical,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ItemIcon } from '@/features/dex/components/ItemIcon'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { DOUBLES_STAT_LABELS } from '@/features/doubles/api'
import {
  NATURE_EFFECT,
  NATURE_EN,
  NATURE_ZH,
  STAT_ZH,
  natureEffectLabel,
} from '@/features/doubles/showdown'
import { moveDetailLink } from '@/features/moves/api'
import { CopyShowdownButton } from '@/features/teams/CopyShowdownButton'
import { ItemPicker } from '@/features/teams/ItemPicker'
import { renderMemberShowdown } from '@/features/teams/showdownText'
import { LANGUAGES, type TeamLanguage, type TeamMember, type TeamOptionUsage } from '@/features/teams/api'
import { useTeamMemberOptions } from '@/features/teams/hooks'
import { cn } from '@/lib/utils'

const NATURE_KEYS = Object.keys(NATURE_EN)
const MAX_MOVES = 4

/** 下拉框里的一行特性（合法值 + 使用率），按使用率降序。 */
interface AbilityOption {
  value: string
  label: string
  pct: number | null
}

export function TeamMemberEditor({
  index,
  member,
  formatKey,
  pointsKind,
  defaultLevel,
  teamMembers,
  onChange,
  onRemove,
  selectedForm,
  onFormChange,
  dragHandleProps,
  rowProps,
  dragging = false,
  showLineBefore = false,
  showLineAfter = false,
  onMoveUp,
  onMoveDown,
  canMoveUp = false,
  canMoveDown = false,
}: {
  index: number
  member: TeamMember
  formatKey: string
  pointsKind: 'ev' | 'stat_points'
  defaultLevel: number
  /** 同队其它成员（用于提示道具 / 编号重复）。 */
  teamMembers: TeamMember[]
  onChange: (next: TeamMember) => void
  onRemove: () => void
  /**
   * 当前选中的形态：`undefined` 表示自动（后端选使用率最高的形态），
   * `null` 表示明确选择默认形态，其余为本地形态 slug。
   * 由父组件持有：形态影响 Showdown 名、属性与推荐配置，切换后要整只重算。
   */
  selectedForm?: string | null
  /** 切换形态（`null` = 默认形态）。 */
  onFormChange?: (form: string | null) => void
  /** 拖动手柄的属性（HTML5 DnD）；不传则不显示手柄。 */
  dragHandleProps?: React.HTMLAttributes<HTMLElement> & { draggable?: boolean }
  /** 整行的放置属性。 */
  rowProps?: React.HTMLAttributes<HTMLDivElement>
  dragging?: boolean
  /** 拖动时在该行上方 / 下方画插入线。 */
  showLineBefore?: boolean
  showLineAfter?: boolean
  /** 键盘 / 触屏可用的上下移动。 */
  onMoveUp?: () => void
  onMoveDown?: () => void
  canMoveUp?: boolean
  canMoveDown?: boolean
}) {
  const [open, setOpen] = useState(index === 0)
  // `undefined` = 自动选（首次加入时由后端挑使用率最高的形态）；
  // `null` = 明确选了默认形态（请求 `form=default`）。两者语义不同，不能合并。
  const formQuery = selectedForm === undefined ? undefined : (selectedForm ?? 'default')
  const options = useTeamMemberOptions(member.dex_number, formatKey, formQuery)
  const [appliedFor, setAppliedFor] = useState<string | null>(null)

  /**
   * 拿到选项后把「形态相关」的字段同步过来并补全空配置。
   *
   * 两种情况：
   *   - 首次自动填充（`appliedFor` 为空）：只补空字段，用户改过的不覆盖；
   *   - **切换形态**：形态变了 → Showdown 名、特性、可用招式都可能不同，
   *     旧配置里属于上一个形态的招式 / 特性必须换成新形态的推荐值，
   *     否则会导出「热洛托姆用热水」这种非法组合。
   */
  useEffect(() => {
    if (!options.data) return
    const data = options.data
    const appliedKey = `${member.dex_number}-${formatKey}-${data.form ?? 'default'}`
    if (appliedFor === appliedKey) return
    const switchingForm = appliedFor !== null && appliedFor !== appliedKey
    setAppliedFor(appliedKey)

    // 用 showdown 名与推荐值补全空字段；用户已填的保持不变
    const rec = data.recommended
    const legalMoves = new Set(
      (data.legal_moves ?? []).map((move) => move.name_en ?? move.name),
    )
    // 队里存的是 Showdown 显示名（`Levitate`），选项里的 `slug` 是本地小写形式
    // （`levitate`）；两种写法都算合法，避免切换形态时误把合法特性改掉。
    const legalAbilities = new Set(
      (data.legal_abilities ?? []).flatMap((ability) => [
        ability.name_en ?? ability.slug,
        ability.slug,
      ]),
    )
    const previousMoves = member.moves.filter((move) =>
      !switchingForm ? true : legalMoves.has(move),
    )
    // 超极巨化：只在剑盾、且该形态确实有 G 形态时保留。
    // 首次自动填充时沿用成员上的标记（导入 `Charizard-Gmax` / `Gigantamax Charizard`
    // 时后端已折算成 `gigantamax: true`）；切换形态 / 重新拉取后以用户当前选择为准，
    // 避免取消勾选后又被自动勾回来。
    const gigantamax =
      formatKey === 'swsh' && Boolean(data.can_gigantamax)
        ? switchingForm || appliedFor === null
          ? Boolean(member.gigantamax) || Boolean(data.gigantamax)
          : Boolean(member.gigantamax)
        : false
    const next: TeamMember = {
      ...member,
      // 队伍里只存 Showdown 规范名（导出要用），搜索加入时给的是小写英文名，
      // 这里统一换成后端确认的规范名（如 charizard → Charizard，
      // rotom-wash → Rotom-Wash）。切换形态时这个名字会变，必须跟着更新。
      showdown_name: data.showdown_name || member.showdown_name,
      ability:
        switchingForm || !member.ability
          ? (topAbility(data) ?? null)
          : legalAbilities.has(member.ability)
            ? member.ability
            : (topAbility(data) ?? member.ability),
      item: member.item ?? rec?.items[0]?.name_en ?? null,
      nature: member.nature ?? rec?.spread?.nature ?? null,
      evs:
        member.evs.some((value) => value !== 0) || !rec?.spread
          ? member.evs
          : rec.spread.points,
      moves:
        previousMoves.length > 0
          ? previousMoves
          : (rec?.moves.slice(0, MAX_MOVES).map((move) => move.name_en ?? move.name) ?? []),
      // 性别：已有值保持；新建时 AddSlot 默认雌性，这里按性别比例校正
      // （尼多朗只能雄性 → M，超梦无性别 → null）
      gender: member.gender === null ? null : genderFromRate(data.gender_rate),
      gigantamax,
      // 注意：不要在自动填充里补 level / shiny ——
      // 已保存队伍的 level=null 表示「按格式默认」，补成 100 会让内容比较
      // 误判为「有未保存改动」。默认值由新建流程（AddSlot）写入。
    }
    onChange(next)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.data])

  const usedItems = new Set(
    teamMembers
      .filter((other) => other.dex_number !== member.dex_number)
      .map((other) => (other.item ?? '').toLowerCase())
      .filter(Boolean),
  )
  const itemConflict = Boolean(member.item) && usedItems.has((member.item ?? '').toLowerCase())

  const data = options.data
  const moveOptions = useMemo(() => sortMoves(data?.legal_moves ?? [], data?.recommended), [data])
  const abilityOptions = useMemo(() => sortAbilities(data), [data])
  /** 使用率最高的特性 —— 默认选中它，下拉里也标一下。 */
  const recommendedAbility = abilityOptions[0]?.value ?? null
  const recommended = data?.recommended ?? null
  const statsBySlug = useMemo(() => {
    const map = new Map<string, number>()
    for (const move of recommended?.moves ?? []) map.set(move.slug, move.pct)
    return map
  }, [recommended])

  // 图图犬（#235）的招式表只有写生；后端已按写生规则展开合法招式，这里补一句说明
  const isSmeargle = member.dex_number === 235
  const displayName = data?.name_zh ?? member.showdown_name
  const types = data?.types ?? []
  const recommendedItem = recommended?.items[0]
  /** 可选形态（后端已按使用率降序；只有一种形态时为空）。 */
  const formOptions = data?.forms ?? []
  const activeFormOption =
    formOptions.find((item) => item.form === (data?.form ?? null)) ?? null

  const update = (patch: Partial<TeamMember>) => onChange({ ...member, ...patch })

  const toggleMove = (move: TeamOptionUsage) => {
    const value = move.name_en ?? move.name
    if (member.moves.includes(value)) {
      update({ moves: member.moves.filter((item) => item !== value) })
      return
    }
    if (member.moves.length >= MAX_MOVES) return
    update({ moves: [...member.moves, value] })
  }

  return (
    <div
      {...rowProps}
      className={cn(
        'relative rounded-2xl border border-border/70 bg-card shadow-[var(--card-glow)] transition-[opacity,border-color]',
        dragging && 'opacity-40',
        // 拖动时把整行略抬高，提示这是可放置的目标
        dragHandleProps && !dragging && 'hover:border-primary/40',
      )}
    >
      {showLineBefore ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-2 -top-1 h-0.5 rounded-full bg-primary"
        />
      ) : null}
      {showLineAfter ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-2 -bottom-1 h-0.5 rounded-full bg-primary"
        />
      ) : null}
      {/* ---------- 摘要行 ---------- */}
      <div className="flex items-center gap-2 px-2.5 py-2">
        {dragHandleProps ? (
          <span
            {...dragHandleProps}
            role="button"
            tabIndex={-1}
            aria-label={`拖动 ${member.showdown_name} 调整顺序`}
            title="拖动调整顺序"
            className="shrink-0 cursor-grab active:cursor-grabbing rounded p-0.5 text-muted-foreground/60 hover:bg-muted hover:text-foreground"
          >
            <GripVertical aria-hidden="true" className="size-4" />
          </span>
        ) : null}
        <span className="w-5 shrink-0 text-center font-mono text-[11px] text-muted-foreground tabular-nums">
          {index + 1}
        </span>
        {/* 图标与名字都链到图鉴详情页（新标签打开，不打断建队） */}
        <Link
          to={`/dex/${member.dex_number}`}
          title={`查看图鉴：${displayName}`}
          aria-label={`查看图鉴 ${displayName}`}
          className="shrink-0"
        >
          <PokemonSprite
            src={resolveMediaUrl(data?.sprite_url)}
            alt={displayName}
            type={types[0]}
            className="size-8"
          />
        </Link>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="min-w-0 flex-1 text-left"
        >
          <span className="flex flex-wrap items-center gap-1.5">
            <Link
              to={`/dex/${member.dex_number}`}
              title={`查看图鉴：${displayName}`}
              className="truncate text-sm font-medium underline-offset-2 hover:text-primary hover:underline"
            >
              {displayName}
            </Link>
            {types.map((type) => (
              <TypeBadge key={type} type={type} className="px-1 py-0 text-[9px]" />
            ))}
            {activeFormOption && !activeFormOption.is_default ? (
              <Badge variant="secondary" className="text-[9px]">
                {activeFormOption.label}
              </Badge>
            ) : null}
            {formatKey === 'swsh' ? (
              <Badge
                variant="outline"
                className="text-[9px] tabular-nums text-muted-foreground"
                title={`极巨化等级 ${member.dynamax_level ?? 10}（0–10）`}
              >
                极巨 Lv.{member.dynamax_level ?? 10}
              </Badge>
            ) : null}
            {member.gigantamax && formatKey === 'swsh' ? (
              <Badge variant="secondary" className="text-[9px]">
                超极巨化
              </Badge>
            ) : null}
            {data && !data.has_stats ? (
              <Badge variant="outline" className="text-[9px] text-muted-foreground">
                无使用率数据
              </Badge>
            ) : null}
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[10px] text-muted-foreground">
            <span>{member.ability ?? '未选特性'}</span>
            <span>·</span>
            <span className={cn(itemConflict && 'text-destructive')}>
              {member.item ?? '未选道具'}
              {itemConflict ? '（与队友重复）' : ''}
            </span>
            <span>·</span>
            <span>{member.moves.filter(Boolean).length} 招式</span>
          </span>
        </button>
        <CopyShowdownButton
          text={renderMemberShowdown(member, { formatKey, defaultLevel })}
          label={`复制 ${displayName} 的 Showdown 代码`}
        />
        {onMoveUp || onMoveDown ? (
          <span className="flex shrink-0 items-center">
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label="上移这一只"
              title="上移"
              disabled={!canMoveUp}
              onClick={onMoveUp}
            >
              <ArrowUp aria-hidden="true" />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label="下移这一只"
              title="下移"
              disabled={!canMoveDown}
              onClick={onMoveDown}
            >
              <ArrowDown aria-hidden="true" />
            </Button>
          </span>
        ) : null}
        <Button size="icon-sm" variant="ghost" aria-label="移除这只" onClick={onRemove}>
          <Trash2 aria-hidden="true" />
        </Button>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={open ? '收起配置' : '展开配置'}
          onClick={() => setOpen((value) => !value)}
        >
          <ChevronDown
            aria-hidden="true"
            className={cn('transition-transform', open && 'rotate-180')}
          />
        </Button>
      </div>

      {open ? (
        <div className="space-y-3.5 border-t px-3 py-3">
          {options.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : options.isError ? (
            <p className="text-xs text-destructive">无法加载该宝可梦的建队选项。</p>
          ) : (
            <>
              {recommended ? (
                <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/50 px-2.5 py-1.5">
                  <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <Sparkles aria-hidden="true" className="size-3 text-primary" />
                    使用率推荐
                    {recommended.usage != null ? `（${recommended.usage.toFixed(1)}%）` : ''}
                    {recommended.rank ? ` · 排名 #${recommended.rank}` : ''}
                  </span>
                  <Button
                    size="xs"
                    variant="ghost"
                    className="ml-auto"
                    onClick={() => applyRecommendation(recommended, member, update)}
                  >
                    <RefreshCw aria-hidden="true" />
                    套用推荐
                  </Button>
                </div>
              ) : null}

              {formOptions.length > 1 && onFormChange ? (
                <Section
                  title="形态"
                  hint="形态决定属性、专属招式与导出名称"
                >
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="选择形态">
                    {formOptions.map((option) => {
                      const value = option.form
                      const active = value === (data?.form ?? null)
                      return (
                        <button
                          key={value ?? 'default'}
                          type="button"
                          aria-pressed={active}
                          onClick={() => onFormChange(value)}
                          className={cn(
                            'flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] transition-colors',
                            active
                              ? 'border-primary/50 bg-primary/10 text-primary'
                              : 'border-border text-muted-foreground hover:bg-muted',
                          )}
                        >
                          {option.sprite_url ? (
                            <PokemonSprite
                              src={resolveMediaUrl(option.sprite_url)}
                              alt={option.label}
                              type={option.types[0]}
                              className="size-4"
                            />
                          ) : null}
                          {option.label}
                          {option.usage != null ? (
                            <span className="text-[9px] opacity-70 tabular-nums">
                              {option.usage.toFixed(1)}%
                            </span>
                          ) : null}
                        </button>
                      )
                    })}
                  </div>
                </Section>
              ) : null}

              <Section title="特性 / 道具">
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="space-y-1">
                    <span className="text-[10px] text-muted-foreground">特性</span>
                    <select
                      value={member.ability ?? ''}
                      onChange={(event) => update({ ability: event.target.value || null })}
                      aria-label="特性"
                      className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
                    >
                      <option value="">（不选）</option>
                      {abilityOptions.map((ability) => (
                        <option key={ability.value} value={ability.value}>
                          {ability.label}
                          {ability.pct != null ? ` · ${ability.pct.toFixed(1)}%` : ''}
                          {ability.value === recommendedAbility ? '　★推荐' : ''}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="space-y-1">
                    <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                      道具
                      {recommendedItem ? (
                        <span className="flex items-center gap-0.5">
                          <ItemIcon
                            src={resolveMediaUrl(recommendedItem.icon_url)}
                            alt={recommendedItem.name}
                          />
                          推荐 {recommendedItem.name}
                          {recommendedItem.pct != null
                            ? ` · ${recommendedItem.pct.toFixed(1)}%`
                            : ''}
                        </span>
                      ) : null}
                    </span>
                    <ItemPicker
                      value={member.item ?? null}
                      onChange={(next) => update({ item: next })}
                      suggestions={data?.legal_items ?? []}
                      conflict={itemConflict}
                    />
                  </div>
                </div>
              </Section>

              <Section title="配点">
                <div className="space-y-2">
                  <div className="space-y-1 sm:max-w-56">
                    <span className="text-[10px] text-muted-foreground">性格</span>
                    <select
                      value={member.nature ?? ''}
                      onChange={(event) => update({ nature: event.target.value || null })}
                      aria-label="性格"
                      className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
                    >
                      <option value="">（不选）</option>
                      {NATURE_KEYS.map((key) => (
                        <option key={key} value={key}>
                          {NATURE_ZH[key] ?? key}（{NATURE_EN[key]}）
                          {NATURE_EFFECT[key] ? ` · ${natureEffectLabel(key)}` : ' · 无增减'}
                        </option>
                      ))}
                    </select>
                    {member.nature ? (
                      <NatureEffect nature={member.nature} />
                    ) : null}
                  </div>
                  <PointsEditor
                    evs={member.evs}
                    pointsKind={pointsKind}
                    onChange={(evs) => update({ evs })}
                  />
                  {pointsKind === 'ev' ? (
                    <IvEditor
                      ivs={member.ivs ?? [31, 31, 31, 31, 31, 31]}
                      onChange={(ivs) => update({ ivs })}
                    />
                  ) : null}
                </div>
              </Section>

              <Section title="外观 / 等级">
                <div className="grid gap-2 sm:grid-cols-4">
                  <label className="space-y-1">
                    <span className="block text-[10px] text-muted-foreground">闪光</span>
                    <select
                      value={member.shiny ? 'yes' : 'no'}
                      onChange={(event) => update({ shiny: event.target.value === 'yes' })}
                      aria-label="闪光"
                      className="h-8 w-full rounded-md border border-input bg-background px-1 text-xs"
                    >
                      <option value="no">否</option>
                      <option value="yes">是</option>
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="block text-[10px] text-muted-foreground">性别</span>
                    <select
                      value={member.gender ?? ''}
                      onChange={(event) =>
                        update({ gender: (event.target.value || null) as 'M' | 'F' | null })
                      }
                      aria-label="性别"
                      className="h-8 w-full rounded-md border border-input bg-background px-1 text-xs"
                    >
                      <option value="">无</option>
                      <option value="M">♂</option>
                      <option value="F">♀</option>
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="block text-[10px] text-muted-foreground">等级</span>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      value={member.level ?? defaultLevel}
                      onChange={(event) => update({ level: Number(event.target.value) })}
                      className="h-8 px-1 text-xs tabular-nums"
                      aria-label="等级"
                    />
                  </label>
                  {/* 极巨化：只在剑盾显示。超极巨化开关只对带 G 形态的物种出现 */}
                  {formatKey === 'swsh' ? (
                    <label className="space-y-1">
                      <span className="block text-[10px] text-muted-foreground">
                        极巨化等级
                      </span>
                      <Input
                        type="number"
                        min={0}
                        max={10}
                        value={member.dynamax_level ?? 10}
                        onChange={(event) => {
                          const next = Math.min(10, Math.max(0, Number(event.target.value) || 0))
                          update({ dynamax_level: next })
                        }}
                        className="h-8 px-1 text-xs tabular-nums"
                        aria-label="极巨化等级"
                      />
                    </label>
                  ) : null}
                  {formatKey === 'swsh' ? (
                    <label className="space-y-1">
                      <span className="block text-[10px] text-muted-foreground">
                        超极巨化
                      </span>
                      <span
                        className={cn(
                          'flex h-8 items-center gap-1.5 rounded-md border border-input bg-background px-2',
                          !data?.can_gigantamax && 'opacity-60',
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={Boolean(member.gigantamax)}
                          disabled={!data?.can_gigantamax}
                          onChange={(event) => update({ gigantamax: event.target.checked })}
                          aria-label="超极巨化"
                          className="size-3.5 accent-(--primary)"
                        />
                        <span className="truncate text-[10px] text-muted-foreground">
                          {data?.can_gigantamax
                            ? (data.gigantamax_move ?? 'G 形态')
                            : '无 G 形态'}
                        </span>
                      </span>
                    </label>
                  ) : null}
                  <label className="space-y-1">
                    <span className="block text-[10px] text-muted-foreground">语言</span>
                    <select
                      value={member.language ?? 'CHS'}
                      onChange={(event) =>
                        update({ language: event.target.value as TeamLanguage })
                      }
                      aria-label="语言"
                      className="h-8 w-full rounded-md border border-input bg-background px-1 text-xs"
                    >
                      {LANGUAGES.map((language) => (
                        <option key={language} value={language}>
                          {language}
                        </option>
                      ))}
                    </select>
                  </label>
                  {formatKey === 'sv' ? (
                    <label className="space-y-1">
                      <span className="block text-[10px] text-muted-foreground">太晶属性</span>
                      <Input
                        value={member.tera_type ?? ''}
                        onChange={(event) => update({ tera_type: event.target.value || null })}
                        placeholder="Fire"
                        aria-label="太晶属性"
                        className="h-8 text-xs"
                      />
                    </label>
                  ) : null}
                </div>
              </Section>

              {isSmeargle ? (
                <p className="rounded-md bg-muted/50 px-2 py-1 text-[10px] text-muted-foreground">
                  图图犬只会「写生」，这里列出它通过写生可以获得的招式（{moveOptions.length} 个）；
                  暗黑洞等少数招式无法写生，已排除。一场对战只能写生 1 个招式。
                </p>
              ) : null}

              <Section
                title="招式"
                hint={`${member.moves.filter(Boolean).length}/${MAX_MOVES} · 按使用率排序`}
                action={
                  member.moves.length > 0 ? (
                    <button
                      type="button"
                      onClick={() => update({ moves: [] })}
                      className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground hover:text-foreground"
                    >
                      <X aria-hidden="true" className="size-3" />
                      清空
                    </button>
                  ) : null
                }
              >
                <ul className="grid gap-1 sm:grid-cols-2">
                  {moveOptions.map((move) => {
                    const value = move.name_en ?? move.name
                    const selected = member.moves.includes(value)
                    const pct = statsBySlug.get(move.slug)
                    const disabled = !selected && member.moves.length >= MAX_MOVES
                    return (
                      <li key={move.slug} className="flex items-stretch gap-1">
                        <button
                          type="button"
                          onClick={() => toggleMove(move)}
                          disabled={disabled}
                          aria-pressed={selected}
                          title={move.name}
                          className={cn(
                            'flex min-w-0 flex-1 items-center gap-1.5 rounded-md border px-1.5 py-1 text-left text-xs transition-colors',
                            selected
                              ? 'border-primary/50 bg-primary/10'
                              : 'border-border hover:bg-muted',
                            disabled && 'opacity-40',
                          )}
                        >
                          {move.type ? (
                            <TypeBadge type={move.type} className="shrink-0 px-1 py-0 text-[9px]" />
                          ) : null}
                          <span className="min-w-0 flex-1 truncate">{move.name}</span>
                          {pct != null ? (
                            <span className="shrink-0 text-[9px] text-muted-foreground tabular-nums">
                              {pct.toFixed(1)}%
                            </span>
                          ) : null}
                        </button>
                        {/* 招式详情在另一个页面，用独立链接而不是把 button 包进 a */}
                        <Link
                          to={moveDetailLink(move.slug)}
                          aria-label={`查看招式 ${move.name}`}
                          title={`查看招式详情：${move.name}`}
                          className="flex w-6 shrink-0 items-center justify-center rounded-md border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-muted hover:text-foreground"
                        >
                          <ExternalLink aria-hidden="true" className="size-3" />
                        </Link>
                      </li>
                    )
                  })}
                  {moveOptions.length === 0 ? (
                    <li className="text-[11px] text-muted-foreground">
                      本地没有该版本可学招式数据。
                    </li>
                  ) : null}
                </ul>
              </Section>
            </>
          )}
        </div>
      ) : null}
    </div>
  )
}

/** 分组标题：小字号标签 + 右侧可选说明 / 操作，统一各段的视觉层级。 */
function Section({
  title,
  hint,
  action,
  children,
}: {
  title: string
  hint?: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
          {title}
        </span>
        {hint ? <span className="text-[10px] text-muted-foreground">{hint}</span> : null}
        {action ? <span className="ml-auto">{action}</span> : null}
      </div>
      {children}
    </section>
  )
}

/** 合法特性按使用率降序；没有统计的排在最后（保持字母序）。 */
function sortAbilities(data: { legal_abilities: TeamOptionUsage[]; recommended: unknown } | undefined) {
  if (!data) return [] as AbilityOption[]
  const rec = data.recommended as
    | { abilities: { slug: string; pct: number }[] }
    | null
    | undefined
  const pctBySlug = new Map((rec?.abilities ?? []).map((item) => [item.slug, item.pct]))
  return (data.legal_abilities ?? [])
    .map((ability) => ({
      value: ability.name_en ?? ability.name,
      label: ability.name,
      pct: pctBySlug.get(ability.slug) ?? null,
    }))
    .sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1))
}

/** 默认特性 = 使用率最高的那个（没有统计时用第一个合法特性）。 */
function topAbility(
  data: { legal_abilities: TeamOptionUsage[]; recommended: unknown } | undefined,
): string | null {
  const sorted = sortAbilities(data)
  return sorted[0]?.value ?? null
}

/** 合法招式按「统计里有使用率的在前、按使用率降序」排列。 */
function sortMoves(
  moves: TeamOptionUsage[],
  recommended: { moves: { slug: string; pct: number }[] } | null | undefined,
) {
  const pctBySlug = new Map((recommended?.moves ?? []).map((item) => [item.slug, item.pct]))
  return [...moves].sort((a, b) => {
    const left = pctBySlug.get(a.slug) ?? -1
    const right = pctBySlug.get(b.slug) ?? -1
    if (left !== right) return right - left
    return a.name.localeCompare(b.name, 'zh-Hans-CN')
  })
}

/** 「套用推荐」：把统计推荐整套写回成员（覆盖当前选择）。 */
function applyRecommendation(
  recommended: {
    abilities: TeamOptionUsage[]
    items: TeamOptionUsage[]
    moves: TeamOptionUsage[]
    spread: { nature: string; points: number[] } | null
  },
  member: TeamMember,
  update: (patch: Partial<TeamMember>) => void,
) {
  update({
    ability: recommended.abilities[0]?.name_en ?? member.ability,
    item: recommended.items[0]?.name_en ?? member.item,
    nature: recommended.spread?.nature ?? member.nature,
    evs: recommended.spread?.points ?? member.evs,
    moves: recommended.moves.slice(0, MAX_MOVES).map((move) => move.name_en ?? move.name),
  })
}

function genderFromRate(rate: number | null | undefined): 'M' | 'F' | null {
  if (rate == null) return null
  if (rate === -1) return null
  if (rate === 0) return 'M'
  if (rate === 8) return 'F'
  return 'F'
}

/**
 * 性格的增减效果：`攻击 ↑ / 特攻 ↓` 这样的彩色标注。
 *
 * 下拉框里的选项文本只能看个大概（部分浏览器会截断），选中后在下方
 * 再明确展示一次，避免「选了固执却不知道加了什么」。
 */
function NatureEffect({ nature }: { nature: string }) {
  const effect = NATURE_EFFECT[nature]
  if (!effect) {
    return (
      <p className="text-[10px] text-muted-foreground">该性格无属性增减（中性）</p>
    )
  }
  return (
    <p className="flex items-center gap-2 text-[10px]">
      <span className="font-medium text-success">
        ▲ {STAT_ZH[effect[0]]}
      </span>
      <span className="font-medium text-destructive">
        ▼ {STAT_ZH[effect[1]]}
      </span>
      <span className="text-muted-foreground">（×1.1 / ×0.9）</span>
    </p>
  )
}

/**
 * 六项配点输入（EV / 能力点）。
 *
 * **允许手动输入任意数字，不自动取整、不偷偷夹紧**：
 * 以前的写法会把输入按 4 取整、越界直接截断到上限，用户看不到自己输错了。
 * 现在原样保留输入，越界在输入框上标红，并在下方汇总里说明原因 ——
 * 最终由保存时的后端校验（`domain/team_rules.py`）兜底拦截。
 */
export function PointsEditor({
  evs,
  pointsKind,
  onChange,
}: {
  evs: number[]
  pointsKind: 'ev' | 'stat_points'
  onChange: (evs: number[]) => void
}) {
  const max = pointsKind === 'stat_points' ? 32 : 252
  const totalMax = pointsKind === 'stat_points' ? 66 : 508
  const label = pointsKind === 'stat_points' ? '能力点' : 'EV'
  const total = evs.reduce((sum, value) => sum + value, 0)

  const setValue = (index: number, raw: string) => {
    // 只保留数字（避免 "12e3"、负号等被 Number() 解释成意外值）；空串按 0
    const digits = raw.replace(/[^0-9]/g, '')
    const next = [...evs]
    next[index] = digits ? Number(digits) : 0
    onChange(next)
  }

  const overSingle = evs.some((value) => value > max)
  const overTotal = total > totalMax

  return (
    <div>
      <p className="mb-1 flex items-center justify-between text-[10px] text-muted-foreground">
        <span>
          {label}（{DOUBLES_STAT_LABELS.join(' / ')}）
        </span>
        <span className={cn('tabular-nums', overTotal && 'font-medium text-destructive')}>
          合计 {total}/{totalMax}
        </span>
      </p>
      <div className="grid grid-cols-3 gap-1 sm:grid-cols-6">
        {DOUBLES_STAT_LABELS.map((statLabel, index) => {
          const value = evs[index] ?? 0
          const invalid = value > max
          return (
            <label key={statLabel} className="space-y-0.5">
              <span className="block text-[9px] text-muted-foreground">{statLabel}</span>
              <Input
                type="number"
                min={0}
                inputMode="numeric"
                value={value}
                onChange={(event) => setValue(index, event.target.value)}
                aria-label={`${statLabel} ${label}`}
                aria-invalid={invalid}
                className={cn(
                  'h-7 px-1 text-xs tabular-nums',
                  invalid && 'border-destructive text-destructive',
                )}
              />
            </label>
          )
        })}
      </div>
      {overSingle || overTotal ? (
        <p className="mt-1 text-[10px] text-destructive">
          {overSingle ? `单项不能超过 ${max}` : null}
          {overSingle && overTotal ? '；' : null}
          {overTotal ? `合计不能超过 ${totalMax}（当前 ${total}）` : null}
        </p>
      ) : null}
    </div>
  )
}

function IvEditor({ ivs, onChange }: { ivs: number[]; onChange: (ivs: number[]) => void }) {
  return (
    <div>
      <p className="mb-1 flex items-center justify-between text-[10px] text-muted-foreground">
        <span>个体值（默认全 31）</span>
        <span className="tabular-nums">0–31</span>
      </p>
      <div className="grid grid-cols-3 gap-1 sm:grid-cols-6">
        {DOUBLES_STAT_LABELS.map((label, index) => (
          <label key={label} className="space-y-0.5">
            <span className="block text-[9px] text-muted-foreground">{label}</span>
            <Input
              type="number"
              min={0}
              max={31}
              value={ivs[index] ?? 31}
              onChange={(event) => {
                const next = [...ivs]
                next[index] = Math.min(31, Math.max(0, Number(event.target.value)))
                onChange(next)
              }}
              className="h-7 px-1 text-xs tabular-nums"
              aria-label={`${label} 个体值`}
            />
          </label>
        ))}
      </div>
    </div>
  )
}
