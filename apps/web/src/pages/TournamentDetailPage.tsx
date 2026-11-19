/**
 * 官方赛事详情页（`/tournaments/:tournamentId`）。
 *
 * 从列表页点赛事名进入，展示：
 *   - 赛事头信息（日期 / 人数 / 规则 / 冠军 / 来源链接）；
 *   - **队伍**：每支队伍的 6 只配置，可复制 Showdown 代码、一键建队；
 *   - **使用率**：由该赛事全部队表重算；
 *   - **名次**：成绩页的名次表（分页）。
 *
 * 一键建队不在这里直接落库：跳转到 `/teams?fromTournament=…&eventTeam=…`，
 * 由建队页载入草稿，用户确认后再保存。
 */

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CircleAlert, ExternalLink, RefreshCw } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { resolveMediaUrl } from '@/features/dex/api'
import { pageItems } from '@/features/dex/pagination'
import { EventTeamCard } from '@/features/tournaments/EventTeamCard'
import { useTournament } from '@/features/tournaments/hooks'
import type { EventTeam, EventUsage, StandingView } from '@/features/tournaments/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const TEAM_PAGE_SIZE = 20
const STANDING_PAGE_SIZE = 50

type DetailTab = 'teams' | 'usage' | 'standings'

export function TournamentDetailPage() {
  const { tournamentId } = useParams<{ tournamentId: string }>()
  const id = Number(tournamentId ?? '') || null
  const detail = useTournament(id)

  if (id == null) {
    return (
      <Alert variant="destructive">
        <CircleAlert aria-hidden="true" />
        <AlertTitle>赛事编号无效</AlertTitle>
        <AlertDescription>请从赛事列表进入。</AlertDescription>
        <AlertAction>
          <Button size="xs" variant="outline" asChild>
            <Link to="/tournaments">返回赛事列表</Link>
          </Button>
        </AlertAction>
      </Alert>
    )
  }

  if (detail.isPending) {
    return (
      <div className="space-y-4">
        <BackLink />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (detail.isError || !detail.data) {
    return (
      <div className="space-y-4">
        <BackLink />
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>无法加载赛事详情</AlertTitle>
          <AlertDescription>
            {detail.error ? describeApiError(detail.error) : '赛事不存在'}
          </AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => void detail.refetch()}>
              <RefreshCw aria-hidden="true" />
              重试
            </Button>
          </AlertAction>
        </Alert>
      </div>
    )
  }

  const { tournament, teams, usage, standings } = detail.data
  const canBuild = Boolean(tournament.format_key)

  return (
    <div className="space-y-4">
      <BackLink />

      <PageHeader
        title={tournament.name}
        description={`${tournament.date} · ${tournament.players} 人 · ${tournament.event_type_label} · ${tournament.ruleset_label}${
          tournament.winner ? ` · 冠军 ${tournament.winner}` : ''
        }`}
        actions={
          tournament.source_url ? (
            <Button size="sm" variant="outline" asChild>
              <a href={tournament.source_url} target="_blank" rel="noreferrer">
                查看来源
                <ExternalLink aria-hidden="true" />
              </a>
            </Button>
          ) : null
        }
      />

      <TournamentBody
        canBuild={canBuild}
        teams={teams}
        usage={usage}
        standings={standings}
        tournamentId={tournament.id}
      />
    </div>
  )
}

function BackLink() {
  return (
    <Button asChild size="sm" variant="ghost" className="-ml-2">
      <Link to="/tournaments">
        <ArrowLeft aria-hidden="true" />
        返回赛事列表
      </Link>
    </Button>
  )
}

function TournamentBody({
  canBuild,
  teams,
  usage,
  standings,
  tournamentId,
}: {
  canBuild: boolean
  teams: EventTeam[]
  usage: EventUsage[]
  standings: StandingView[]
  tournamentId: number
}) {
  const [tab, setTab] = useState<DetailTab>('teams')

  const tabs = [
    ['teams', `队伍 ${teams.length}`],
    ['usage', `使用率 ${usage.length}`],
    ['standings', `名次 ${standings.length}`],
  ] as const

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="赛事详情视图">
          {tabs.map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
              className={cn(
                'rounded-full border px-2.5 py-0.5 text-[11px] font-medium',
                tab === value
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:bg-muted',
              )}
            >
              {label}
            </button>
          ))}
          {!canBuild ? (
            <span className="ml-auto self-center text-[10px] text-muted-foreground">
              该规则本地没有建队数据，只能查看。
            </span>
          ) : null}
        </div>

        {tab === 'teams' ? (
          <TeamsTab teams={teams} tournamentId={tournamentId} canBuild={canBuild} />
        ) : tab === 'usage' ? (
          <UsageTab usage={usage} teamCount={teams.length} />
        ) : (
          <StandingsTab standings={standings} />
        )}
      </CardContent>
    </Card>
  )
}

