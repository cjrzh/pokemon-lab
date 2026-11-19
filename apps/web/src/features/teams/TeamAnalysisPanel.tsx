/**
 * 队伍评价面板。
 *
 * 分两层，来源不同、可靠性也不同：
 *   1. **计算**（打击面 / 缺失面 / 共同弱点）由后端纯函数算出，可复现；
 *   2. **AI 建议**（队伍评价 / 改进建议 / 玩法推荐）由 LLM 生成，可能不可用。
 *
 * LLM 不可用时只提示、不隐藏计算结果 —— 页面把「确定的」和「生成的」分开呈现，
 * 用户能看出哪部分是可以直接采信的。
 *
 * **流式**：模型是推理模型，完整回答要 10–50 秒；用 SSE 边生成边显示，
 * 既不会撞上前端 10 秒超时，用户也能更早看到内容（思考阶段给出进度提示）。
 *
 * 保存方式：
 *   - **已保存的队伍**：评价存到队伍上（`POST /teams/{id}/analyze/stream`），下次打开直接显示，
 *     按钮是「更新评价」；成员改动过会提示「已过期」。
 *   - **未保存的草稿**：只能即时算，不落库。
 */

import { CalendarClock, CircleAlert, RefreshCw, Sparkles, Wand2 } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { useStreamTeamAnalysis } from '@/features/teams/hooks'
import type { StoredAnalysis, TeamAnalysis, TeamMemberInput } from '@/features/teams/api'
import { describeApiError } from '@/lib/apiClient'

export function TeamAnalysisPanel({
  teamId,
  formatKey,
  memberInputs,
  storedAnalysis,
  dirty = false,
  disabled,
}: {
  /** 已保存队伍的 id；草稿为 null（评价不落库）。 */
  teamId?: number | null
  /** 队伍所在版本（草稿评价要用，决定太晶 / 默认等级）。 */
  formatKey: string
  memberInputs: TeamMemberInput[]
  /** 队伍上已存的评价（来自详情接口）。 */
  storedAnalysis?: StoredAnalysis | null
  /** 有未保存改动：此时落库评价已不对应，改为就地评价当前草稿。 */
  dirty?: boolean
  /** 队伍为空时不能评价。 */
  disabled: boolean
}) {
  const stream = useStreamTeamAnalysis()

  // 只有「已保存且没有未保存改动」时才能把评价写回队伍，否则就地评价草稿。
  const persist = Boolean(teamId && teamId > 0) && !dirty
  const streaming = stream.running
  const error = stream.error

  const run = (useLlm: boolean) => {
    void stream.start({
      teamId: persist ? teamId : null,
      members: memberInputs,
      formatKey,
      useLlm,
    })
  }

  // 本次流式结果优先；否则展示落库的那份（仅在没有未保存改动时它才对应所见配置）
  const live: TeamAnalysis | null = stream.coverage
    ? {
        ...stream.coverage,
        llm: stream.text ? { text: stream.text, model: stream.model } : null,
        llm_error: stream.llmError,
      }
    : null
  const shownStored = dirty ? null : (storedAnalysis?.analysis ?? null)
  const shown = live ?? shownStored
  const stale = !live && !dirty && Boolean(storedAnalysis?.stale)
  const dirtyHint = dirty && Boolean(teamId && teamId > 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wand2 aria-hidden="true" className="size-4 text-muted-foreground" />
          队伍评价
          {storedAnalysis?.generated_at && !live && !dirty ? (
            <Badge variant="outline" className="text-[9px] font-normal">
              <CalendarClock aria-hidden="true" className="size-2.5" />
              {formatWhen(storedAnalysis.generated_at)}
            </Badge>
          ) : null}
          {stale ? (
            <Badge variant="outline" className="text-[9px] font-normal text-amber-600">
              队伍已改动，评价已过期
            </Badge>
          ) : null}
        </CardTitle>
        <CardDescription>
          打击面 / 缺失面按**属性**推算（不逐招解析，导入的英文招式名也能覆盖）；
          改进建议与玩法推荐由 AI 生成，仅供参考。
          {persist
            ? '评价会保存在队伍上，下次打开直接显示。'
            : dirtyHint
              ? '有未保存改动：先点「保存」才能把评价更新到队伍上。'
              : '保存队伍后可把评价一并保存。'}
        </CardDescription>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" disabled={disabled || streaming} onClick={() => run(true)}>
            {streaming ? (
              <RefreshCw aria-hidden="true" className="animate-spin" />
            ) : (
              <Sparkles aria-hidden="true" />
            )}
            {shown ? (persist ? '更新评价' : '重新评价') : '生成评价'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || streaming}
            onClick={() => run(false)}
          >
            只看数据
          </Button>
          {streaming ? (
            <Button size="sm" variant="ghost" onClick={() => stream.stop()}>
              停止
            </Button>
          ) : null}
          <span className="text-[11px] text-muted-foreground">
            {disabled ? '先加入宝可梦' : `当前 ${memberInputs.length} 只`}
            {stale ? ' · 建议更新' : ''}
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {error ? (
          <Alert variant="destructive">
            <CircleAlert aria-hidden="true" />
            <AlertTitle>无法生成评价</AlertTitle>
            <AlertDescription>{describeApiError(error)}</AlertDescription>
          </Alert>
        ) : shown ? (
          <AnalysisBody
            analysis={shown}
            thinking={streaming && !stream.text}
            onRetryLlm={() => run(true)}
            retrying={streaming}
          />
        ) : streaming ? (
          <p className="text-xs text-muted-foreground">正在计算打击面…</p>
        ) : (
          <p className="text-xs text-muted-foreground">
            点「生成评价」按当前队伍给出打击面、缺失面与改进建议。
          </p>
        )}
      </CardContent>
    </Card>
  )
}

