/**
 * 属性徽章：用设计令牌中的 18 属性色渲染。
 *
 * 颜色由 tokens.css 的 --type-* 生成（bg-type-fire 等），前景色按对比度择取
 * （text-type-*-fg），保证徽章内文字可读。
 */

import { ZH as TYPE_ZH } from '@/features/type-chart/data'
import { cn } from '@/lib/utils'

export interface TypeBadgeProps {
  type: string
  className?: string
}

export function TypeBadge({ type, className }: TypeBadgeProps) {
  const zh = TYPE_ZH[type] ?? type
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        'bg-type-' + type,
        'text-type-' + type + '-fg',
        className,
      )}
    >
      {zh}
    </span>
  )
}
