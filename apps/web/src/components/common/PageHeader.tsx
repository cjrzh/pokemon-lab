import type { ReactNode } from 'react'

export interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
}

/** 统一页面头部：渐变装饰线、标题层级与操作区在所有页面保持一致。 */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <div
          aria-hidden="true"
          className="glow-line mb-3.5 h-1 w-10 rounded-full opacity-90"
        />
        <h1 className="font-heading text-[1.7rem] leading-[1.15] font-semibold tracking-tight sm:text-[2rem]">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-3xl text-[13px] leading-6 text-muted-foreground sm:text-sm">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </header>
  )
}