/** 生成时间的简短展示（YYYY-MM-DD HH:mm）。 */
function formatWhen(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function AnalysisBody({
  analysis,
  thinking,
  onRetryLlm,
  retrying,
}: {
  analysis: TeamAnalysis
  /** 已收到计算部分、AI 正文还没开始（模型在思考）。 */
  thinking: boolean
  onRetryLlm: () => void
  retrying: boolean
}) {
  return (
    <div className="space-y-4">
      {/* ---------- 打击面 ---------- */}
      <section className="space-y-1.5">
        <h3 className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          打击面
        </h3>
        {analysis.attack.length === 0 ? (
          <p className="text-xs text-muted-foreground">队伍里还没有能克制对手的属性。</p>
        ) : (
          <ul className="space-y-1">
            {analysis.attack.map((entry) => (
              <li key={entry.type} className="flex flex-wrap items-center gap-1.5 text-xs">
                <TypeBadge type={entry.type} className="shrink-0 px-1.5 py-0 text-[10px]" />
                <span className="text-muted-foreground">克制</span>
                <span className="flex flex-wrap gap-0.5">
                  {entry.hits.map((hit) => (
                    <TypeBadge key={hit} type={hit} className="px-1 py-0 text-[9px]" />
                  ))}
                </span>
                <span className="text-[10px] text-muted-foreground tabular-nums">
                  {entry.member_count} 只 · {entry.hits.length} 种
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ---------- 缺失面 ---------- */}
      <section className="space-y-1.5">
        <h3 className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          缺失面 <span className="normal-case">（没人能 2 倍克制）</span>
        </h3>
        {analysis.gaps.length === 0 ? (
          <p className="text-xs text-muted-foreground">没有缺口，18 个属性都能打出克制。</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {analysis.gaps.map((gap) => (
              <TypeBadge key={gap} type={gap} className="px-1.5 py-0.5 text-[10px] opacity-80" />
            ))}
          </div>
        )}
      </section>

      {/* ---------- 共同弱点 ---------- */}
      <section className="space-y-1.5">
        <h3 className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          共同弱点 <span className="normal-case">（2 只以上同时怕）</span>
        </h3>
        {analysis.hotspots.length === 0 ? (
          <p className="text-xs text-muted-foreground">没有两只以上共享的弱点。</p>
        ) : (
          <ul className="space-y-1">
            {analysis.hotspots.map((spot) => (
              <li key={spot.type} className="flex flex-wrap items-center gap-1.5 text-xs">
                <TypeBadge type={spot.type} className="shrink-0 px-1.5 py-0 text-[10px]" />
                <span className="text-muted-foreground">
                  {spot.members.length} 只：
                </span>
                <span className="tabular-nums">#{spot.members.join('、#')}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ---------- AI 建议 ---------- */}
      <section className="space-y-1.5">
        <h3 className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          <Sparkles aria-hidden="true" className="size-3 text-primary" />
          AI 建议
          {analysis.llm?.model ? (
            <Badge variant="outline" className="text-[9px] normal-case">
              {analysis.llm.model}
            </Badge>
          ) : null}
        </h3>
        {analysis.llm ? (
          <Markdownish text={analysis.llm.text} />
        ) : thinking ? (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <RefreshCw aria-hidden="true" className="size-3 animate-spin" />
            AI 正在思考…（推理模型会先推理，随后流式输出建议）
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed p-2.5">
            <p className="text-xs text-muted-foreground">
              AI 建议暂不可用{analysis.llm_error ? `（${analysis.llm_error}）` : ''}。
              上面的计算结论不受影响。
            </p>
            <Button size="xs" variant="outline" disabled={retrying} onClick={onRetryLlm}>
              <RefreshCw aria-hidden="true" className={retrying ? 'animate-spin' : undefined} />
              重试
            </Button>
          </div>
        )}
      </section>
    </div>
  )
}

/**
 * 极简渲染：模型按约定输出 `## 小标题` 与列表。
 * 不引 markdown 库 —— 只需要标题与列表两种结构，正则够用且没有 XSS 面。
 */
function Markdownish({ text }: { text: string }) {
  const blocks: React.ReactNode[] = []
  let bullets: string[] = []

  const flush = (key: string) => {
    if (bullets.length === 0) return
    blocks.push(
      <ul key={key} className="list-disc space-y-0.5 pl-4 text-xs leading-relaxed">
        {bullets.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>,
    )
    bullets = []
  }

  text.split('\n').forEach((raw, index) => {
    const line = raw.trim()
    if (!line) return
    if (line.startsWith('#')) {
      flush(`l${index}`)
      blocks.push(
        <p key={`h${index}`} className="text-xs font-medium">
          {line.replace(/^#+\s*/, '')}
        </p>,
      )
      return
    }
    if (/^[-*]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*]\s+/, ''))
      return
    }
    flush(`l${index}`)
    blocks.push(
      <p key={`p${index}`} className="text-xs leading-relaxed">
        {line}
      </p>,
    )
  })
  flush('last')

  return <div className="space-y-1.5 rounded-lg bg-muted/40 p-2.5">{blocks}</div>
}
