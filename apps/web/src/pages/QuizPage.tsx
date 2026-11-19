/**
 * 出卷页：看图识宝可梦。
 *
 * 三段式：
 *   1. **设置**：选范围（世代 / 编号区间）与数量（随机 N 或全量），点「开始出卷」；
 *   2. **答题**：一次一只，大图 + 输入框，回车/提交后立即判分并显示正确答案，
 *      下一题自动聚焦；顶部进度条显示已答 / 总数；
 *   3. **结果**：正确率、逐题回看（图片 + 你的答案 + 正确答案），错题已自动进错题集。
 *
 * 判分只由后端做（中英文名均可、忽略大小写与标点），前端不自己比对；
 * 页面也不在作答前拿到答案 —— 接口就不返回。
 *
 * 错题集单独一块：按错误次数排序，可单条移除或清空，可跳转图鉴复习。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  Check,
  CircleAlert,
  ClipboardList,
  Loader2,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Trash2,
  Trophy,
  Wand2,
  X,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { PokemonArtwork } from '@/features/dex/components/PokemonArtwork'
import { resolveMediaUrl } from '@/features/dex/api'
import {
  useAnswerQuiz,
  useClearQuizMistakes,
  useCreateQuiz,
  useQuizMistakes,
  useRemoveQuizMistake,
} from '@/features/quiz/hooks'
import type { QuizAnswerResult, QuizSession } from '@/features/quiz/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const GENERATIONS = [
  { value: 1, label: '第 1 世代 · 关都' },
  { value: 2, label: '第 2 世代 · 城都' },
  { value: 3, label: '第 3 世代 · 丰缘' },
  { value: 4, label: '第 4 世代 · 神奥' },
  { value: 5, label: '第 5 世代 · 合众' },
  { value: 6, label: '第 6 世代 · 卡洛斯' },
  { value: 7, label: '第 7 世代 · 阿罗拉' },
  { value: 8, label: '第 8 世代 · 伽勒尔' },
  { value: 9, label: '第 9 世代 · 帕底亚' },
]
const COUNT_PRESETS = [10, 20, 50, 100]

/** 当前阶段：设置 → 答题 → 结果。 */
type Stage = 'setup' | 'playing' | 'result'

