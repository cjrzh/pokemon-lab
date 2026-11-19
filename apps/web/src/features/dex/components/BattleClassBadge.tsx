/**
 * 对战分类徽章。
 *
 * 分类是**项目整理的规范数据**（`data/battle-classes.json`），不是官方字段：
 * 一级神 / 二级神的界限来自 VGC「限制传说的宝可梦」规则，准神是社区约定。
 * 普通不显示徽章 —— 图上大部分都是普通，全标出来反而噪声。
 */

import { Badge } from '@/components/ui/badge'
import { BATTLE_CLASS_LABEL, type BattleClass } from '@/features/dex/api'
import { cn } from '@/lib/utils'

const STYLES: Record<Exclude<BattleClass, 'normal'>, string> = {
  restricted: 'border-transparent bg-destructive/10 text-destructive',
  sub_legendary: 'border-transparent bg-warning/15 text-warning',
  mythical: 'border-transparent bg-primary/10 text-primary',
  pseudo_legendary: 'border-transparent bg-foreground/10 text-foreground',
  paradox: 'border-transparent bg-[color-mix(in_oklab,var(--type-psychic)_18%,transparent)] text-[var(--type-psychic)]',
}

export function BattleClassBadge({
  battleClass,
  className,
  showNormal = false,
}: {
  battleClass: BattleClass
  className?: string
  /** 为 true 时连「普通」也显示（筛选结果页可用来确认分类）。 */
  showNormal?: boolean
}) {
  if (battleClass === 'normal' && !showNormal) return null
  return (
    <Badge
      variant="outline"
      className={cn(
        'shrink-0 px-1.5 py-0 text-[9px] font-medium',
        battleClass !== 'normal' && STYLES[battleClass],
        className,
      )}
      title={`对战分类：${BATTLE_CLASS_LABEL[battleClass]}（项目整理，非官方字段）`}
    >
      {BATTLE_CLASS_LABEL[battleClass]}
    </Badge>
  )
}
