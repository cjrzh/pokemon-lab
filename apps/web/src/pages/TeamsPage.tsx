/**
 * 双打建队页面。
 *
 * 结构：
 *   - 左侧：队伍列表（新建 / 选择 / 删除）；
 *   - 右侧：编辑器（最多 6 只槽位，每只可展开编辑招式 / 特性 / 道具 / EV / IV / 性格）；
 *   - 顶部：队伍命名、格式切换、保存、打开 Showdown 导出页。
 *
 * 数据流：编辑在本地草稿上进行，保存时整队提交给后端校验（编号不重复、道具不重复、
 * 招式 / 特性在该版本可用、配点边界）。切换宝可梦时用 `/team-options` 拉该格式的
 * 合法招式与按使用率的推荐值，作为默认选择。
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  Check,
  CircleAlert,
  ArrowDown,
  ArrowUp,
  GripVertical,
  RotateCcw,
  ClipboardPaste,
  Loader2,
  Plus,
  Save,
  Search,
  Terminal,
  Trash2,
  Users,
  X,
} from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { PokemonSprite } from '@/features/dex/components/PokemonSprite'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { resolveMediaUrl } from '@/features/dex/api'
import { useDebouncedValue, usePokemonList } from '@/features/dex/hooks'
import { TeamMemberEditor } from '@/features/teams/TeamMemberEditor'
import { BatchSkippedNotice, TeamBatchBar } from '@/features/teams/TeamBatchBar'
import { CopyShowdownButton } from '@/features/teams/CopyShowdownButton'
import { TeamAnalysisPanel } from '@/features/teams/TeamAnalysisPanel'
import { ShowdownImportDialog } from '@/features/teams/ShowdownImportDialog'
import { renderTeamShowdown } from '@/features/teams/showdownText'
import { sameTeamContent, withPositions } from '@/features/teams/draft'
import { panelMaxHeight, shouldDropUp } from '@/features/teams/dropdown'
import { mergeSubsetOrder, moveItem, moveMemberDown, moveMemberUp } from '@/features/teams/reorder'
import {
  useListReorder,
  useListReorder as useMemberReorder,
} from '@/features/teams/useListReorder'
import { fetchEventTeamImport } from '@/features/tournaments/api'
import {
  useCreateTeam,
  useDeleteTeam,
  useTeam,
  useTeams,
  useReorderTeams,
  useUpdateTeam,
  useValidateTeam,
} from '@/features/teams/hooks'
import type { TeamDetail, TeamMember, TeamMemberInput, TeamSummary } from '@/features/teams/api'
import { describeApiError } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

const TEAM_SIZE = 6
const SEARCH_LIMIT = 8
/**
 * 未保存草稿的本地暂存键（sessionStorage）。
 *
 * 为什么需要：新建队伍 / 官方赛事载入的草稿是组件 state，离开建队页（切到图鉴、
 * 赛事页…）组件卸载就会丢。用户「建到一半跳走再回来」看到空白甚至无法编辑，
 * 就是这里丢的数据。已保存队伍不存 —— 它从接口按 `?team=id` 重新拉。
 */
const DRAFT_STORAGE_KEY = 'pokemon-lab:team-draft'

/** 读取暂存草稿；数据损坏时静默丢弃，不阻断页面。 */
function readStoredDraft(): { draft: TeamDetail; forms: Record<number, string | null> } | null {
  try {
    const raw = window.sessionStorage.getItem(DRAFT_STORAGE_KEY)
    if (!raw) return null
    const payload = JSON.parse(raw) as {
      draft?: TeamDetail
      forms?: Record<number, string | null>
    }
    if (!payload.draft || payload.draft.id !== 0) return null
    return { draft: payload.draft, forms: payload.forms ?? {} }
  } catch {
    return null
  }
}

function writeStoredDraft(
  draft: TeamDetail | null,
  forms: Record<number, string | null>,
): void {
  try {
    // 只暂存「未保存的新队伍」。已保存队伍以数据库为准，存了反而会与库里不一致。
    if (!draft || draft.id !== 0) {
      window.sessionStorage.removeItem(DRAFT_STORAGE_KEY)
      return
    }
    window.sessionStorage.setItem(
      DRAFT_STORAGE_KEY,
      JSON.stringify({ draft, forms }),
    )
  } catch {
    // 隐私模式 / 配额不足：暂存失败不影响当前编辑
  }
}

