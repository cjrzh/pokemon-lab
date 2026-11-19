export interface BrandMarkProps {
  className?: string
}

/**
 * 项目标志：原创绘制的精灵球，不使用任何官方美术素材。
 * 颜色全部取自设计令牌（描边用 currentColor），在浅色 / 深色侧边栏与
 * 不同背景上都能保持同一识别度。
 */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="Pokémon Lab 标志">
      <circle cx="32" cy="32" r="27" fill="var(--card)" stroke="currentColor" strokeWidth="4.5" />
      <path
        d="M5 32a27 27 0 0 1 54 0Z"
        fill="var(--type-fire)"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="32" r="9" fill="var(--card)" stroke="currentColor" strokeWidth="4.5" />
      <circle cx="32" cy="32" r="3.5" fill="var(--primary)" />
    </svg>
  )
}
