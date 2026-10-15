import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

/** 404 页：一只走丢的宝可梦提示，保持克制的幽默感。 */
export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center py-12 text-center">
      {/* 迷路的胖丁轮廓：原创简笔，呼应「迷路了」的语境 */}
      <svg
        aria-hidden="true"
        viewBox="0 0 96 96"
        className="mb-6 size-24 text-muted-foreground/60"
      >
        <circle cx="48" cy="48" r="30" fill="none" stroke="currentColor" strokeWidth="4" />
        <path
          d="M18 48a30 30 0 0 1 60 0"
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
        />
        <circle cx="48" cy="48" r="11" fill="none" stroke="currentColor" strokeWidth="4" />
        <circle cx="48" cy="48" r="4" fill="currentColor" />
        <path
          d="M8 42 C4 36 6 28 12 26 M88 42 C92 36 90 28 84 26"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <h1 className="font-heading text-2xl font-semibold tracking-tight">
        这里没有野生宝可梦
      </h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        你好像走进了一片高草丛 —— 这个地址没有对应的页面。
      </p>
      <Button asChild size="sm" variant="outline" className="mt-6">
        <Link to="/">
          回到研究所
          <ArrowRight aria-hidden="true" data-icon="inline-end" />
        </Link>
      </Button>
    </div>
  )
}