function TeamsTab({
  teams,
  tournamentId,
  canBuild,
}: {
  teams: EventTeam[]
  tournamentId: number
  canBuild: boolean
}) {
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil(teams.length / TEAM_PAGE_SIZE))
  const visible = useMemo(
    () => teams.slice((page - 1) * TEAM_PAGE_SIZE, page * TEAM_PAGE_SIZE),
    [teams, page],
  )

  if (teams.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        这场赛事没有公开队表（早期赛事常见），可查看名次与使用率。
      </p>
    )
  }

  return (
    <>
      <div className="space-y-2">
        {visible.map((team) => (
          <EventTeamCard
            key={team.id}
            team={team}
            tournamentId={tournamentId}
            canBuild={canBuild}
            defaultOpen={page === 1 && team.rank === 1}
          />
        ))}
      </div>
      {totalPages > 1 ? (
        <Pager page={page} totalPages={totalPages} onChange={setPage} />
      ) : null}
    </>
  )
}

function UsageTab({
  usage,
  teamCount,
}: {
  usage: EventUsage[]
  teamCount: number
}) {
  if (usage.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        没有队表，无法统计赛事使用率。
      </p>
    )
  }
  return (
    <div>
      <p className="mb-2 text-[11px] text-muted-foreground">
        按该赛事全部 {teamCount} 支队伍重算（每队同一物种只计一次）。
      </p>
      <ul className="divide-y divide-border/60 overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[var(--card-glow)]">
        {usage.map((entry) => (
          <li key={entry.species_slug} className="flex items-center gap-2 px-3 py-2 transition-colors hover:bg-primary/[0.045]">
            <span className="w-6 text-right font-mono text-[10px] text-muted-foreground tabular-nums">
              {entry.rank}
            </span>
            {entry.dex_number ? (
              <PokemonSprite
                src={resolveMediaUrl(`/media/sprites/${entry.dex_number}.png`)}
                alt={entry.showdown_name}
                className="size-6 shrink-0"
              />
            ) : null}
            <span className="min-w-0 flex-1 truncate text-xs">
              {entry.dex_number ? (
                <Link
                  to={`/dex/${entry.dex_number}`}
                  className="hover:text-primary hover:underline"
                >
                  {entry.showdown_name}
                </Link>
              ) : (
                entry.showdown_name
              )}
            </span>
            <span className="w-24 shrink-0">
              <span className="block h-1.5 overflow-hidden rounded-full bg-muted">
                <span
                  className="block h-full rounded-full bg-primary"
                  style={{ width: `${Math.min(100, entry.share)}%` }}
                />
              </span>
            </span>
            <span className="w-16 text-right text-[11px] tabular-nums">
              {entry.share.toFixed(2)}%
            </span>
            <span className="w-10 text-right text-[10px] text-muted-foreground tabular-nums">
              {entry.count} 队
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function StandingsTab({ standings }: { standings: StandingView[] }) {
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil(standings.length / STANDING_PAGE_SIZE))
  const visible = standings.slice(
    (page - 1) * STANDING_PAGE_SIZE,
    page * STANDING_PAGE_SIZE,
  )

  if (standings.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">没有名次数据。</p>
  }

  return (
    <div className="space-y-2">
      <ul className="divide-y divide-border/60 overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[var(--card-glow)]">
        {visible.map((row) => (
          <li
            key={`${row.rank}-${row.player}`}
            className="flex items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-primary/[0.045]"
          >
            <span className="w-7 text-right font-mono text-[10px] text-muted-foreground tabular-nums">
              {row.rank}
            </span>
            <span className="min-w-0 flex-1 truncate font-medium">{row.player}</span>
            <span className="hidden truncate text-[10px] text-muted-foreground sm:block">
              {row.species.join(' / ')}
            </span>
            {row.team_id ? (
              <Badge variant="outline" className="text-[9px]">
                有队表
              </Badge>
            ) : null}
          </li>
        ))}
      </ul>
      {totalPages > 1 ? (
        <Pager page={page} totalPages={totalPages} onChange={setPage} />
      ) : null}
    </div>
  )
}

function Pager({
  page,
  totalPages,
  onChange,
}: {
  page: number
  totalPages: number
  onChange: (page: number) => void
}) {
  return (
    <div className="flex items-center justify-center gap-1">
      <Button
        size="xs"
        variant="outline"
        disabled={page <= 1}
        onClick={() => onChange(Math.max(1, page - 1))}
      >
        上一页
      </Button>
      {pageItems(page, totalPages).map((item, index) =>
        item === 'ellipsis' ? (
          <span key={`e${index}`} className="px-1 text-xs text-muted-foreground">
            …
          </span>
        ) : (
          <Button
            key={item}
            size="xs"
            variant={item === page ? 'default' : 'outline'}
            onClick={() => onChange(item)}
          >
            {item}
          </Button>
        ),
      )}
      <Button
        size="xs"
        variant="outline"
        disabled={page >= totalPages}
        onClick={() => onChange(Math.min(totalPages, page + 1))}
      >
        下一页
      </Button>
    </div>
  )
}
