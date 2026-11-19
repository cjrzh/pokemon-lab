/**
 * 从 Showdown 代码导入队伍（对话框）。
 *
 * 交互：粘贴文本 → 点「解析」→ 展示识别到的成员与跳过原因 → 确认后交给页面
 * 作为草稿（**不自动保存**，用户还能继续改）。解析由后端 `POST /teams/import` 完成，
 * 前端不做物种名到图鉴编号的映射（那需要查库）。
 *
 * 导入结果替换当前草稿的成员列表，所以只在新建 / 空白队伍时提供入口，
 * 避免覆盖用户已经编辑的内容（页面负责这个判断）。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleAlert, ClipboardPaste, Loader2, Upload, X } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useImportTeam } from '@/features/teams/hooks'
import type { TeamImportResult, TeamMemberInput } from '@/features/teams/api'
import { describeApiError } from '@/lib/apiClient'

const SAMPLE = `Charizard (F) @ Choice Specs
Ability: Solar Power
Level: 50
Tera Type: Fire
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Heat Wave`

export function ShowdownImportDialog({
  formatKey,
  usedDex,
  teamSize,
  onImported,
  onClose,
}: {
  formatKey: string
  /** 队伍里已有的编号（用于提示重复，避免导入后才发现）。 */
  usedDex: number[]
  /** 队伍上限（一般为 6）。 */
  teamSize: number
  /** 解析成功后把**可加入的成员**交给页面（已去重、已按空位截断）。 */
  onImported: (members: TeamMemberInput[]) => void
  onClose: () => void
}) {
  const [text, setText] = useState('')
  const [result, setResult] = useState<TeamImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const importTeam = useImportTeam()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // 调用方每次渲染都会传新的 onClose；存进 ref 让下面的 effect 只跑一次，
  // 避免反复抢焦点（effect 里同步，不在渲染期写 ref）
  const closeRef = useRef(onClose)

  // 打开即聚焦输入框，并支持 Esc 关闭（Esc 只在有焦点的元素上冒泡到 document）
  useEffect(() => {
    closeRef.current = onClose
  })
  useEffect(() => {
    textareaRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  /** 过滤出真正能加入的：跳过已在队伍里的编号，再按剩余空位截断。 */
  const decision = useMemo(() => {
    if (!result) return null
    const used = new Set(usedDex)
    const free = Math.max(0, teamSize - usedDex.length)
    const accepted: TeamMemberInput[] = []
    const duplicates: string[] = []
    const overflow: string[] = []
    for (const member of result.members) {
      if (used.has(member.dex_number)) {
        duplicates.push(`#${member.dex_number} ${member.showdown_name}已经在队伍里，跳过`)
        continue
      }
      if (accepted.length >= free) {
        overflow.push(`#${member.dex_number} ${member.showdown_name}`)
        continue
      }
      accepted.push(member)
      used.add(member.dex_number)
    }
    return { accepted, duplicates, overflow, free }
  }, [result, usedDex, teamSize])

  const parse = async () => {
    setError(null)
    setResult(null)
    try {
      const parsed = await importTeam.mutateAsync({ format_key: formatKey, text })
      setResult(parsed)
      if (parsed.members.length === 0) {
        setError('没有解析出任何宝可梦，请检查代码格式。')
      }
    } catch (cause) {
      setError(describeApiError(cause))
    }
  }

  const paste = async () => {
    try {
      const clip = await navigator.clipboard.readText()
      setText(clip)
    } catch {
      // 剪贴板被拒绝时用户手动粘贴即可
      setError('无法读取剪贴板，请手动粘贴（Ctrl/Cmd + V）。')
    }
  }

  const confirm = () => {
    if (decision && decision.accepted.length > 0) {
      onImported(decision.accepted)
      onClose()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-black/50 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="从 Showdown 代码导入"
    >
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2">
              <ClipboardPaste aria-hidden="true" className="size-4 text-muted-foreground" />
              从 Showdown 代码导入
            </span>
            <Button size="icon-sm" variant="ghost" aria-label="关闭" onClick={onClose}>
              <X aria-hidden="true" />
            </Button>
          </CardTitle>
          <CardDescription>
            粘贴 Pokémon Showdown 或交换机器人的队伍代码（首行的 !trade 前缀会自动忽略）。
            解析后**追加**到当前队伍，一只也能导；确认无误再保存。
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(event) => {
              setText(event.target.value)
              setResult(null)
              setError(null)
            }}
            placeholder={SAMPLE}
            rows={10}
            aria-label="Showdown 队伍代码"
            className="w-full resize-y rounded-lg border border-input bg-background p-2.5 font-mono text-[11px] leading-relaxed outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => void paste()}>
              <ClipboardPaste aria-hidden="true" />
              读取剪贴板
            </Button>
            <Button size="sm" onClick={() => void parse()} disabled={!text.trim() || importTeam.isPending}>
              {importTeam.isPending ? (
                <Loader2 aria-hidden="true" className="animate-spin" />
              ) : (
                <Upload aria-hidden="true" />
              )}
              解析
            </Button>
            <span className="text-[11px] text-muted-foreground">
              当前版本：{formatKey} · 队伍还可放 {Math.max(0, teamSize - usedDex.length)} 只
            </span>
          </div>

          {error ? (
            <Alert variant="destructive">
              <CircleAlert aria-hidden="true" />
              <AlertTitle>导入失败</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {result && decision ? (
            <div className="space-y-2 rounded-lg border p-2.5">
              <p className="text-xs">
                {`识别到 ${result.members.length} 只，可加入 ${decision.accepted.length} 只${
                  result.problems.length > 0 ||
                  decision.duplicates.length > 0 ||
                  decision.overflow.length > 0
                    ? '（部分条目被跳过）'
                    : ''
                }`}
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {decision.accepted.map((member, index) => (
                  <li
                    key={`${member.dex_number}-${index}`}
                    className="rounded-md border border-primary/40 bg-primary/5 px-1.5 py-0.5 text-[11px]"
                  >
                    #{member.dex_number} {member.showdown_name}
                    {member.item ? ` @ ${member.item}` : ''}
                  </li>
                ))}
              </ul>
              {decision.accepted.length === 0 ? (
                <p className="text-[11px] text-amber-600">
                  没有可加入的成员 —— 都已在队伍里，或队伍已满。
                </p>
              ) : null}
              <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-amber-600">
                {result.problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
                {decision.duplicates.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
                {decision.overflow.length > 0 ? (
                  <li>{`队伍只剩 ${decision.free} 个空位，未加入：${decision.overflow.join('、')}`}</li>
                ) : null}
              </ul>
              <div className="flex justify-end gap-2 pt-1">
                <Button size="sm" variant="ghost" onClick={onClose}>
                  取消
                </Button>
                <Button
                  size="sm"
                  onClick={confirm}
                  disabled={decision.accepted.length === 0}
                >
                  加入队伍（{decision.accepted.length} 只）
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
