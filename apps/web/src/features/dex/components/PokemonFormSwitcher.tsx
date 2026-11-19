/**
 * 图鉴详情页的形态切换菜单。
 *
 * 形态来自 PokéAPI 的 `varieties`，后端只收录机制上不同的（属性 / 种族值 / 特性 /
 * 身高体重有差异），例如武道熊师的「一击流 / 连击流」、洛托姆的六种家电形态。
 * 纯外观差异（超极巨化、霸主、性别）不收录，菜单里也不会出现。
 *
 * 交互参考宝可梦百科的形态条目：一排可点击的胶囊按钮，选中项高亮并展示其属性；
 * 点击后由父组件切换当前形态（属性、种族值、特性、立绘随之更新）。
 */

import { cn } from '@/lib/utils'

import { PokemonSprite } from './PokemonSprite'
import { TypeBadge } from './TypeBadge'
import type { PokemonFormSummary } from '../api'

export function PokemonFormSwitcher({
  forms,
  active,
  onSelect,
  spriteUrl,
}: {
  forms: PokemonFormSummary[]
  /** 当前形态 slug；默认形态用 `DEFAULT_FORM_NAME`。 */
  active: string
  onSelect: (name: string) => void
  /** 把相对路径补成可访问地址（与页面其它图片一致）。 */
  spriteUrl?: (path: string | null) => string | undefined
}) {
  if (forms.length <= 1) return null

  return (
    <div className="mt-3">
      <p className="mb-1.5 text-[11px] font-medium text-muted-foreground">
        形态（{forms.length}）
      </p>
      <ul className="flex flex-wrap gap-1.5" role="group" aria-label="选择宝可梦形态">
        {forms.map((form) => {
          const isActive = form.name === active
          return (
            <li key={form.name}>
              <button
                type="button"
                onClick={() => onSelect(form.name)}
                aria-pressed={isActive}
                title={form.name_en ?? form.label}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs transition-colors',
                  isActive
                    ? 'border-primary bg-primary/10 font-medium text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <PokemonSprite
                  src={spriteUrl?.(form.sprite_url)}
                  alt={form.label}
                  type={form.types[0]}
                  className="size-5"
                />
                <span className="max-w-36 truncate">{form.label}</span>
                {form.types.map((type) => (
                  <TypeBadge key={type} type={type} className="px-1 py-0 text-[9px]" />
                ))}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
