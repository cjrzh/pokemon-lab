/**
 * 属性徽章：用设计令牌中的 18 属性色渲染。
 *
 * 颜色直接引用 CSS 变量（--type-*），而不是拼接 `bg-type-${type}` 类名 ——
 * Tailwind 在构建期扫描源码，动态拼接的类名不会被生成，18 个属性里只有
 * 静态写到的几个能拿到背景色。用 inline style 引用令牌可保证全部属性生效，
 * 深浅色主题切换也照常工作。
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
        className,
      )}
      style={{
        backgroundColor: `var(--type-${type}, var(--muted))`,
        color: `var(--type-${type}-fg, var(--muted-foreground))`,
      }}
    >
      {zh}
    </span>
  )
}
