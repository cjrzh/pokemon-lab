/**
 * 赛事队表卡片：展示 6 只配置、复制 Showdown 代码、一键建队。
 *
 * 一键建队不在这里直接调用后端：它通过 URL 参数把 tournament / team 交给
 * `/teams` 页面，由建队页拉取草稿并载入编辑器 —— 这样用户还能继续修改，
 * 也不会把「查看赛事」和「写队列」两个动作绑死。
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, CircleAlert, Copy, Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { resolveMediaUrl } from '@/features/dex/api'
import type { EventTeam } from '@/features/tournaments/api'
import { cn } from '@/lib/utils'

export function EventTeamCard({
  team,
  tournamentId,
  canBuild,
  rank,
  defaultOpen = false,
}: {
  team: EventTeam
  tournamentId: number
  /** 该赛事的规则能不能一键建队（本地没有该版本时只能看）。 */
  canBuild: boolean
  /** 名次徽章（与队伍卡片上的名次重复时可不传）。 */
  rank?: number
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(team.showdown_text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // 剪贴板不可用：保留文本在展开区，用户可手动全选
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[var(--card-glow)] transition-colors hover:border-primary/20">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <Badge variant="outline" className="font-mono text-[10px] tabular-nums">
          {rank ?? team.rank}
        </Badge>
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{team.player}</span>
        {team.problems.length > 0 ? (
          <span
            className="inline-flex items-center gap-1 text-[10px] text-warning"
            title={team.problems.join('；')}
          >
            <CircleAlert aria-hidden="true" className="size-3" />
            {team.problems.length} 只未知
          </span>
        ) : null}
        {team.validation?.issues?.length ? (
          <span
            className="inline-flex items-center gap-1 text-[10px] text-warning"
            title={`源站数据与本地规则不一致（不影响复制）：${team.validation.issues.join('；')}`}
          >
            <CircleAlert aria-hidden="true" className="size-3" />
            {team.validation.issues.length} 处待核对
          </span>
        ) : null}
        <Button size="xs" variant="outline" onClick={() => void copy()}>
          {copied ? <Sparkles aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copied ? '已复制' : 'Showdown'}
        </Button>
        {canBuild ? (
          <Button size="xs" asChild>
            <Link
              to={`/teams?fromTournament=${tournamentId}&eventTeam=${team.id}`}
              title="把这支队伍载入建队页（EV / IV 赛事未公开，配点为 0）"
            >
              一键建队
            </Link>
          </Button>
        ) : null}
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={open ? '收起队表' : '展开队表'}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          <ChevronDown
            aria-hidden="true"
            className={cn('transition-transform', open && 'rotate-180')}
          />
        </Button>
      </div>

      {open ? (
        <div className="space-y-1.5 border-t px-3 py-2">
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {team.members.map((member) => (
              <TeamMemberLine key={member.position} member={member} />
            ))}
          </ul>
          {team.validation?.issues?.length ? (
            <ul className="list-disc space-y-0.5 pl-4 text-[10px] text-warning">
              {team.validation.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          ) : null}
          <details className="text-[11px] text-muted-foreground">
            <summary className="cursor-pointer">
              Showdown 代码（默认 100 级 / 闪光，不含 EV / IV）
            </summary>
            <pre className="mt-1 max-h-56 overflow-auto rounded-md bg-muted/50 p-2 font-mono text-[10px] leading-snug whitespace-pre-wrap">
              {team.showdown_text}
            </pre>
          </details>
        </div>
      ) : null}
    </div>
  )
}

function TeamMemberLine({
  member,
}: {
  member: EventTeam['members'][number]
}) {
  const sprite = member.dex_number
    ? `/media/sprites/${member.dex_number}.png`
    : null
  return (
    <li className="rounded-lg border bg-background/60 px-2 py-1.5">
      <div className="flex items-center gap-1.5">
        {sprite ? (
          <PokemonSprite
            src={resolveMediaUrl(sprite)}
            alt={member.showdown_name}
            className="size-6 shrink-0"
          />
        ) : (
          <CircleAlert aria-hidden="true" className="size-4 shrink-0 text-warning" />
        )}
        <span className="truncate text-xs font-medium">{member.showdown_name}</span>
        {member.gigantamax ? (
          <Badge variant="secondary" className="shrink-0 text-[9px]">
            超极巨化
          </Badge>
        ) : null}
        {member.item ? (
          <span className="truncate text-[10px] text-muted-foreground">@ {member.item}</span>
        ) : null}
      </div>
      <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
        {[
          member.ability,
          member.gigantamax ? 'Gigantamax: Yes' : null,
          member.nature ? `${member.nature} 性格` : null,
          member.tera_type ? `太晶 ${member.tera_type}` : null,
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
      <p className="truncate text-[10px]">{member.moves.join(' / ')}</p>
    </li>
  )
}
