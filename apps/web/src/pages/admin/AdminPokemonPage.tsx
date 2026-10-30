import { useState } from 'react'
import { CircleAlert, Pencil, Plus, RefreshCw, Save, X } from 'lucide-react'

import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { TypeBadge } from '@/features/dex/components/TypeBadge'
import { useDebouncedValue, usePokemonList } from '@/features/dex/hooks'
import { useCreatePokemon, useEditPokemon } from '@/features/admin/hooks'
import { TYPES } from '@/features/type-chart/data'
import { describeApiError } from '@/lib/apiClient'

export function AdminPokemonPage() {
  const [search, setSearch] = useState('')
  const debounced = useDebouncedValue(search, 300)
  const [editingDex, setEditingDex] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)

  const list = usePokemonList({ page: 1, page_size: 100, q: debounced.trim() || undefined })

  return (
    <>
      <PageHeader
        title="图鉴编辑"
        description="手动修正同步数据的字段，或新增自定义条目。编辑过的条目标记为「手动维护」，后续同步不会覆盖。"
        actions={
          <Button size="sm" variant="outline" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" />
            新增条目
          </Button>
        }
      />

      {creating ? (
        <CreateForm onClose={() => setCreating(false)} />
      ) : null}

      <div className="mb-4">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="按名称筛选（中/英）…"
          aria-label="筛选图鉴条目"
        />
      </div>

      {list.isPending ? (
        <Card>
          <CardContent className="space-y-2 pt-6">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </CardContent>
        </Card>
      ) : list.isError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>图鉴列表加载失败</AlertTitle>
          <AlertDescription>{describeApiError(list.error)}</AlertDescription>
        </Alert>
      ) : list.data.items.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          本地还没有图鉴数据 —— 先到「数据同步」页拉取，或用「新增条目」手动添加。
        </Card>
      ) : (
        <ul className="space-y-2">
          {list.data.items.map((p) => (
            <li key={p.dex_number}>
              {editingDex === p.dex_number ? (
                <EditForm
                  dexNumber={p.dex_number}
                  nameEn={p.name_en}
                  nameZh={p.name_zh}
                  types={p.types}
                  onClose={() => setEditingDex(null)}
                />
              ) : (
                <Card className="flex-row items-center justify-between gap-3 px-4 py-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="w-12 shrink-0 text-xs text-muted-foreground tabular-nums">
                      #{String(p.dex_number).padStart(3, '0')}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {p.name_zh ?? p.name_en}
                        {p.name_zh ? (
                          <span className="ml-1.5 text-xs text-muted-foreground">{p.name_en}</span>
                        ) : null}
                      </p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {p.types.map((t) => (
                          <TypeBadge key={t} type={t} className="px-1.5 py-0 text-[10px]" />
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {p.is_demo ? <Badge variant="secondary">演示</Badge> : null}
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label={`编辑 ${p.name_zh ?? p.name_en}`}
                      onClick={() => setEditingDex(p.dex_number)}
                    >
                      <Pencil aria-hidden="true" />
                    </Button>
                  </div>
                </Card>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

/** 编辑表单：名称与属性（MVP 最常用的修正字段）。 */
function EditForm({
  dexNumber,
  nameEn,
  nameZh,
  types,
  onClose,
}: {
  dexNumber: number
  nameEn: string
  nameZh: string | null
  types: string[]
  onClose: () => void
}) {
  const [en, setEn] = useState(nameEn)
  const [zh, setZh] = useState(nameZh ?? '')
  const [genus, setGenus] = useState('')
  const [flavor, setFlavor] = useState('')
  const [selectedTypes, setSelectedTypes] = useState<string[]>(types)
  const edit = useEditPokemon(dexNumber)

  const toggleType = (type: string) => {
    setSelectedTypes((current) =>
      current.includes(type)
        ? current.filter((t) => t !== type)
        : current.length >= 2
          ? current
          : [...current, type],
    )
  }

  return (
    <Card className="ring-primary/30">
      <CardHeader>
        <CardTitle className="text-sm">编辑 #{dexNumber}</CardTitle>
        <CardDescription>保存后该条目标记为「手动维护」，同步不再覆盖。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor={`edit-en-${dexNumber}`}>英文名</Label>
            <Input
              id={`edit-en-${dexNumber}`}
              value={en}
              onChange={(event) => setEn(event.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor={`edit-zh-${dexNumber}`}>中文名</Label>
            <Input
              id={`edit-zh-${dexNumber}`}
              value={zh}
              onChange={(event) => setZh(event.target.value)}
              placeholder="留空表示无中文名"
              className="mt-1.5"
            />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor={`edit-genus-${dexNumber}`}>分类（如「种子宝可梦」）</Label>
            <Input
              id={`edit-genus-${dexNumber}`}
              value={genus}
              onChange={(event) => setGenus(event.target.value)}
              placeholder="留空不修改"
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor={`edit-flavor-${dexNumber}`}>图鉴描述</Label>
            <Input
              id={`edit-flavor-${dexNumber}`}
              value={flavor}
              onChange={(event) => setFlavor(event.target.value)}
              placeholder="留空不修改"
              className="mt-1.5"
            />
          </div>
        </div>
        <div>
          <Label>属性（最多 2 个）</Label>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {TYPES.map(({ name, zh: typeZh }) => (
              <button
                key={name}
                type="button"
                onClick={() => toggleType(name)}
                aria-pressed={selectedTypes.includes(name)}
                className={
                  'rounded-md px-2 py-1 text-xs font-medium transition-transform ' +
                  (selectedTypes.includes(name)
                    ? 'scale-105 ring-2 ring-ring'
                    : 'opacity-60 hover:opacity-100')
                }
              >
                <TypeBadge type={name} />
                <span className="sr-only">{typeZh}</span>
              </button>
            ))}
          </div>
        </div>

        {edit.isError ? (
          <Alert variant="destructive">
            <CircleAlert aria-hidden="true" />
            <AlertDescription>{describeApiError(edit.error)}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={edit.isPending || !en.trim() || selectedTypes.length === 0}
            onClick={() =>
              edit.mutate(
                {
                  name_en: en.trim(),
                  name_zh: zh.trim() || undefined,
                  types: selectedTypes,
                  ...(genus.trim() ? { genus_zh: genus.trim() } : {}),
                  ...(flavor.trim() ? { flavor_zh: flavor.trim() } : {}),
                },
                { onSuccess: onClose },
              )
            }
          >
            {edit.isPending ? (
              <RefreshCw aria-hidden="true" className="animate-spin" />
            ) : (
              <Save aria-hidden="true" />
            )}
            保存
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>
            <X aria-hidden="true" />
            取消
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

/** 新增表单。 */
function CreateForm({ onClose }: { onClose: () => void }) {
  const [dex, setDex] = useState('')
  const [en, setEn] = useState('')
  const [zh, setZh] = useState('')
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [isDemo, setIsDemo] = useState(true)
  const create = useCreatePokemon()

  const valid = Number(dex) >= 1 && en.trim() && selectedTypes.length > 0

  const toggleType = (type: string) => {
    setSelectedTypes((current) =>
      current.includes(type)
        ? current.filter((t) => t !== type)
        : current.length >= 2
          ? current
          : [...current, type],
    )
  }

  return (
    <Card className="mb-4 ring-primary/30">
      <CardHeader>
        <CardTitle className="text-sm">新增图鉴条目</CardTitle>
        <CardDescription>
          用于补充自定义或演示条目。演示数据会带显式标记，不冒充真实数据。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="create-dex">图鉴编号</Label>
            <Input
              id="create-dex"
              type="number"
              min={1}
              value={dex}
              onChange={(event) => setDex(event.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="create-en">英文名</Label>
            <Input
              id="create-en"
              value={en}
              onChange={(event) => setEn(event.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label htmlFor="create-zh">中文名</Label>
            <Input
              id="create-zh"
              value={zh}
              onChange={(event) => setZh(event.target.value)}
              placeholder="留空表示无中文名"
              className="mt-1.5"
            />
          </div>
        </div>
        <div>
          <Label>属性（最多 2 个）</Label>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {TYPES.map(({ name, zh: typeZh }) => (
              <button
                key={name}
                type="button"
                onClick={() => toggleType(name)}
                aria-pressed={selectedTypes.includes(name)}
                className={
                  'rounded-md px-2 py-1 text-xs font-medium transition-transform ' +
                  (selectedTypes.includes(name)
                    ? 'scale-105 ring-2 ring-ring'
                    : 'opacity-60 hover:opacity-100')
                }
              >
                <TypeBadge type={name} />
                <span className="sr-only">{typeZh}</span>
              </button>
            ))}
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={isDemo}
            onChange={(event) => setIsDemo(event.target.checked)}
            className="size-4 accent-(--primary)"
          />
          标记为演示数据
        </label>

        {create.isError ? (
          <Alert variant="destructive">
            <CircleAlert aria-hidden="true" />
            <AlertDescription>{describeApiError(create.error)}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={create.isPending || !valid}
            onClick={() =>
              create.mutate(
                {
                  dex_number: Number(dex),
                  name_en: en.trim(),
                  name_zh: zh.trim() || undefined,
                  types: selectedTypes,
                  is_demo: isDemo,
                },
                { onSuccess: onClose },
              )
            }
          >
            {create.isPending ? (
              <RefreshCw aria-hidden="true" className="animate-spin" />
            ) : (
              <Plus aria-hidden="true" />
            )}
            创建
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>
            <X aria-hidden="true" />
            取消
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
