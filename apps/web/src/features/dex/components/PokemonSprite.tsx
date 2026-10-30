/**
 * 宝可梦小图标（96×96 sprite）。
 *
 * 用途：列表行、特性拥有者等「只需认出是哪只」的位置。与立绘分开的原因：
 *   - 小图体积小（约 1 KB），一页几十行时加载成本可忽略；
 *   - 本地缓存优先（`/media/sprites/{dex}.png`），离线可用；缺失时回落到远程代理。
 *   - 加载失败显示占位圆点，不伪造图片。
 */

import { useState } from 'react'

import { cn } from '@/lib/utils'

export interface PokemonSpriteProps {
  src: string | null | undefined
  alt: string
  /** 是否按主属性着色底圈（列表与特性页都用主属性色，便于扫读）。 */
  type?: string | null
  className?: string
  imageClassName?: string
}

export function PokemonSprite({
  src,
  alt,
  type,
  className,
  imageClassName,
}: PokemonSpriteProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const visible = Boolean(src) && failedSrc !== src

  return (
    <span
      className={cn(
        'relative inline-flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-full',
        className,
      )}
      style={{
        backgroundColor: type
          ? `color-mix(in oklab, var(--type-${type}) 22%, transparent)`
          : 'var(--muted)',
      }}
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
        <span
          aria-hidden="true"
          className="size-1.5 rounded-full"
          style={{ backgroundColor: type ? `var(--type-${type})` : 'var(--muted-foreground)' }}
        />
      )}
    </span>
  )
}
