export interface BrandMarkProps {
  className?: string
}

/** 项目标志：原创绘制的精灵球，不使用任何官方美术素材。 */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="Pokémon Lab 标志">
      <circle cx="32" cy="32" r="27" fill="#f4f4f5" stroke="currentColor" strokeWidth="5" />
      <path
        d="M5 32a27 27 0 0 1 54 0Z"
        fill="#ee8130"
        stroke="currentColor"
        strokeWidth="5"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="32" r="9" fill="#fafafa" stroke="currentColor" strokeWidth="5" />
      <circle cx="32" cy="32" r="3.5" fill="currentColor" />
    </svg>
  )
}