export function QuizPage() {
  const createQuiz = useCreateQuiz()
  const answerQuiz = useAnswerQuiz()

  const [stage, setStage] = useState<Stage>('setup')
  const [quiz, setQuiz] = useState<QuizSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  /** 当前题的判分结果（显示对错与答案），进入下一题时清空。 */
  const [feedback, setFeedback] = useState<QuizAnswerResult | null>(null)
  const [answer, setAnswer] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // ---------- 设置 ----------
  const [generation, setGeneration] = useState<string>('all')
  const [dexFrom, setDexFrom] = useState('')
  const [dexTo, setDexTo] = useState('')
  const [mode, setMode] = useState<'random' | 'all'>('random')
  const [count, setCount] = useState<number>(20)

  const currentIndex = quiz ? quiz.questions.findIndex((q) => q.is_correct === null) : -1
  const current = quiz && currentIndex >= 0 ? quiz.questions[currentIndex] : null

  // 换题后聚焦输入框（桌面端）；移动端不强制弹键盘。
  // 只在「题号变化 / 反馈关闭 / 进入答题」时触发，不跟随整个 question 对象。
  const currentPosition = current?.position ?? null
  useEffect(() => {
    if (stage === 'playing' && currentPosition !== null && !feedback) {
      inputRef.current?.focus()
    }
  }, [stage, currentPosition, feedback])

  const start = async () => {
    setError(null)
    const from = dexFrom.trim() ? Number(dexFrom) : null
    const to = dexTo.trim() ? Number(dexTo) : null
    if (from !== null && to !== null && from > to) {
      setError('编号下限不能大于上限')
      return
    }
    try {
      const result = await createQuiz.mutateAsync({
        generation: generation === 'all' ? null : Number(generation),
        dex_from: from,
        dex_to: to,
        count: mode === 'all' ? null : count,
        mode,
      })
      setQuiz(result.session)
      setFeedback(null)
      setAnswer('')
      setStage('playing')
    } catch (cause) {
      setError(describeApiError(cause))
    }
  }

  const submit = async () => {
    if (!quiz || !current || feedback) return
    setError(null)
    try {
      const result = await answerQuiz.mutateAsync({
        quizId: quiz.id,
        position: current.position,
        answer,
      })
      setQuiz(result.session)
      setFeedback(result)
      setAnswer('')
    } catch (cause) {
      setError(describeApiError(cause))
    }
  }

  const next = () => {
    setFeedback(null)
    if (quiz?.finished) setStage('result')
  }

  const restart = () => {
    setStage('setup')
    setQuiz(null)
    setFeedback(null)
    setAnswer('')
    setError(null)
  }

  return (
    <>
      <PageHeader
        title="出卷 · 看图识宝可梦"
        description="只看图鉴图片，写出宝可梦名称（中文或英文都可以）。可选世代 / 编号范围，随机抽题或全量出；答错的会自动进入错题集。"
        actions={
          quiz && stage !== 'setup' ? (
            <Button size="sm" variant="outline" onClick={restart}>
              <RotateCcw aria-hidden="true" />
              重新出卷
            </Button>
          ) : null
        }
      />

      {error ? (
        <Alert variant="destructive" className="mb-4">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>出错了</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <div className="space-y-4">
          {stage === 'setup' ? (
            <SetupCard
              generation={generation}
              setGeneration={setGeneration}
              dexFrom={dexFrom}
              setDexFrom={setDexFrom}
              dexTo={dexTo}
              setDexTo={setDexTo}
              mode={mode}
              setMode={setMode}
              count={count}
              setCount={setCount}
              pending={createQuiz.isPending}
              onStart={() => void start()}
            />
          ) : null}

          {stage === 'playing' && quiz ? (
            <PlayingCard
              quiz={quiz}
              current={current}
              answer={answer}
              setAnswer={setAnswer}
              feedback={feedback}
              pending={answerQuiz.isPending}
              inputRef={inputRef}
              onSubmit={() => void submit()}
              onNext={next}
              onFinish={() => setStage('result')}
            />
          ) : null}

          {stage === 'result' && quiz ? (
            <ResultCard
              quiz={quiz}
              onAgain={() => void start()}
              onSetup={restart}
              regenerating={createQuiz.isPending}
            />
          ) : null}
        </div>

        <MistakePanel />
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// 设置
// ---------------------------------------------------------------------------

function SetupCard({
  generation,
  setGeneration,
  dexFrom,
  setDexFrom,
  dexTo,
  setDexTo,
  mode,
  setMode,
  count,
  setCount,
  pending,
  onStart,
}: {
  generation: string
  setGeneration: (value: string) => void
  dexFrom: string
  setDexFrom: (value: string) => void
  dexTo: string
  setDexTo: (value: string) => void
  mode: 'random' | 'all'
  setMode: (value: 'random' | 'all') => void
  count: number
  setCount: (value: number) => void
  pending: boolean
  onStart: () => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wand2 aria-hidden="true" className="size-4 text-muted-foreground" />
          出卷设置
        </CardTitle>
        <CardDescription>
          范围取「世代」与「编号区间」的交集；都不选即全国图鉴 #1–1025。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="space-y-1">
            <span className="text-[11px] text-muted-foreground">世代</span>
            <select
              value={generation}
              onChange={(event) => setGeneration(event.target.value)}
              aria-label="世代范围"
              className="h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm"
            >
              <option value="all">全部世代</option>
              {GENERATIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-[11px] text-muted-foreground">编号下限</span>
            <Input
              inputMode="numeric"
              value={dexFrom}
              onChange={(event) => setDexFrom(event.target.value.replace(/\D/g, ''))}
              placeholder="如 1"
              aria-label="编号下限"
              className="h-9"
            />
          </label>
          <label className="space-y-1">
            <span className="text-[11px] text-muted-foreground">编号上限</span>
            <Input
              inputMode="numeric"
              value={dexTo}
              onChange={(event) => setDexTo(event.target.value.replace(/\D/g, ''))}
              placeholder="如 151"
              aria-label="编号上限"
              className="h-9"
            />
          </label>
        </div>

        <div className="space-y-2">
          <span className="text-[11px] text-muted-foreground">题目数量</span>
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="题目数量">
            <ModeChip active={mode === 'all'} onClick={() => setMode('all')}>
              全量
            </ModeChip>
            <ModeChip active={mode === 'random'} onClick={() => setMode('random')}>
              随机
            </ModeChip>
            {mode === 'random' ? (
              <>
                <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
                {COUNT_PRESETS.map((value) => (
                  <ModeChip key={value} active={count === value} onClick={() => setCount(value)}>
                    {value} 题
                  </ModeChip>
                ))}
                <Input
                  type="number"
                  min={1}
                  max={2000}
                  value={count}
                  onChange={(event) => setCount(Math.max(1, Number(event.target.value) || 1))}
                  aria-label="自定义题目数量"
                  className="h-7 w-20 px-2 text-xs tabular-nums"
                />
              </>
            ) : (
              <span className="text-[11px] text-muted-foreground">
                范围内的宝可梦全部出题（按编号顺序）
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={onStart} disabled={pending}>
            {pending ? (
              <Loader2 aria-hidden="true" className="animate-spin" />
            ) : (
              <Sparkles aria-hidden="true" />
            )}
            开始出卷
          </Button>
          <span className="text-[11px] text-muted-foreground">
            答案接受中文名或英文名，忽略大小写与标点
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function ModeChip({
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
        'rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors',
        active
          ? 'border-primary/40 bg-primary/10 text-primary'
          : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// 答题
// ---------------------------------------------------------------------------

function PlayingCard({
  quiz,
  current,
  answer,
  setAnswer,
  feedback,
  pending,
  inputRef,
  onSubmit,
  onNext,
  onFinish,
}: {
  quiz: QuizSession
  current: QuizSession['questions'][number] | null
  answer: string
  setAnswer: (value: string) => void
  feedback: QuizAnswerResult | null
  pending: boolean
  inputRef: React.RefObject<HTMLInputElement | null>
  onSubmit: () => void
  onNext: () => void
  onFinish: () => void
}) {
  const progress = quiz.total > 0 ? Math.round((quiz.answered / quiz.total) * 100) : 0
  // 反馈阶段显示刚答完那题（而不是下一题）；用「已答题目」定位，避免依赖进度推算
  const answeredQuestion = feedback
    ? [...quiz.questions].reverse().find((q) => q.is_correct !== null) ?? null
    : null
  const question = feedback ? answeredQuestion : current

  return (
    <Card>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Sparkles aria-hidden="true" className="size-4 text-muted-foreground" />
            第 {Math.min(quiz.answered + 1, quiz.total)} / {quiz.total} 题
          </CardTitle>
          <Badge variant="outline" className="tabular-nums">
            已答对 {quiz.correct}
          </Badge>
        </div>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="答题进度"
        >
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {question || feedback ? (
          <>
            <div className="relative mx-auto max-w-sm">
              <div className="rounded-2xl bg-gradient-to-br from-muted/60 to-transparent p-3">
                <PokemonArtwork
                  src={resolveMediaUrl(feedback ? question?.artwork_url : current?.artwork_url)}
                  fallbackSrc={resolveMediaUrl(
                    feedback ? question?.artwork_fallback_url : current?.artwork_fallback_url,
                  )}
                  alt="待识别的宝可梦"
                  variant="hero"
                  className="aspect-square w-full bg-transparent"
                />
              </div>
            </div>

            {feedback ? (
              <FeedbackBlock
                feedback={feedback}
                answered={answeredQuestion}
                onNext={onNext}
              />
            ) : (
              <form
                className="mx-auto flex max-w-sm flex-col gap-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  onSubmit()
                }}
              >
                <Input
                  ref={inputRef}
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  placeholder="输入中文名或英文名…"
                  aria-label="宝可梦名称"
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                  className="h-11 text-center text-base"
                  disabled={pending}
                />
                <div className="flex items-center gap-2">
                  <Button type="submit" className="flex-1" disabled={pending || !answer.trim()}>
                    {pending ? (
                      <Loader2 aria-hidden="true" className="animate-spin" />
                    ) : (
                      <Check aria-hidden="true" />
                    )}
                    提交
                  </Button>
                  <Button type="button" variant="outline" onClick={onFinish} disabled={pending}>
                    结束并看结果
                  </Button>
                </div>
                <p className="text-center text-[11px] text-muted-foreground">
                  按回车提交 · 不确定也可以直接提交，答错会进错题集
                </p>
              </form>
            )}
          </>
        ) : (
          <div className="space-y-2 py-8 text-center">
            <p className="text-sm">这一轮已经答完了。</p>
            <Button size="sm" onClick={onFinish}>
              <Trophy aria-hidden="true" />
              查看结果
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/** 单题反馈：对错、你的答案、正确答案、下一题。 */
function FeedbackBlock({
  feedback,
  answered,
  onNext,
}: {
  feedback: QuizAnswerResult
  answered: QuizSession['questions'][number] | null
  onNext: () => void
}) {
  const correct = feedback.correct

  return (
    <div
      className={cn(
        'mx-auto max-w-sm space-y-3 rounded-xl border p-3 text-center',
        correct ? 'border-success/40 bg-success/5' : 'border-destructive/40 bg-destructive/5',
      )}
      role="status"
    >
      <p
        className={cn(
          'flex items-center justify-center gap-1.5 text-sm font-medium',
          correct ? 'text-success' : 'text-destructive',
        )}
      >
        {correct ? (
          <>
            <Check aria-hidden="true" className="size-4" /> 正确
          </>
        ) : (
          <>
            <X aria-hidden="true" className="size-4" /> 答错了
          </>
        )}
      </p>
      <div className="space-y-0.5">
        {answered?.answer ? (
          <p className="text-xs text-muted-foreground">你的答案：{answered.answer}</p>
        ) : null}
        <p className="text-sm font-semibold">
          {feedback.expected_zh ?? feedback.expected_en}
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">
            {feedback.expected_en}
          </span>
        </p>
      </div>
      <Button size="sm" onClick={onNext} autoFocus>
        下一题
        <ArrowRight aria-hidden="true" />
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 结果
// ---------------------------------------------------------------------------

function ResultCard({
  quiz,
  onAgain,
  onSetup,
  regenerating,
}: {
  quiz: QuizSession
  onAgain: () => void
  onSetup: () => void
  regenerating: boolean
}) {
  const wrong = quiz.questions.filter((q) => q.is_correct === false)
  const skipped = quiz.questions.filter((q) => q.is_correct === null)
  const scored = quiz.correct + wrong.length

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy aria-hidden="true" className="size-4 text-muted-foreground" />
            本轮结果
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <p className="text-4xl font-semibold tabular-nums">{quiz.score}<span className="text-lg text-muted-foreground"> 分</span></p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                答对 {quiz.correct} / 已答 {scored}
                {skipped.length > 0 ? ` · 未答 ${skipped.length}` : ''}
                {quiz.total !== scored + skipped.length ? ` · 共 ${quiz.total}` : ''}
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Badge variant="secondary" className="tabular-nums">
                正确 {quiz.correct}
              </Badge>
              <Badge variant="outline" className="tabular-nums text-destructive">
                错误 {wrong.length}
              </Badge>
              {wrong.length > 0 ? (
                <Badge variant="outline" className="tabular-nums text-amber-600">
                  已加入错题集 {wrong.length}
                </Badge>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={onAgain} disabled={regenerating}>
              {regenerating ? (
                <Loader2 aria-hidden="true" className="animate-spin" />
              ) : (
                <RefreshCw aria-hidden="true" />
              )}
              再考一次（同范围）
            </Button>
            <Button size="sm" variant="outline" onClick={onSetup}>
              改设置
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardList aria-hidden="true" className="size-4 text-muted-foreground" />
            逐题回看
          </CardTitle>
          <CardDescription>
            绿色为答对、红色为答错（已自动加入错题集）、灰色为未作答。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-2 sm:grid-cols-2">
            {quiz.questions.map((question) => (
              <ReviewRow key={question.position} question={question} />
            ))}
          </ul>
        </CardContent>
      </Card>
    </>
  )
}

function ReviewRow({ question }: { question: QuizSession['questions'][number] }) {
  const state =
    question.is_correct === null ? 'skipped' : question.is_correct ? 'correct' : 'wrong'
  return (
    <li
      className={cn(
        'flex items-center gap-2 rounded-lg border p-1.5',
        state === 'correct' && 'border-success/40 bg-success/5',
        state === 'wrong' && 'border-destructive/40 bg-destructive/5',
      )}
    >
      <PokemonArtwork
        src={resolveMediaUrl(question.artwork_url)}
        fallbackSrc={resolveMediaUrl(question.artwork_fallback_url)}
        alt={question.name_zh ?? question.name_en ?? ''}
        className="size-12 shrink-0 bg-transparent"
        imageClassName="p-0.5"
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium">
          {question.name_zh ?? question.name_en}
          <span className="ml-1 font-normal text-muted-foreground">{question.name_en}</span>
        </p>
        <p className="truncate text-[10px] text-muted-foreground">
          #{String(question.dex_number).padStart(4, '0')}
          {state === 'skipped'
            ? ' · 未作答'
            : ` · 你答：${question.answer ?? '（空）'}`}
        </p>
      </div>
      {state === 'correct' ? (
        <Check aria-label="答对" className="size-4 shrink-0 text-success" />
      ) : state === 'wrong' ? (
        <X aria-label="答错" className="size-4 shrink-0 text-destructive" />
      ) : null}
    </li>
  )
}

// ---------------------------------------------------------------------------
// 错题集
// ---------------------------------------------------------------------------

function MistakePanel() {
  const mistakes = useQuizMistakes()
  const remove = useRemoveQuizMistake()
  const clear = useClearQuizMistakes()
  const [confirmClear, setConfirmClear] = useState(false)

  const items = useMemo(() => mistakes.data?.items ?? [], [mistakes.data])
  const total = mistakes.data?.total ?? 0

  return (
    <Card className="h-fit">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ClipboardList aria-hidden="true" className="size-4 text-muted-foreground" />
          错题集
          <Badge variant="outline" className="tabular-nums">
            {total}
          </Badge>
        </CardTitle>
        <CardDescription>答错会自动记录；答对不会自动移除，由你判断是否已掌握。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {mistakes.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : mistakes.isError ? (
          <p className="text-xs text-destructive">无法加载错题集。</p>
        ) : items.length === 0 ? (
          <p className="text-xs text-muted-foreground">还没有错题。做错的宝可梦会出现在这里。</p>
        ) : (
          <>
            <ul className="space-y-1">
              {items.map((item) => (
                <li key={item.dex_number} className="flex items-center gap-1.5 rounded-md px-1 py-1">
                  <PokemonArtwork
                    src={resolveMediaUrl(item.sprite_url)}
                    alt={item.name_zh ?? item.name_en}
                    className="size-7 shrink-0 bg-transparent"
                    imageClassName="p-0.5"
                  />
                  <Link
                    to={`/dex/${item.dex_number}`}
                    className="min-w-0 flex-1 truncate text-xs hover:text-primary hover:underline"
                    title={`查看图鉴：${item.name_zh ?? item.name_en}`}
                  >
                    {item.name_zh ?? item.name_en}
                    <span className="ml-1 text-[10px] text-muted-foreground">{item.name_en}</span>
                  </Link>
                  <Badge variant="outline" className="shrink-0 text-[9px] tabular-nums">
                    错 {item.wrong_count}
                  </Badge>
                  <button
                    type="button"
                    onClick={() => remove.mutate(item.dex_number)}
                    aria-label={`移除 ${item.name_zh ?? item.name_en}`}
                    className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 aria-hidden="true" className="size-3" />
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-end pt-1">
              {confirmClear ? (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-muted-foreground">确定清空？</span>
                  <Button
                    size="xs"
                    variant="destructive"
                    onClick={() => {
                      clear.mutate()
                      setConfirmClear(false)
                    }}
                  >
                    清空
                  </Button>
                  <Button size="xs" variant="ghost" onClick={() => setConfirmClear(false)}>
                    取消
                  </Button>
                </div>
              ) : (
                <Button size="xs" variant="ghost" onClick={() => setConfirmClear(true)}>
                  清空错题集
                </Button>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