/** 空槽位占位（不落库，保存前必须填满或删掉）。 */
export function TeamsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = Number(searchParams.get('team') ?? '') || null
  /**
   * 从官方赛事页跳转来的「一键建队」参数：
   * `?fromTournament={赛事 id}&eventTeam={队伍 id}`。
   *
   * 载入后把成员填进草稿（不保存），并清掉参数，避免刷新时反复覆盖用户的改动。
   */
  const fromTournament = Number(searchParams.get('fromTournament') ?? '') || null
  const eventTeamId = Number(searchParams.get('eventTeam') ?? '') || null

  const teamsQuery = useTeams()
  const createTeam = useCreateTeam()
  const updateTeam = useUpdateTeam()
  const deleteTeam = useDeleteTeam()
  const validate = useValidateTeam()
  const reorderTeams = useReorderTeams()

  const [draft, setDraft] = useState<TeamDetail | null>(() => readStoredDraft()?.draft ?? null)
  /**
   * 上次保存（或刚打开）时的快照。
   *
   * `dirty` 由「草稿 vs 快照」比对得出，而不是每次 onChange 直接置 true：
   * 成员编辑器挂载后会自动套用推荐值并回调 onChange，即使结果与原值完全相同
   * （已保存的队伍本来就带完整推荐配置），旧写法也会误报「有未保存改动」。
   */
  const [savedSnapshot, setSavedSnapshot] = useState<TeamDetail | null>(null)
  const [message, setMessage] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  /** 队伍列表的版本筛选：'all' 或某个 format_key。 */
  const [teamFilter, setTeamFilter] = useState<string>('all')
  /** 上次批量操作里「按性别规则保持原样」的成员说明。 */
  const [batchSkipped, setBatchSkipped] = useState<string[]>([])
  /**
   * 每个成员当前选中的形态（`dex_number` → 本地形态 slug）。
   *
   * `undefined`（不在表里）表示「自动」：后端会选使用率最高的形态
   * （洛托姆 → 清洗洛托姆、喷火龙 → 超级进化 Y）。用户手动切换后写进这里，
   * 切换形态必须重新拉 `/team-options`，因为招式、特性、Showdown 名都会变。
   * 形态不落库 —— 它已经体现在 `showdown_name` 里。
   */
  const [memberForms, setMemberForms] = useState<Record<number, string | null>>(
    () => readStoredDraft()?.forms ?? {},
  )
  /**
   * 已经切到「本地草稿」（新建 / 导入 / 删除后）时，详情数据不能再覆盖它。
   *
   * `setSearchParams` 是异步导航：点「新建队伍」后会有一次渲染里 `?team=3`
   * 还在，如果详情在这时返回（或重新拉取），就会把刚建好的空白草稿覆盖回
   * 已保存队伍 —— 用户表现为「要点两次」。这里用一个 ref 在本地操作时立起
   * 闸门，等 URL 真正清空后再放下。
   */
  const ignoreDetailRef = useRef(false)

  const formats = useMemo(() => teamsQuery.data?.formats ?? [], [teamsQuery.data])
  const allTeams = useMemo(() => teamsQuery.data?.items ?? [], [teamsQuery.data])

  /** 筛选后的队伍；同时给出「版本 → 数量」用于筛选按钮。 */
  const visibleTeams = useMemo(
    () => (teamFilter === 'all' ? allTeams : allTeams.filter((t) => t.format_key === teamFilter)),
    [allTeams, teamFilter],
  )
  /**
   * 队伍列表的拖动排序。
   *
   * 筛选状态下拖的是可见子集，但保存需要完整顺序：先对子集排序，
   * 再用 `mergeSubsetOrder` 把新顺序填回完整列表里对应的位置。
   */
  const teamReorder = useListReorder<TeamSummary>(visibleTeams, (nextVisible) => {
    const merged = mergeSubsetOrder(allTeams, nextVisible)
    reorderTeams.mutate(merged.map((team) => team.id))
  }, (team) => team.id)

  const teamsByFormat = useMemo(() => {
    const counts = new Map<string, number>()
    for (const team of allTeams) {
      counts.set(team.format_key, (counts.get(team.format_key) ?? 0) + 1)
    }
    // 按格式定义的顺序展示（与建队时的版本下拉一致），无名格式排最后
    const order = new Map(formats.map((format, index) => [format.key, index]))
    return [...counts.entries()]
      .map(([key, count]) => {
        const label = formats.find((format) => format.key === key)?.short_label ?? key
        return [key, label, count] as const
      })
      .sort((a, b) => (order.get(a[0]) ?? 99) - (order.get(b[0]) ?? 99))
  }, [allTeams, formats])

  const openTeam = async (teamId: number) => {
    ignoreDetailRef.current = false
    setSearchParams({ team: String(teamId) }, { replace: true })
    setMessage(null)
  }

  /** 清掉 URL 里的队伍参数并打开「本地草稿」闸门（异步导航期间不回收草稿）。 */
  const deselectTeam = useCallback(() => {
    ignoreDetailRef.current = true
    setSearchParams({}, { replace: true })
  }, [setSearchParams])

  const startNew = () => {
    const blank = blankDraft(formats)
    setMemberForms({})
    setDraft(blank)
    // 新建草稿与快照都为空队伍：未改动前不显示脏标记
    setSavedSnapshot(blank)
    deselectTeam()
    setMessage(null)
  }

  const editExisting = (teamId: number) => {
    void openTeam(teamId)
  }

  // 从官方赛事载入队伍：拉取草稿 → 填进编辑器（不落库）
  const [eventMessage, setEventMessage] = useState<string | null>(null)
  const loadedEventKey = useRef<string | null>(null)
  useEffect(() => {
    if (!fromTournament || !eventTeamId) return
    const key = `${fromTournament}:${eventTeamId}`
    if (loadedEventKey.current === key) return
    loadedEventKey.current = key
    let cancelled = false
    void fetchEventTeamImport(fromTournament, eventTeamId)
      .then((data) => {
        if (cancelled) return
        const members: TeamMemberInput[] = data.members.map((member) => ({
          ...member,
          language: member.language as TeamMemberInput['language'],
        }))
        // 队表里带了形态（连击流武道熊师 / 低调颤弦蝾螈）：预置形态选择，
        // 避免编辑器按使用率自动换成另一个形态（G 形态尤其容易认错）
        setMemberForms(
          Object.fromEntries(
            data.members.map((member) => [member.dex_number, member.form ?? null]),
          ),
        )
        setDraft({
          id: 0,
          name: `${data.team.player} · ${data.tournament.name}`,
          format_key: data.format_key,
          format_label: data.tournament.ruleset_label,
          note: `来自官方赛事 ${data.tournament.name}（${data.team.rank} 名 ${data.team.player}）；赛事未公开 EV / IV，配点需自行调整。`,
          member_count: members.length,
          updated_at: null,
          members: withPositions(members),
          trade_prefix: data.trade_prefix,
          default_level: data.default_level,
          points_kind: data.points_kind,
        })
        // 载入即视为「有未保存改动」：用户确认后保存
        setSavedSnapshot(null)
        deselectTeam()
        const issues = data.validation?.issues ?? []
        setEventMessage(
          issues.length > 0
            ? `已载入 ${members.length} 只；源站数据有 ${issues.length} 处与本地规则不一致（见保存时提示）`
            : `已从赛事载入 ${members.length} 只，确认后保存`,
        )
      })
      .catch((error) => {
        if (!cancelled) setEventMessage(describeApiError(error))
      })
    return () => {
      cancelled = true
    }
  }, [fromTournament, eventTeamId, deselectTeam])

  // 打开已有队伍时拉详情（用 query 的同时把结果同步进草稿）
  const detailQuery = useTeam(selectedId)
  /**
   * 详情数据 → 草稿的同步放在 effect 里，**不能在渲染期 setState**。
   *
   * 渲染期写状态会让「新建队伍」先渲染一次再把草稿覆盖回旧队伍；放进 effect
   * 后只在 `selectedId` / 详情数据变化时执行，且本地草稿模式下被闸门挡住。
   */
  useEffect(() => {
    if (!selectedId) {
      // 已没有选中队伍：本地草稿模式下不再拦截后续的详情（用户再点开队伍要用）
      ignoreDetailRef.current = false
      return
    }
    const saved = detailQuery.data
    if (!saved || ignoreDetailRef.current) return
    setDraft((current) => (current && current.id === saved.id ? current : saved))
    setSavedSnapshot((current) => (current && current.id === saved.id ? current : saved))
    // 已保存的队伍：后端按 showdown_name 反查出了形态，填进选择器
    // （后端返回 `default` 表示「明确选择默认形态」；编辑器需要把它映射成
    // 请求参数 `form=default`，不能当成 undefined，那样会被自动替换形态）
    setMemberForms(
      Object.fromEntries(
        saved.members
          .filter((member) => member.form !== undefined && member.form !== null)
          .map((member) => [
            member.dex_number,
            member.form === 'default' ? null : (member.form ?? null),
          ]),
      ),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, detailQuery.data])

  // 草稿变化时同步暂存（含形态选择）；只存未保存的新队伍
  useEffect(() => {
    writeStoredDraft(draft, memberForms)
  }, [draft, memberForms])

  /** 有未保存改动：与上次保存的快照逐字段比较（自动填充推荐值不会误报）。 */
  const dirty = !sameTeamContent(draft, savedSnapshot)

  /** 恢复到上次保存的状态。 */
  const revert = () => {
    if (!savedSnapshot) return
    setDraft(savedSnapshot)
    setBatchSkipped([])
    setMessage(null)
  }

  const memberInputs: TeamMemberInput[] = useMemo(
    () => (draft?.members ?? []).map(toInput),
    [draft],
  )

  /** 拖动排序：只改草稿顺序，保存时按 position 落库。 */
  const reorder = useMemberReorder(draft?.members ?? [], (members) => {
    if (!draft) return
    setDraft({ ...draft, members })
  })

  const save = async () => {
    if (!draft) return
    setMessage(null)
    const payload = { name: draft.name, format_key: draft.format_key, members: memberInputs }
    const result = await validate.mutateAsync(payload)
    if (!result.ok) {
      setMessage({ tone: 'error', text: result.issues.map((issue) => issue.message).join('；') })
      return
    }

    try {
      if (draft.id > 0) {
        const saved = await updateTeam.mutateAsync({ teamId: draft.id, payload })
        setDraft(saved)
        setSavedSnapshot(saved)
      } else {
        const saved = await createTeam.mutateAsync({
          name: draft.name,
          format_key: draft.format_key,
          note: draft.note,
          members: memberInputs,
        })
        setDraft(saved)
        setSavedSnapshot(saved)
        setSearchParams({ team: String(saved.id) }, { replace: true })
      }
      setMessage({ tone: 'ok', text: '已保存' })
    } catch (error) {
      setMessage({ tone: 'error', text: describeApiError(error) })
    }
  }

  const remove = async (teamId: number) => {
    await deleteTeam.mutateAsync(teamId)
    if (draft?.id === teamId) {
      setDraft(null)
      setSavedSnapshot(null)
      deselectTeam()
    }
  }

  /** 导入结果**追加**进当前队伍（对话框已按空位与重复编号筛过）。 */
  const applyImport = (members: TeamMemberInput[]) => {
    if (members.length === 0) return
    const base = draft ?? blankDraft(formats)
    setDraft({
      ...base,
      members: withPositions([...base.members, ...members]),
    })
    deselectTeam()
    setMessage({ tone: 'ok', text: `已加入 ${members.length} 只，确认后保存` })
  }

  return (
    <>
      <PageHeader
        title="双打建队"
        description="最多 6 只，编号与道具不可重复；招式 / 特性按所选版本校验。切到某只宝可梦时，招式、特性、道具、配点默认取该格式的使用率推荐值。"
        actions={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={startNew}>
              <Plus aria-hidden="true" />
              新建队伍
            </Button>
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
              <ClipboardPaste aria-hidden="true" />
              导入代码
            </Button>
            {draft?.id ? (
              <Button size="sm" variant="outline" asChild>
                <Link to={`/teams/${draft.id}/showdown`}>
                  <Terminal aria-hidden="true" />
                  Showdown
                </Link>
              </Button>
            ) : null}
          </div>
        }
      />

      {importOpen ? (
        <ShowdownImportDialog
          formatKey={draft?.format_key ?? formats[0]?.key ?? 'sv'}
          usedDex={draft?.members.map((member) => member.dex_number) ?? []}
          teamSize={TEAM_SIZE}
          onImported={applyImport}
          onClose={() => setImportOpen(false)}
        />
      ) : null}

      {eventMessage ? (
        <Alert className="mb-3">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>来自官方赛事</AlertTitle>
          <AlertDescription>{eventMessage}</AlertDescription>
          <AlertAction>
            <Button size="xs" variant="outline" onClick={() => setEventMessage(null)}>
              知道了
            </Button>
          </AlertAction>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        {/* ---------- 队伍列表 ---------- */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users aria-hidden="true" className="size-4 text-muted-foreground" />
              我的队伍
              <Badge variant="outline" className="tabular-nums">
                {visibleTeams.length}
              </Badge>
            </CardTitle>
            {/* 按游戏版本筛选：队伍可以很多，按版本收窄才找得快 */}
            <div
              className="flex flex-wrap gap-1 pt-1"
              role="group"
              aria-label="按版本筛选队伍"
            >
              <FilterChip
                active={teamFilter === 'all'}
                onClick={() => setTeamFilter('all')}
              >
                全部
              </FilterChip>
              {teamsByFormat.map(([key, label, count]) => (
                <FilterChip
                  key={key}
                  active={teamFilter === key}
                  onClick={() => setTeamFilter(key)}
                >
                  {label}
                  <span className="ml-1 text-[9px] opacity-70 tabular-nums">{count}</span>
                </FilterChip>
              ))}
            </div>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {teamsQuery.isPending ? (
              <Skeleton className="h-10 w-full" />
            ) : visibleTeams.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                {teamFilter === 'all' ? '还没有队伍，点右上角新建。' : '该版本还没有队伍。'}
              </p>
            ) : (
              <ul className="space-y-1">
                {visibleTeams.map((team, index) => {
                  const dragging = teamReorder.isDragging(index)
                  return (
                    <li
                      key={team.id}
                      {...teamReorder.rowProps(index)}
                      className={cn(
                        'relative flex items-center gap-0.5 rounded-lg transition-opacity',
                        dragging && 'opacity-40',
                      )}
                    >
                      {teamReorder.showLineBefore(index) ? (
                        <span
                          aria-hidden="true"
                          className="pointer-events-none absolute inset-x-1 -top-1 h-0.5 rounded-full bg-primary"
                        />
                      ) : null}
                      {teamReorder.showLineAfter(index) ? (
                        <span
                          aria-hidden="true"
                          className="pointer-events-none absolute inset-x-1 -bottom-1 h-0.5 rounded-full bg-primary"
                        />
                      ) : null}
                      <span
                        {...teamReorder.handleProps(index)}
                        aria-label={`拖动 ${team.name} 调整顺序`}
                        title="拖动调整顺序"
                        className="shrink-0 cursor-grab rounded p-0.5 text-muted-foreground/50 hover:bg-muted hover:text-foreground active:cursor-grabbing"
                      >
                        <GripVertical aria-hidden="true" className="size-3.5" />
                      </span>
                      <button
                        type="button"
                        onClick={() => editExisting(team.id)}
                        className={cn(
                          'min-w-0 flex-1 rounded-lg px-2 py-1.5 text-left text-xs transition-colors',
                          draft?.id === team.id
                            ? 'bg-primary/10 font-medium text-primary ring-1 ring-inset ring-primary/20'
                            : 'hover:bg-muted/70',
                        )}
                      >
                        <span className="block truncate">{team.name}</span>
                        <span className="block text-[10px] text-muted-foreground">
                          {team.format_label ?? team.format_key} · {team.member_count} 只
                        </span>
                      </button>
                      {/* 键盘 / 触屏也能排序：筛选状态下在可见子集内移动 */}
                      <span className="flex shrink-0 items-center">
                        <button
                          type="button"
                          disabled={index === 0}
                          onClick={() => {
                            const next = moveItem(visibleTeams, index, index - 1)
                            reorderTeams.mutate(
                              mergeSubsetOrder(allTeams, next).map((item) => item.id),
                            )
                          }}
                          aria-label={`上移 ${team.name}`}
                          className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30 disabled:hover:bg-transparent"
                        >
                          <ArrowUp aria-hidden="true" className="size-3" />
                        </button>
                        <button
                          type="button"
                          disabled={index === visibleTeams.length - 1}
                          onClick={() => {
                            const next = moveItem(visibleTeams, index, index + 1)
                            reorderTeams.mutate(
                              mergeSubsetOrder(allTeams, next).map((item) => item.id),
                            )
                          }}
                          aria-label={`下移 ${team.name}`}
                          className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30 disabled:hover:bg-transparent"
                        >
                          <ArrowDown aria-hidden="true" className="size-3" />
                        </button>
                      </span>
                      <button
                        type="button"
                        onClick={() => void remove(team.id)}
                        aria-label={`删除 ${team.name}`}
                        className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 aria-hidden="true" className="size-3.5" />
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* ---------- 编辑器 ---------- */}
        {!draft ? (
          <Card className="flex items-center justify-center p-12 text-center text-sm text-muted-foreground">
            从左侧选一支队伍，或新建一支开始。
          </Card>
        ) : (
          <div className="space-y-3">
            <Card className="sticky top-2 z-20 bg-card/85 backdrop-blur-xl">
              <CardContent className="flex flex-wrap items-end gap-2 pt-4">
                <label className="min-w-48 flex-1 space-y-1">
                  <span className="text-[11px] text-muted-foreground">队伍名称</span>
                  <Input
                    value={draft.name}
                    onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                    className="h-9"
                    aria-label="队伍名称"
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-[11px] text-muted-foreground">版本</span>
                  <select
                    value={draft.format_key}
                    disabled={draft.id > 0}
                    onChange={(event) => {
                      const next = event.target.value
                      const meta = formats.find((item) => item.key === next)
                      setDraft({
                        ...draft,
                        format_key: next,
                        format_label: meta?.label ?? null,
                        trade_prefix: meta?.trade_prefix ?? null,
                        points_kind: meta?.points_kind ?? 'ev',
                        default_level: meta?.default_level ?? 50,
                        members: [],
                      })
                    }}
                    aria-label="队伍版本"
                    className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm disabled:opacity-60"
                  >
                    {formats.map((format) => (
                      <option key={format.key} value={format.key}>
                        {format.short_label}
                      </option>
                    ))}
                  </select>
                </label>

                {/* 队伍容量：一眼看清还能加几只 */}
                <div className="space-y-1">
                  <span className="text-[11px] text-muted-foreground">成员</span>
                  <div className="flex h-9 items-center gap-1.5 rounded-lg border border-input px-2.5">
                    {Array.from({ length: TEAM_SIZE }, (_, slot) => (
                      <span
                        key={slot}
                        aria-hidden="true"
                        className={cn(
                          'size-2 rounded-full',
                          slot < draft.members.length
                            ? 'bg-primary'
                            : 'bg-muted-foreground/25',
                        )}
                      />
                    ))}
                    <span className="ml-1 text-xs text-muted-foreground tabular-nums">
                      {draft.members.length}/{TEAM_SIZE} 只
                    </span>
                  </div>
                </div>

                <Button size="sm" onClick={() => void save()} disabled={validate.isPending}>
                  {validate.isPending ? (
                    <Loader2 aria-hidden="true" className="animate-spin" />
                  ) : (
                    <Save aria-hidden="true" />
                  )}
                  保存
                </Button>
                {/* 整队一键复制：只复制队伍本体，不带交易机器人前缀 */}
                <CopyShowdownButton
                  text={renderTeamShowdown(draft.members, {
                    formatKey: draft.format_key,
                    defaultLevel: draft.default_level,
                  })}
                  label="复制整队 Showdown 代码"
                  fallbackText="无法自动复制，请手动全选复制整队代码："
                  fallbackClassName="h-40"
                >
                  复制整队
                </CopyShowdownButton>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={revert}
                  disabled={!dirty}
                  title="放弃当前改动，恢复到上次保存的状态"
                >
                  <RotateCcw aria-hidden="true" />
                  恢复
                </Button>
                {dirty ? (
                  <Badge variant="outline" className="mb-2 text-[10px] text-amber-600">
                    有未保存改动
                  </Badge>
                ) : null}
              </CardContent>
            </Card>

            {message ? (
              <Alert variant={message.tone === 'error' ? 'destructive' : 'default'}>
                {message.tone === 'ok' ? (
                  <Check aria-hidden="true" />
                ) : (
                  <CircleAlert aria-hidden="true" />
                )}
                <AlertTitle>{message.tone === 'ok' ? '保存成功' : '无法保存'}</AlertTitle>
                <AlertDescription>{message.text}</AlertDescription>
              </Alert>
            ) : null}

            {batchSkipped.length > 0 ? (
              <BatchSkippedNotice skipped={batchSkipped} />
            ) : null}

            <TeamBatchBar
              members={draft.members}
              onApplied={(members, skipped) => {
                setDraft({ ...draft, members: withPositions(members) })
                setBatchSkipped(skipped)
              }}
            />

            <div className="space-y-2">
              {draft.members.map((member, index) => (
                <TeamMemberEditor
                  // 用图鉴编号做 key（队伍内编号唯一）：拖动改的是顺序，
                  // 若把 index 拼进 key，换位会让组件重挂载并丢掉展开状态。
                  key={member.dex_number}
                  index={index}
                  formatKey={draft.format_key}
                  pointsKind={draft.points_kind}
                  defaultLevel={draft.default_level}
                  member={member}
                  teamMembers={draft.members}
                  selectedForm={memberForms[member.dex_number]}
                  onFormChange={(form) => {
                    setMemberForms((current) => ({
                      ...current,
                      [member.dex_number]: form,
                    }))
                  }}
                  onChange={(next) => {
                    const members = [...draft.members]
                    members[index] = next
                    setDraft({ ...draft, members })
                  }}
                  onRemove={() => {
                    setDraft({
                      ...draft,
                      members: withPositions(
                        draft.members.filter((_, position) => position !== index),
                      ),
                    })
                  }}
                  dragHandleProps={reorder.handleProps(index)}
                  rowProps={reorder.rowProps(index)}
                  dragging={reorder.isDragging(index)}
                  showLineBefore={reorder.showLineBefore(index)}
                  showLineAfter={reorder.showLineAfter(index)}
                  canMoveUp={index > 0}
                  canMoveDown={index < draft.members.length - 1}
                  onMoveUp={() => setDraft({ ...draft, members: moveMemberUp(draft.members, index) })}
                  onMoveDown={() =>
                    setDraft({ ...draft, members: moveMemberDown(draft.members, index) })
                  }
                />
              ))}

              {draft.members.length < TEAM_SIZE ? (
                <AddSlot
                  formatKey={draft.format_key}
                  usedDex={draft.members.map((member) => member.dex_number)}
                  onAdd={(member) => {
                    setDraft({
                      ...draft,
                      members: withPositions([...draft.members, member]),
                    })
                  }}
                />
              ) : null}
            </div>

            <TeamAnalysisPanel
              teamId={draft.id > 0 ? draft.id : null}
              formatKey={draft.format_key}
              memberInputs={memberInputs}
              storedAnalysis={draft.analysis}
              dirty={dirty}
              disabled={memberInputs.length === 0}
            />
          </div>
        )}
      </div>
    </>
  )
}

/** 小号筛选按钮（版本筛选用，与招式页的风格一致）。 */
function FilterChip({
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
        'inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] transition-colors',
        active
          ? 'bg-primary/10 font-medium text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

function toInput(member: TeamMember): TeamMemberInput {
  // `position` 与 `form` 都不是提交字段：位置由数组顺序落库，形态由 showdown_name 表达
  const { position: _position, form: _form, ...rest } = member
  return rest
}

/** 一张空白草稿（新建队伍 / 导入时没有选中队伍时的落点）。 */
function blankDraft(formats: { key: string; label: string; trade_prefix: string | null; points_kind: 'ev' | 'stat_points'; default_level: number }[]): TeamDetail {
  const formatKey = formats[0]?.key ?? 'sv'
  const meta = formats.find((item) => item.key === formatKey)
  return {
    id: 0,
    name: '新队伍',
    format_key: formatKey,
    format_label: meta?.label ?? null,
    note: null,
    member_count: 0,
    updated_at: null,
    members: [],
    trade_prefix: meta?.trade_prefix ?? null,
    default_level: meta?.default_level ?? 50,
    points_kind: meta?.points_kind ?? 'ev',
  }
}

/** 空缺位：搜索中文名 / 英文名 / 图鉴编号加入一只（前缀匹配，输入「喷火」即可命中）。 */
function AddSlot({
  formatKey,
  usedDex,
  onAdd,
}: {
  formatKey: string
  usedDex: number[]
  onAdd: (member: TeamMember) => void
}) {
  const listboxId = useId()
  const containerRef = useRef<HTMLDivElement>(null)
  const [value, setValue] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [error, setError] = useState<string | null>(null)
  /** 面板朝上还是朝下：打开时按输入框位置决定一次，滚动中不跳动。 */
  const [dropUp, setDropUp] = useState(false)
  const [maxHeight, setMaxHeight] = useState<number | undefined>(undefined)

  /** 打开面板前测量可用空间（视口底部不够就向上展开）。 */
  const measure = () => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    const up = shouldDropUp(rect.bottom, rect.top, window.innerHeight)
    setDropUp(up)
    setMaxHeight(panelMaxHeight(rect.bottom, rect.top, window.innerHeight, up))
  }

  const term = useDebouncedValue(value, 300).trim()
  const list = usePokemonList(
    { page: 1, page_size: SEARCH_LIMIT, q: term || undefined, prefix: true },
    { enabled: term.length > 0 },
  )
  // 已在队伍里的仍列出来（标「已在队伍」），点它给出明确提示，而不是凭空消失
  const results = useMemo(() => (term ? (list.data?.items ?? []) : []), [term, list.data])

  // 查询变化后重置高亮项（与图鉴搜索栏同一写法，避免渲染期索引越界）
  const [syncedTerm, setSyncedTerm] = useState(term)
  if (syncedTerm !== term) {
    setSyncedTerm(term)
    setActive(0)
  }

  useEffect(() => {
    if (!open) return
    const handler = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  /**
   * 空配置：推荐值由成员编辑器在拉到 `/team-options` 后填入，人工可改。
   *
   * 默认值按对战习惯给：**闪光、100 级、雌性**。性别先按中性处理，
   * 编辑器拿到 `gender_rate` 后再校正（尼多朗这类只能雄性的会改成雄性）。
   */
  const emptyMember = (dex: number, showdownName: string): TeamMember => ({
    position: usedDex.length,
    dex_number: dex,
    showdown_name: showdownName,
    item: null,
    ability: null,
    nature: null,
    evs: [0, 0, 0, 0, 0, 0],
    ivs: [31, 31, 31, 31, 31, 31],
    moves: [],
    tera_type: null,
    gender: 'F',
    shiny: true,
    level: 100,
    // 极巨化等级只在剑盾有；默认 10（Showdown 的默认值），可逐只调整
    dynamax_level: formatKey === 'swsh' ? 10 : null,
    gigantamax: false,
  })

  const add = (dex: number, showdownName: string) => {
    if (usedDex.includes(dex)) {
      setError('这只已经在队伍里了（同一编号不能重复）')
      return
    }
    setError(null)
    onAdd(emptyMember(dex, showdownName))
    setValue('')
    setOpen(false)
    setActive(0)
  }

  const submit = () => {
    const picked = results[active] ?? results[0]
    if (picked) {
      add(picked.dex_number, picked.name_en)
      return
    }
    // 防抖未结束 / 无结果时，纯数字仍可直接按编号加入（英文名稍后由推荐值补全）
    const dex = Number(term)
    if (term && Number.isInteger(dex) && dex > 0) {
      add(dex, `#${dex}`)
      return
    }
    setError(term ? '没有找到匹配的宝可梦，换个名字或编号试试' : '先输入宝可梦名称或图鉴编号')
  }

  const showPanel = open && term.length > 0

  return (
    // Card 默认 overflow-hidden（圆角裁切图片用），但这里要放下拉面板：
    // 面板绝对定位在输入框下方，超出卡片边界会被裁掉，所以显式放开。
    <Card className="overflow-visible border-dashed border-primary/25 bg-primary/[0.025] transition-colors hover:border-primary/40">
      <CardContent className="space-y-2 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <div ref={containerRef} className="relative min-w-40 flex-1">
            <Search
              aria-hidden="true"
              className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={value}
              onChange={(event) => {
                setValue(event.target.value)
                measure()
                setOpen(true)
                setError(null)
              }}
              onFocus={() => {
                measure()
                setOpen(true)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setOpen(false)
                  return
                }
                if (event.key === 'ArrowDown') {
                  event.preventDefault()
                  if (results.length) setActive((index) => (index + 1) % results.length)
                  return
                }
                if (event.key === 'ArrowUp') {
                  event.preventDefault()
                  if (results.length)
                    setActive((index) => (index - 1 + results.length) % results.length)
                  return
                }
                if (event.key === 'Enter') {
                  event.preventDefault()
                  submit()
                }
              }}
              placeholder="搜索中文名 / 英文名 / 编号加入（如「喷火」）…"
              className="h-10 pr-9 pl-9"
              aria-label="添加宝可梦"
              role="combobox"
              aria-expanded={showPanel}
              aria-controls={listboxId}
              aria-autocomplete="list"
            />
            {value ? (
              <button
                type="button"
                onClick={() => {
                  setValue('')
                  setOpen(false)
                  setActive(0)
                }}
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="清空搜索"
              >
                <X aria-hidden="true" className="size-3.5" />
              </button>
            ) : null}

            {showPanel ? (
              <div
                className={cn(
                  'absolute z-50 w-full overflow-y-auto rounded-xl border border-border/70 bg-popover shadow-xl',
                  dropUp ? 'bottom-full mb-1' : 'top-full mt-1',
                )}
                style={{ maxHeight: maxHeight ?? undefined }}
              >
                {list.isPending && results.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-muted-foreground">搜索中…</p>
                ) : list.isError ? (
                  <p className="px-3 py-2 text-xs text-destructive">搜索失败，请稍后再试。</p>
                ) : results.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-muted-foreground">
                    没有匹配的宝可梦 —— 试试中文名、英文名或图鉴编号。
                  </p>
                ) : (
                  <ul id={listboxId} role="listbox" aria-label="宝可梦搜索结果">
                    {results.map((pokemon, index) => {
                      const already = usedDex.includes(pokemon.dex_number)
                      return (
                        <li
                          key={pokemon.dex_number}
                          role="option"
                          aria-selected={index === active}
                        >
                          <button
                            type="button"
                            onClick={() => add(pokemon.dex_number, pokemon.name_en)}
                            onMouseEnter={() => setActive(index)}
                            className={cn(
                              'flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors',
                              index === active ? 'bg-muted' : 'hover:bg-muted/60',
                            )}
                          >
                            <PokemonSprite
                              src={resolveMediaUrl(pokemon.sprite_url)}
                              alt={pokemon.name_zh ?? pokemon.name_en}
                              type={pokemon.types[0]}
                              className="size-6"
                            />
                            <span className="w-11 shrink-0 text-[10px] text-muted-foreground tabular-nums">
                              #{String(pokemon.dex_number).padStart(4, '0')}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-xs">
                              <span className="font-medium">
                                {pokemon.name_zh ?? pokemon.name_en}
                              </span>
                              {pokemon.name_zh ? (
                                <span className="ml-1.5 text-[10px] text-muted-foreground">
                                  {pokemon.name_en}
                                </span>
                              ) : null}
                            </span>
                            {already ? (
                              <Badge variant="outline" className="shrink-0 text-[9px]">
                                已在队伍
                              </Badge>
                            ) : (
                              <span className="flex shrink-0 gap-0.5">
                                {pokemon.types.map((type) => (
                                  <TypeBadge
                                    key={type}
                                    type={type}
                                    className="px-1 py-0 text-[9px]"
                                  />
                                ))}
                              </span>
                            )}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            ) : null}
          </div>

          <Button size="sm" variant="outline" onClick={submit}>
            <Plus aria-hidden="true" />
            加入队伍
          </Button>
          <span className="text-[11px] text-muted-foreground">
            加入后自动填好使用率推荐，可再改 · 当前版本：{formatKey}
          </span>
        </div>
        {error ? (
          <p className="flex items-center gap-1 text-xs text-destructive">
            <AlertCircle aria-hidden="true" className="size-3.5" />
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
