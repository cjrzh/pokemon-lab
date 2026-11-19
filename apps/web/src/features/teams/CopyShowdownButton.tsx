/**
 * 「复制 Showdown 代码」按钮（单只 / 整队共用）。
 *
 * 放在成员摘要行时是图标按钮；传入 `children` 则渲染成带文字的按钮（整队复制用）。
 * 复制失败时回落到一个可全选的文本框，而不是静默失败 —— 剪贴板权限
 * 在非 HTTPS 或用户拒绝时会被浏览器拦下。
 */

import { useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function CopyShowdownButton({
  text,
  label,
  className,
  children,
  fallbackText = '无法自动复制，请手动全选复制（已带上交易前缀）：',
  fallbackClassName,
}: {
  /** 完整文本（含交易前缀）。 */
  text: string
  /** 无障碍标签与提示，如「复制 喷火龙 的 Showdown 代码」。 */
  label: string
  className?: string
  /** 传入后渲染为带文字的按钮（整队复制）；不传则是图标按钮。 */
  children?: React.ReactNode
  /** 降级文本框上方的说明。 */
  fallbackText?: string
  /** 降级文本框的高度（整队代码比单只长）。 */
  fallbackClassName?: string
}) {
  const [copied, setCopied] = useState(false)
  const [fallback, setFallback] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const flash = () => {
    setCopied(true)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopied(false), 1500)
  }

  const copy = async () => {
    try {
      // 优先用异步剪贴板 API；不可用（旧浏览器 / 非安全上下文）时走降级路径
      if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(text)
      flash()
    } catch {
      setFallback(true)
    }
  }

  if (fallback) {
    return (
      <div className="w-full space-y-1 rounded-md border border-dashed p-1.5">
        <p className="text-[10px] text-muted-foreground">{fallbackText}</p>
        <textarea
          readOnly
          autoFocus
          value={text}
          aria-label={`${label}（手动复制）`}
          onFocus={(event) => event.currentTarget.select()}
          className={cn(
            'h-24 w-full resize-none rounded bg-muted/60 p-1.5 font-mono text-[10px] leading-snug',
            fallbackClassName,
          )}
        />
        <Button size="xs" variant="outline" onClick={() => setFallback(false)}>
          关闭
        </Button>
      </div>
    )
  }

  return (
    <Button
      size={children ? 'sm' : 'icon-sm'}
      variant={children ? 'outline' : 'ghost'}
      onClick={() => void copy()}
      aria-label={label}
      title={label}
      className={cn(children ? '' : 'shrink-0', className)}
    >
      {copied ? (
        <Check aria-hidden="true" className="text-success" />
      ) : (
        <Copy aria-hidden="true" />
      )}
      {children}
    </Button>
  )
}
