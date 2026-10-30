import { useState } from 'react'
import { ImageOff, Sparkles, Star } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface PokemonArtworkProps {
  src: string | null | undefined
  fallbackSrc?: string | null
  alt: string
  /** 图片容器尺寸类（默认由调用方决定）。 */
  className?: string
  /** 图片本体尺寸类。 */
  imageClassName?: string
  /** 是否显示「传说 / 幻之宝可梦」角标。 */
  legendary?: boolean
  mythical?: boolean
  /** 圆形之外的外框样式（列表卡片用小尺寸，详情页用大尺寸）。 */
  variant?: 'card' | 'hero' | 'plain'
}

/**
 * 宝可梦立绘：本地缓存优先，加载失败时回落到远程地址，再失败显示占位。
 *
 * 占位不伪造图片 —— 缺失时明确显示「暂无图片」，与项目「不虚构数据」的约定一致。
 */
export function PokemonArtwork({
  src,
  fallbackSrc,
  alt,
  className,
  imageClassName,
  legendary = false,
  mythical = false,
  variant = 'card',
}: PokemonArtworkProps) {
  // 记录已失败过的图片地址，而不是单纯的状态位：翻页/换一只时地址变化，
  // 旧地址的失败不会影响新图片（不需要在 effect 里同步 state）。
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const [failedFallback, setFailedFallback] = useState<string | null>(null)

  const primaryOk = Boolean(src) && failedSrc !== src
  const fallbackOk = Boolean(fallbackSrc) && failedFallback !== fallbackSrc
  const resolved = primaryOk ? src : fallbackOk ? fallbackSrc : null

  return (
    <div
      className={cn(
        'relative flex items-center justify-center overflow-hidden',
        variant === 'card' && 'rounded-xl bg-linear-to-b from-muted/70 to-muted',
        variant === 'hero' && 'rounded-2xl bg-linear-to-b from-muted/60 via-muted/40 to-transparent',
        // plain：底色由调用方提供（如按主属性着色），这里只管裁切
        variant === 'plain' && 'rounded-lg',
        className,
      )}
    >
      {resolved ? (
        <img
          src={resolved}
          alt={alt}
          loading={variant === 'hero' ? 'eager' : 'lazy'}
          decoding="async"
          className={cn(
            'size-full object-contain drop-shadow-sm',
            variant === 'hero' && 'scale-105',
            imageClassName,
          )}
          onError={() => {
            if (primaryOk) setFailedSrc(src ?? null)
            else setFailedFallback(fallbackSrc ?? null)
          }}
        />
      ) : (
        <div className="flex flex-col items-center gap-1 text-muted-foreground">
          <ImageOff aria-hidden="true" className={variant === 'hero' ? 'size-10' : 'size-5'} />
          {variant === 'hero' ? <span className="text-xs">暂无立绘</span> : null}
        </div>
      )}

      {variant !== 'hero' && (legendary || mythical) ? (
        <span
          className="absolute top-1.5 right-1.5 inline-flex items-center gap-0.5 rounded-full bg-background/85 px-1.5 py-0.5 text-[10px] font-medium text-foreground shadow-sm backdrop-blur"
          title={mythical ? '幻之宝可梦' : '传说的宝可梦'}
        >
          {mythical ? (
            <Sparkles aria-hidden="true" className="size-2.5 text-primary" />
          ) : (
            <Star aria-hidden="true" className="size-2.5 text-warning" />
          )}
          {mythical ? '幻' : '传说'}
        </span>
      ) : null}
    </div>
  )
}
