/**
 * 双打对战辅助卡片：按格式切换，展示排名 / 使用率、推荐配置、备选配点与常见队友。
 *
 * 布局顺序（个人使用习惯优先）：
 *   1. 格式切换 + 统计月份与等级线（数据是快照，必须显眼）
 *   2. 使用率概览：排名、使用率、样本
 *   3. 推荐配置：性格 / 配点 / 特性 / 道具 / 招式（默认展开）
 *   4. 备选配点、道具、招式、太晶属性、队友（折叠）
 *
 * 多形态（如 Charizard / Charizard-Mega-Y）在同一格式下按使用率降序，
 * 用次级标签切换；形态不影响图鉴编号。
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CircleAlert,
  ChevronDown,
  RefreshCw,
  Sparkles,
  Swords,
  Users,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ItemIcon } from '@/features/dex/components/ItemIcon'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

import {
  DOUBLES_STAT_LABELS,
  formatMonth,
  formatPct,
  pointsUnit,
  type DoublesFormatBlock,
  type DoublesProfile,
  type DoublesUsage,
  type PointsKind,
} from './api'
import { useDoubles } from './hooks'
import { ShowdownExport } from './ShowdownExport'
import {
  pointsScale,
  recommendedBuild,
  spreadSummary,
  teammateLabel,
} from './recommendation'

export function DoublesCard({
  dexNumber,
  genderRate = null,
}: {
  dexNumber: number
  /** 图鉴里的雌性比例；用于生成 Showdown 代码时决定默认性别。 */
  genderRate?: number | null
}) {
  const query = useDoubles(dexNumber)
  const [formatKey, setFormatKey] = useState<string | null>(null)

  if (query.isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Swords aria-hidden="true" className="size-4 text-muted-foreground" />
            双打对战辅助
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </CardContent>
      </Card>
    )
  }

  if (query.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Swords aria-hidden="true" className="size-4 text-muted-foreground" />
            双打对战辅助
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <CircleAlert aria-hidden="true" className="size-4" />
            {describeApiError(query.error)}
          </p>
          <Button size="sm" variant="outline" onClick={() => void query.refetch()}>
            <RefreshCw aria-hidden="true" />
            重试
          </Button>
        </CardContent>
      </Card>
    )
  }

  const data = query.data
  if (data.formats.length === 0) {
    return (
      <SimpleHint
        title="双打对战辅助"
        description="尚未导入双打统计数据。运行 scripts/sync_doubles.py 后即可在此查看推荐配置。"
      />
    )
  }

  const active =
    data.formats.find((format) => format.key === formatKey) ??
    data.formats.find((format) => format.profiles.length > 0) ??
    data.formats[0]

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Swords aria-hidden="true" className="size-4 text-muted-foreground" />
              双打对战辅助
            </CardTitle>
            <CardDescription>
              来自 Smogon 公开使用率统计：推荐性格 / 配点 / 特性 / 道具 / 招式与出场率。
              统计为月度快照，不是实时环境。
            </CardDescription>
          </div>
          <Badge variant="outline" className="shrink-0">
            {active.month} · cutoff {active.cutoff}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ---------- 格式切换 ---------- */}
        <div
          className="flex flex-wrap gap-1.5"
          role="group"
          aria-label="选择双打格式"
        >
          {data.formats.map((format) => {
            const isActive = format.key === active.key
            const empty = !format.profiles.length
            return (
              <button
                key={format.key}
                type="button"
                onClick={() => setFormatKey(format.key)}
                aria-pressed={isActive}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  isActive
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
                  empty && !isActive && 'opacity-60',
                )}
              >
                {format.short_label}
                {empty ? (
                  <span className="text-[10px] opacity-80">无数据</span>
                ) : (
                  <span className="text-[10px] tabular-nums opacity-80">
                    {format.profiles.length}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {/* key 让切换格式时重置形态选择，避免沿用上一个格式的下标 */}
        <FormatBody key={active.key} format={active} genderRate={genderRate} />

        <p className="text-[11px] leading-relaxed text-muted-foreground">
          统计：{active.label} · {formatMonth(active.month)} · Smogon 等级线 {active.cutoff}
          以上 · 共 {active.battles.toLocaleString()} 场对战。
          {active.note ? ` ${active.note}` : ''}
          {active.source_url ? (
            <>
              {' '}
              <a
                href={active.source_url}
                target="_blank"
                rel="noreferrer"
                className="underline underline-offset-2 hover:text-foreground"
              >
                数据原文
              </a>
            </>
          ) : null}
          。个体值不在 Smogon 统计中，页面显示的是按配点与招式推断的建议值。
        </p>
      </CardContent>
    </Card>
  )
}

function FormatBody({
  format,
  genderRate,
}: {
  format: DoublesFormatBlock
  genderRate: number | null
}) {
  const [profileIndex, setProfileIndex] = useState(0)

  if (!format.profiles.length) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        该格式没有这只宝可梦的统计数据。可能是它不在该作品的可用名单里，
        或出场率低于统计下限。
      </div>
    )
  }

  const profile = format.profiles[Math.min(profileIndex, format.profiles.length - 1)]
  return (
    <div className="space-y-4">
      {format.profiles.length > 1 ? (
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="选择形态">
          <span className="text-xs text-muted-foreground">形态：</span>
          {format.profiles.map((item, index) => (
            <button
              key={item.showdown_name}
              type="button"
              onClick={() => setProfileIndex(index)}
              aria-pressed={index === profileIndex}
              className={cn(
                'rounded-md border px-2 py-0.5 text-[11px] transition-colors',
                index === profileIndex
                  ? 'border-primary/40 bg-primary/10 font-medium text-primary'
                  : 'border-border text-muted-foreground hover:bg-muted',
              )}
            >
              {item.showdown_name}
              <span className="ml-1 tabular-nums opacity-70">
                {item.usage != null ? `${item.usage.toFixed(1)}%` : '—'}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          形态 / 统计名：<span className="text-foreground">{profile.showdown_name}</span>
        </p>
      )}

      <ProfileBody profile={profile} pointsKind={format.points_kind} />

      {/* key：切换形态时用该形态的推荐值重新初始化草稿 */}
      <ShowdownExport
        key={profile.showdown_name}
        format={format}
        profile={profile}
        genderRate={genderRate}
      />
    </div>
  )
}

function ProfileBody({ profile, pointsKind }: { profile: DoublesProfile; pointsKind: PointsKind }) {
  const build = useMemo(() => recommendedBuild(profile), [profile])
  const topSpread = build.nature

  return (
    <div className="space-y-3">
      {/* ---------- 使用率概览 ---------- */}
      <div className="grid grid-cols-3 gap-2 rounded-lg bg-muted/50 p-3">
        <Stat label="使用率排名" value={profile.rank != null ? `#${profile.rank}` : '—'} />
        <Stat
          label="出场率"
          value={profile.usage != null ? formatPct(profile.usage) : '—'}
          highlight={profile.usage != null && profile.usage >= 10}
        />
        <Stat label="样本数" value={profile.raw_count.toLocaleString()} />
      </div>

      {/* ---------- 推荐配置 ---------- */}
      <div className="rounded-lg border p-3">
        <p className="mb-2 flex flex-wrap items-center gap-2 text-xs font-medium">
          <Sparkles aria-hidden="true" className="size-3.5 text-primary" />
          推荐配置
          <span className="font-normal text-muted-foreground">
            按使用率最高的组合整理
          </span>
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2 text-sm">
            <MetaRow label="性格" value={topSpread?.nature_label ?? '—'} />
            <MetaRow
              label="特性"
              value={build.ability?.name ?? '—'}
              suffix={build.ability ? formatPct(build.ability.pct) : undefined}
            />
            <MetaRow
              label="道具"
              value={build.item?.name ?? '—'}
              suffix={build.item ? formatPct(build.item.pct) : undefined}
              icon={
                build.item?.icon_url ? (
                  <ItemIcon
                    src={resolveMediaUrl(build.item.icon_url)}
                    alt={build.item.name}
                    className="size-4"
                  />
                ) : undefined
              }
            />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">招式</p>
            <ul className="mt-1 space-y-1">
              {build.moves.map((move) => (
                <li key={move.slug} className="flex items-center gap-1.5 text-sm">
                  {move.type ? (
                    <TypeBadge type={move.type} className="shrink-0 px-1.5 py-0 text-[10px]" />
                  ) : null}
                  <span className="min-w-0 flex-1 truncate">{move.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                    {formatPct(move.pct)}
                  </span>
                </li>
              ))}
              {build.moves.length === 0 ? <li className="text-sm text-muted-foreground">—</li> : null}
            </ul>
          </div>
        </div>

        {/* ---------- 配点 ---------- */}
        {topSpread ? (
          <div className="mt-3 border-t pt-3">
            <p className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>配点（{pointsUnit(pointsKind)}）</span>
              <span className="tabular-nums text-foreground">{topSpread.points.join(' / ')}</span>
              <span className="tabular-nums">· {formatPct(topSpread.pct)} 的使用率</span>
            </p>
            <PointsBars points={topSpread.points} kind={pointsKind} />
          </div>
        ) : null}

        {/* ---------- 个体值建议 ---------- */}
        {profile.ivs ? (
          <div className="mt-3 rounded-md bg-muted/60 p-2 text-xs">
            <p className="flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary" className="text-[10px]">
                推断 · 非数据源字段
              </Badge>
              建议iv：
              {DOUBLES_STAT_LABELS.map((label, index) => (
                <span key={label} className="tabular-nums">
                  {label} {profile.ivs?.ivs[ivKeys[index]] ?? 31}
                </span>
              ))}
            </p>
            {profile.ivs.reasons.length > 0 ? (
              <ul className="mt-1 list-disc pl-4 text-muted-foreground">
                {profile.ivs.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-muted-foreground">默认满个体值（31）。</p>
            )}
          </div>
        ) : null}
      </div>

      {/* ---------- 备选与细节 ---------- */}
      <div className="grid gap-3 sm:grid-cols-2">
        <CollapsibleSection title="其他配点" count={profile.spreads.length - 1}>
          <ul className="space-y-1.5">
            {profile.spreads.slice(1, 7).map((spread) => (
              <li key={`${spread.nature}-${spread.points.join('-')}`}>
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="tabular-nums">{spreadSummary(spread, pointsKind)}</span>
                  <span className="text-muted-foreground tabular-nums">{formatPct(spread.pct)}</span>
                </div>
                <div className="mt-1 flex gap-0.5">
                  {DOUBLES_STAT_LABELS.map((label, index) => (
                    <span
                      key={label}
                      title={`${label} ${spread.points[index] ?? 0}`}
                      className="h-1 flex-1 overflow-hidden rounded-full bg-muted"
                    >
                      <span
                        className="block h-full rounded-full bg-primary/70"
                        style={{
                          width: `${Math.min(100, ((spread.points[index] ?? 0) / pointsScale(pointsKind)) * 100)}%`,
                        }}
                      />
                    </span>
                  ))}
                </div>
              </li>
            ))}
            {profile.spreads.length <= 1 ? (
              <li className="text-xs text-muted-foreground">没有其他达到统计门槛的配点。</li>
            ) : null}
          </ul>
        </CollapsibleSection>

        <CollapsibleSection title="其他道具" count={profile.items.length - 1}>
          <UsageList items={profile.items.slice(1, 8)} />
        </CollapsibleSection>

        <CollapsibleSection title="全部招式" count={profile.moves.length} defaultOpen>
          <UsageList items={profile.moves} />
        </CollapsibleSection>

        {profile.tera_types.length > 0 ? (
          <CollapsibleSection title="太晶属性" count={profile.tera_types.length} defaultOpen>
            <ul className="flex flex-wrap gap-1.5">
              {profile.tera_types.map((tera) => (
                <li key={tera.type} className="inline-flex items-center gap-1">
                  <TypeBadge type={tera.type} className="px-1.5 py-0 text-[10px]" />
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {formatPct(tera.pct)}
                  </span>
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        ) : null}
      </div>

      <CollapsibleSection
        title="常见队友"
        count={profile.teammates.length}
        defaultOpen
        icon={<Users aria-hidden="true" className="size-3.5" />}
      >
        <ul className="flex flex-wrap gap-1.5">
          {profile.teammates.slice(0, 12).map((teammate) => {
            const label = teammateLabel(teammate)
            const content = (
              <>
                <span className="font-medium">{label}</span>
                <span className="text-[10px] text-muted-foreground tabular-nums">
                  {formatPct(teammate.pct)}
                </span>
              </>
            )
            return (
              <li key={teammate.showdown_name}>
                {teammate.dex_number != null ? (
                  <Link
                    to={`/dex/${teammate.dex_number}`}
                    className="inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs transition-colors hover:border-primary/40 hover:bg-muted"
                  >
                    {content}
                  </Link>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs">
                    {content}
                  </span>
                )}
              </li>
            )
          })}
          {profile.teammates.length === 0 ? (
            <li className="text-xs text-muted-foreground">没有达到统计门槛的队友数据。</li>
          ) : null}
        </ul>
      </CollapsibleSection>
    </div>
  )
}

/** 个体值字段顺序（与后端 `stat_keys` 一致）。 */
const ivKeys = ['hp', 'attack', 'defense', 'special-attack', 'special-defense', 'speed'] as const

function Stat({
  label,
  value,
  highlight = false,
}: {
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={cn('text-lg font-semibold tabular-nums', highlight && 'text-primary')}>
        {value}
      </p>
    </div>
  )
}

function MetaRow({
  label,
  value,
  suffix,
  icon,
}: {
  label: string
  value: string
  suffix?: string
  /** 可选前置图标（目前用于道具）。 */
  icon?: React.ReactNode
}) {
  return (
    <p className="flex items-baseline justify-between gap-2">
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className="flex min-w-0 flex-1 items-center justify-end gap-1 truncate text-right font-medium">
        {icon}
        <span className="min-w-0 truncate">{value}</span>
        {suffix ? (
          <span className="shrink-0 text-[10px] font-normal text-muted-foreground tabular-nums">
            {suffix}
          </span>
        ) : null}
      </span>
    </p>
  )
}

function PointsBars({ points, kind }: { points: number[]; kind: PointsKind }) {
  const scale = pointsScale(kind)
  return (
    <ul className="space-y-1">
      {DOUBLES_STAT_LABELS.map((label, index) => {
        const value = points[index] ?? 0
        return (
          <li key={label} className="flex items-center gap-2 text-[11px]">
            <span className="w-7 shrink-0 text-muted-foreground">{label}</span>
            <span className="w-7 shrink-0 text-right font-medium tabular-nums">{value}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <span
                className="block h-full rounded-full bg-primary"
                style={{ width: `${Math.min(100, (value / scale) * 100)}%` }}
              />
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function UsageList({ items }: { items: DoublesUsage[] }) {
  if (items.length === 0) {
    return <p className="text-xs text-muted-foreground">没有更多达到统计门槛的条目。</p>
  }
  const max = Math.max(...items.map((item) => item.pct))
  return (
    <ul className="space-y-1">
      {items.map((item) => (
        <li key={item.slug} className="flex items-center gap-2 text-xs">
          {/* 招式带属性徽章、道具带图标；两者互斥，样式与招式列表页一致 */}
          {item.type ? (
            <TypeBadge type={item.type} className="shrink-0 px-1.5 py-0 text-[10px]" />
          ) : item.icon_url ? (
            <ItemIcon
              src={resolveMediaUrl(item.icon_url)}
              alt={item.name}
              className="size-4"
            />
          ) : null}
          <span className="min-w-0 flex-1 truncate">{item.name}</span>
          <span className="h-1 w-12 shrink-0 overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-primary/60"
              style={{ width: `${max > 0 ? (item.pct / max) * 100 : 0}%` }}
            />
          </span>
          <span className="w-12 shrink-0 text-right text-muted-foreground tabular-nums">
            {formatPct(item.pct)}
          </span>
        </li>
      ))}
    </ul>
  )
}

function CollapsibleSection({
  title,
  count,
  children,
  defaultOpen = false,
  icon,
}: {
  title: string
  count: number
  children: React.ReactNode
  defaultOpen?: boolean
  icon?: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const empty = count <= 0
  return (
    <div className="rounded-lg border">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        disabled={empty}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs font-medium transition-colors hover:bg-muted/50 disabled:cursor-default disabled:hover:bg-transparent"
      >
        {icon ?? null}
        {title}
        <span className="text-[10px] font-normal text-muted-foreground tabular-nums">{count}</span>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            'ml-auto size-3.5 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>
      {open && !empty ? <div className="border-t px-3 py-2">{children}</div> : null}
    </div>
  )
}

function SimpleHint({ title, description }: { title: string; description: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Swords aria-hidden="true" className="size-4 text-muted-foreground" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
    </Card>
  )
}
