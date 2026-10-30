/**
 * 道具图标（30×30 sprite）。
 *
 * 与宝可梦小图标同样的约定：本地缓存优先（`/media/items/{slug}.png`），
 * 加载失败显示占位方块；没有地址时不渲染图片。
 * 道具图标比宝可梦 sprite 更小，默认尺寸 16px，避免撑高列表行。
 */

import { useState } from 'react'

import { cn } from '@/lib/utils'

export interface ItemIconProps {
  src: string | null | undefined
  alt: string
  className?: string
  imageClassName?: string
}

export function ItemIcon({ src, alt, className, imageClassName }: ItemIconProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const visible = Boolean(src) && failedSrc !== src

  return (
    <span
      aria-hidden={visible ? undefined : true}
      className={cn(
        'inline-flex size-4 shrink-0 items-center justify-center overflow-hidden rounded-sm',
        !visible && 'bg-muted',
        className,
      )}
    >
      {visible ? (
        <img
          src={src ?? undefined}
          alt={alt}
          loading="lazy"
          decoding="async"
          className={cn('size-full object-contain', imageClassName)}
          onError={() => setFailedSrc(src ?? null)}
        />
      ) : (
        <span className="size-1 rounded-[1px] bg-muted-foreground/50" />
      )}
    </span>
  )
}
