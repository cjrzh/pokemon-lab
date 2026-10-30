/**
 * Showdown 代码生成面板（双打辅助卡片内）。
 *
 * 默认值来自统计推荐：性格 / 配点 / 特性 / 道具 / 招式；IV 全 31、闪光、CHS、
 * 雌性（无性别的宝可梦自动去掉性别标记）。所有字段都可手动改，代码实时重算。
 *
 * 交换前缀（!tradeSV 等）由格式定义给出，放在代码第一行；冠军不输出前缀。
 */

import { useMemo, useState } from 'react'
import { Check, Copy, RotateCcw, Terminal } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  DOUBLES_STAT_LABELS,
  pointsUnit,
  type DoublesFormatBlock,
  type DoublesProfile,
} from '@/features/doubles/api'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import {
  LANGUAGES,
  NATURE_EN,
  NATURE_ZH,
  SHOWDOWN_STAT_SHORT,
  defaultDraft,
  normalizeDraft,
  renderShowdown,
  usageEnglish,
  usageOptionLabel,
  type Gender,
  type Language,
  type ShowdownDraft,
} from '@/features/doubles/showdown'
import { cn } from '@/lib/utils'

const NATURE_KEYS = Object.keys(NATURE_EN)

export function ShowdownExport({
  format,
  profile,
  genderRate,
}: {
  format: DoublesFormatBlock
  profile: DoublesProfile
  genderRate: number | null
}) {
  const initial = useMemo(
    () => normalizeDraft(defaultDraft(format, profile, genderRate), format.points_kind),
    [format, profile, genderRate],
  )
  const [draft, setDraft] = useState<ShowdownDraft>(initial)
  const [copied, setCopied] = useState(false)

  const text = useMemo(
    () =>
      renderShowdown(draft, {
        tradePrefix: format.trade_prefix,
        includeTera: format.key === 'sv',
      }),
    [draft, format],
  )

  const update = (patch: Partial<ShowdownDraft>) =>
    setDraft((current) => normalizeDraft({ ...current, ...patch }, format.points_kind))

  const setEv = (index: number, value: number) => {
    const evs = [...draft.evs]
    evs[index] = value
    update({ evs })
  }

  const setIv = (index: number, value: number) => {
    if (!draft.ivs) return
    const ivs = [...draft.ivs]
    ivs[index] = value
    update({ ivs })
  }

  const setMove = (index: number, value: string) => {
    const moves = [...draft.moves]
    moves[index] = value
    update({ moves: moves.slice(0, 4) })
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // 剪贴板被浏览器拒绝时，用户仍可手动选中文本复制
    }
  }

  const maxEv = format.points_kind === 'stat_points' ? 32 : 252

  // 招式英文名 → 属性：选中值写在代码里是英文，这里用它反查徽章颜色。
  const moveTypes = useMemo(() => {
    const map = new Map<string, string>()
    for (const usage of profile.moves) {
      if (usage.type) map.set(usageEnglish(usage), usage.type)
    }
    return map
  }, [profile.moves])

  return (
    <div className="rounded-lg border p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <p className="flex items-center gap-1.5 text-xs font-medium">
          <Terminal aria-hidden="true" className="size-3.5 text-primary" />
          Showdown 代码
        </p>
        {format.trade_prefix ? (
          <Badge variant="secondary" className="font-mono text-[10px]">
            {format.trade_prefix}
          </Badge>
        ) : (
          <Badge variant="outline" className="text-[10px]">
            无交换前缀
          </Badge>
        )}
        <span className="text-[11px] text-muted-foreground">
          默认：推荐配装 · IV 全 31 · 闪光 · CHS · 雌性
        </span>
        <div className="ml-auto flex items-center gap-1">
          <Button size="xs" variant="ghost" onClick={() => setDraft(initial)}>
            <RotateCcw aria-hidden="true" />
            重置
          </Button>
          <Button size="xs" variant="outline" onClick={() => void copy()}>
            {copied ? (
              <Check aria-hidden="true" className="text-success" />
            ) : (
              <Copy aria-hidden="true" />
            )}
            {copied ? '已复制' : '复制'}
          </Button>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        {/* ---------- 可编辑字段 ---------- */}
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <Field label="特性（按使用率排序）">
              <UsageSelect
                value={draft.ability}
                ariaLabel="特性"
                options={profile.abilities.map((usage) => ({
                  value: usageEnglish(usage),
                  label: usageOptionLabel(usage),
                }))}
                onChange={(value) => update({ ability: value })}
              />
            </Field>
            <Field label="道具">
              <Input
                value={draft.item}
                onChange={(event) => update({ item: event.target.value })}
                className="h-7 text-xs"
              />
            </Field>
            <Field label="性格">
              <select
                value={draft.nature}
                onChange={(event) => update({ nature: event.target.value })}
                className="h-7 w-full rounded-md border border-input bg-background px-2 text-xs"
                aria-label="性格"
              >
                {NATURE_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {NATURE_ZH[key] ?? key}（{NATURE_EN[key]}）
                  </option>
                ))}
              </select>
            </Field>
            <Field label="等级">
              <Input
                type="number"
                min={1}
                max={100}
                value={draft.level}
                onChange={(event) => update({ level: Number(event.target.value) })}
                className="h-7 text-xs tabular-nums"
              />
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
            <Field label="性别">
              <div className="flex items-center gap-1" role="group" aria-label="性别">
                {(
                  [
                    { value: 'M', label: '雄性' },
                    { value: 'F', label: '雌性' },
                    { value: null, label: '无' },
                  ] as const
                ).map((option) => (
                  <Toggle
                    key={option.label}
                    active={draft.gender === option.value}
                    onClick={() => update({ gender: option.value as Gender | null })}
                  >
                    {option.label}
                  </Toggle>
                ))}
              </div>
            </Field>

            <Field label="语言">
              <select
                value={draft.language}
                onChange={(event) => update({ language: event.target.value as Language })}
                className="h-7 rounded-md border border-input bg-background px-2 text-xs"
                aria-label="语言"
              >
                {LANGUAGES.map((language) => (
                  <option key={language} value={language}>
                    {language}
                  </option>
                ))}
              </select>
            </Field>

            <label className="flex items-center gap-1.5 text-muted-foreground">
              <input
                type="checkbox"
                checked={draft.shiny}
                onChange={(event) => update({ shiny: event.target.checked })}
                className="size-3.5 accent-(--primary)"
              />
              闪光
            </label>

            {format.key === 'sv' ? (
              <Field label="太晶属性">
                <Input
                  value={draft.teraType ?? ''}
                  onChange={(event) => update({ teraType: event.target.value || null })}
                  className="h-7 w-24 text-xs"
                  placeholder="Fire"
                />
              </Field>
            ) : null}
          </div>

          {/* ---------- 配点 ---------- */}
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              配点（{pointsUnit(format.points_kind)}）
              <span className="text-[10px]">每项 0–{maxEv}</span>
            </p>
            <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-6">
              {DOUBLES_STAT_LABELS.map((label, index) => (
                <label key={label} className="space-y-0.5">
                  <span className="block text-[10px] text-muted-foreground">{label}</span>
                  <Input
                    type="number"
                    min={0}
                    max={maxEv}
                    step={format.points_kind === 'stat_points' ? 1 : 4}
                    value={draft.evs[index] ?? 0}
                    onChange={(event) => setEv(index, Number(event.target.value))}
                    className="h-7 px-1.5 text-xs tabular-nums"
                    aria-label={`${label} ${pointsUnit(format.points_kind)}`}
                  />
                </label>
              ))}
            </div>
          </div>

          {/* ---------- 个体值（Champions 没有） ---------- */}
          {draft.ivs ? (
            <div>
              <p className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                个体值（默认全 31）
                <span className="text-[10px]">0–31</span>
              </p>
              <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-6">
                {DOUBLES_STAT_LABELS.map((label, index) => (
                  <label key={label} className="space-y-0.5">
                    <span className="block text-[10px] text-muted-foreground">{label}</span>
                    <Input
                      type="number"
                      min={0}
                      max={31}
                      value={draft.ivs?.[index] ?? 31}
                      onChange={(event) => setIv(index, Number(event.target.value))}
                      className="h-7 px-1.5 text-xs tabular-nums"
                      aria-label={`${label} 个体值`}
                    />
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground">
              冠军没有个体值系统：代码只输出能力点，不输出 IV。
            </p>
          )}

          {/* ---------- 招式 ---------- */}
          <div>
            <p className="mb-1 text-xs text-muted-foreground">招式（最多 4 个）</p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {Array.from({ length: 4 }, (_, index) => {
                const current = draft.moves[index] ?? ''
                const type = current ? moveTypes.get(current) : undefined
                return (
                  <div key={index} className="flex items-center gap-1.5">
                    {type ? (
                      <TypeBadge type={type} className="shrink-0 px-1.5 py-0 text-[10px]" />
                    ) : (
                      <span aria-hidden="true" className="w-7 shrink-0" />
                    )}
                    <div className="min-w-0 flex-1">
                      <UsageSelect
                        value={current}
                        ariaLabel={`招式 ${index + 1}`}
                        placeholder={`招式 ${index + 1}（不填）`}
                        options={profile.moves.map((usage) => ({
                          value: usageEnglish(usage),
                          label: usageOptionLabel(usage),
                        }))}
                        onChange={(value) => setMove(index, value)}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* ---------- 生成结果 ---------- */}
        <div className="min-w-0">
          <pre className="h-full min-h-40 overflow-auto rounded-lg bg-muted/60 p-2.5 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
            {text}
          </pre>
          <p className="mt-1.5 text-[10px] text-muted-foreground">
            {format.trade_prefix
              ? `第一行是交换机器人的命令；代码中的 ${pointsUnit(format.points_kind)} 与该格式一致。`
              : '冠军格式没有交换前缀，可直接作为 Showdown 队伍导入。'}
            {format.key === 'sv' ? ' 朱紫包含太晶属性行。' : ''}
            {' '}IV 全 31 时按 Showdown 惯例省略 IV 行。
          </p>
        </div>
      </div>

      {/* 六项短名说明，避免用户不认识 Atk/SpA 等缩写 */}
      <p className="mt-2 text-[10px] text-muted-foreground">
        Showdown 缩写：{SHOWDOWN_STAT_SHORT.join(' / ')} 对应{' '}
        {DOUBLES_STAT_LABELS.join(' / ')}。
      </p>
    </div>
  )
}

/**
 * 使用率下拉框：选项按统计里的推荐比例（使用率降序）排列，标签为「中文（English）· 比例」，
 * 但写进 Showdown 代码的始终是英文值。
 */
function UsageSelect({
  value,
  options,
  onChange,
  ariaLabel,
  placeholder,
}: {
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
  ariaLabel: string
  placeholder?: string
}) {
  // 草稿里可能有统计之外的旧值（例如切换版本后）：保留它，避免下拉框显示空白。
  // 招式下拉额外提供空选项，允许只带 1–3 个招式。
  const known = options.some((option) => option.value === value)
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={ariaLabel}
      className="h-7 w-full min-w-0 rounded-md border border-input bg-background px-2 text-xs"
    >
      {value && !known ? <option value={value}>{value}</option> : null}
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-[10px] text-muted-foreground">{label}</span>
      {children}
    </label>
  )
}

function Toggle({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-md border px-1.5 py-0.5 text-[11px] transition-colors',
        active
          ? 'border-primary/40 bg-primary/10 font-medium text-primary'
          : 'border-border text-muted-foreground hover:bg-muted',
      )}
    >
      {children}
    </button>
  )
}
