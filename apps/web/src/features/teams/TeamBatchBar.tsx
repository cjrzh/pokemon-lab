/**
 * 批量修改队伍成员（闪光 / 等级 / 性别）。
 *
 * 只对**当前草稿**生效：改动算未保存内容，用户确认后再点保存落库。
 * 合法性判断在后端（`domain/team_rules.py`）：性别不是自由选择的 —— 尼多朗只能雄性、
 * 尼多兰只能雌性、超梦等无性别 —— 不合法的成员保持原样，这里如实展示 `skipped`。
 */

import { useState } from 'react'
import { CircleAlert, Layers, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useBatchTeamMembers } from '@/features/teams/hooks'
import type { TeamMember } from '@/features/teams/api'
import { describeApiError } from '@/lib/apiClient'

export function TeamBatchBar({
  members,
  onApplied,
}: {
  members: TeamMember[]
  /** 批量结果交回页面（替换草稿成员）。 */
  onApplied: (members: TeamMember[], skipped: string[]) => void
}) {
  const batch = useBatchTeamMembers()
  // 批量设置默认 100 级（绝大多数对战配置按满级处理）
  const [level, setLevel] = useState('100')
  const [error, setError] = useState<string | null>(null)

  const disabled = members.length === 0 || batch.isPending

  const run = async (patch: {
    shine?: boolean
    level?: number | null
    gender?: 'M' | 'F' | null
  }) => {
    setError(null)
    try {
      const result = await batch.mutateAsync({ members, ...patch })
      onApplied(result.members, result.skipped)
    } catch (cause) {
      setError(describeApiError(cause))
    }
  }

  return (
    <div className="space-y-2 rounded-2xl border border-dashed border-primary/20 bg-primary/[0.025] p-3">
      <p className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
        <Layers aria-hidden="true" className="size-3.5" />
        批量设置（对当前 {members.length} 只）
        {batch.isPending ? (
          <Loader2 aria-hidden="true" className="size-3 animate-spin" />
        ) : null}
      </p>

      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="xs" variant="outline" disabled={disabled} onClick={() => void run({ shine: true })}>
          全部闪光
        </Button>
        <Button size="xs" variant="outline" disabled={disabled} onClick={() => void run({ shine: false })}>
          全部不闪
        </Button>

        <span className="mx-0.5 h-4 w-px bg-border" aria-hidden="true" />

        <Button size="xs" variant="outline" disabled={disabled} onClick={() => void run({ gender: 'M' })}>
          全 ♂
        </Button>
        <Button size="xs" variant="outline" disabled={disabled} onClick={() => void run({ gender: 'F' })}>
          全 ♀
        </Button>
        <Button size="xs" variant="ghost" disabled={disabled} onClick={() => void run({ gender: null })}>
          性别不指定
        </Button>

        <span className="mx-0.5 h-4 w-px bg-border" aria-hidden="true" />

        <label className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground">等级</span>
          <Input
            type="number"
            min={1}
            max={100}
            value={level}
            onChange={(event) => setLevel(event.target.value)}
            aria-label="批量等级"
            className="h-7 w-16 px-1 text-xs tabular-nums"
          />
        </label>
        <Button
          size="xs"
          variant="outline"
          disabled={disabled || !level}
          onClick={() => void run({ level: Number(level) })}
        >
          套用
        </Button>
        <Button size="xs" variant="ghost" disabled={disabled} onClick={() => void run({ level: null })}>
          恢复默认等级
        </Button>
      </div>

      {error ? (
        <p className="flex items-center gap-1 text-xs text-destructive">
          <CircleAlert aria-hidden="true" className="size-3.5" />
          {error}
        </p>
      ) : null}
    </div>
  )
}

/** 批量结果的「保持原样」提示（性别不合法的成员）。 */
export function BatchSkippedNotice({ skipped }: { skipped: string[] }) {
  if (skipped.length === 0) return null
  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-2.5 text-[11px] text-amber-700 dark:text-amber-500">
      <p className="mb-0.5 flex items-center gap-1.5 font-medium">
        <Badge variant="outline" className="text-[9px]">
          {skipped.length}
        </Badge>
        以下成员按性别规则保持原样
      </p>
      <ul className="list-disc space-y-0.5 pl-4">
        {skipped.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}
