/**
 * 列表拖动排序（HTML5 Drag and Drop，零依赖）。
 *
 * 为什么不用 drag 库：需求只有「在同一个列表里上下挪一位」，HTML5 DnD
 * 足够用，也不用为一个交互装一个 20KB 的依赖。
 *
 * 交互约定：
 *   - 只有**拖动手柄**可拖（`draggable` 放在手柄上），避免在输入框里选文字时误拖；
 *   - 拖到目标行中部时插入到该行位置（按鼠标相对行高的前后半决定插前还是插后）；
 *   - 拖动中给源行半透明、目标位置画一条指示线。
 *
 * 泛型化：成员编辑器与左侧队伍列表都用它，两者只需要 `{ id }`。
 * 键盘可访问性由调用方提供「上移 / 下移」按钮（见各列表）。
 */

import { useRef, useState } from 'react'

import { moveItem } from '@/features/teams/reorder'

export interface DragState {
  /** 正在拖的条目下标；未拖动为 null。 */
  from: number | null
  /** 插入指示线的位置（0..length），拖动时显示。 */
  over: number | null
}

export function useListReorder<T>(
  items: T[],
  onReorder: (items: T[]) => void,
  /** 稳定标识：只用于 React key 与拖动提示，不参与排序计算。 */
  keyOf: (item: T) => string | number = (item) => (item as { id: number }).id,
) {
  const [drag, setDrag] = useState<DragState>({ from: null, over: null })
  /** 拖动的下标放 ref 里：dragover 高频触发，读 state 会有一帧延迟。 */
  const fromRef = useRef<number | null>(null)

  const reset = () => {
    fromRef.current = null
    setDrag({ from: null, over: null })
  }

  /** 手柄上的 onDragStart。 */
  const start = (index: number) => (event: React.DragEvent) => {
    fromRef.current = index
    setDrag({ from: index, over: index })
    event.dataTransfer.effectAllowed = 'move'
    // Firefox 需要设置数据才会真正开始拖动
    event.dataTransfer.setData('text/plain', String(index))
  }

  /** 行上的 onDragOver：按指针在半行上/下决定插入点。 */
  const over = (index: number) => (event: React.DragEvent) => {
    if (fromRef.current === null) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    const rect = event.currentTarget.getBoundingClientRect()
    const after = event.clientY > rect.top + rect.height / 2
    setDrag({ from: fromRef.current, over: index + (after ? 1 : 0) })
  }

  /** 行上的 onDrop：把源条目移动到指示线位置。 */
  const drop = (event: React.DragEvent) => {
    event.preventDefault()
    const from = fromRef.current
    const to = drag.over
    reset()
    if (from === null || to === null) return

    // 插入点在被拖项之后时，移除源元素会让目标下标前移一位
    const target = to > from ? to - 1 : to
    const next = moveItem(items, from, target)
    if (next !== items) onReorder(next)
  }

  return {
    drag,
    keyOf,
    handleProps: (index: number) => ({
      draggable: true,
      onDragStart: start(index),
      onDragEnd: reset,
    }),
    rowProps: (index: number) => ({
      onDragOver: over(index),
      onDrop: drop,
      // 拖到行边缘以外时隐藏指示线
      onDragLeave: (event: React.DragEvent) => {
        const rect = event.currentTarget.getBoundingClientRect()
        if (
          event.clientX < rect.left ||
          event.clientX > rect.right ||
          event.clientY < rect.top ||
          event.clientY > rect.bottom
        ) {
          setDrag((current) => ({ ...current, over: null }))
        }
      },
    }),
    isDragging: (index: number) => drag.from === index,
    /** 该行上方是否要画插入线。 */
    showLineBefore: (index: number) => drag.from !== null && drag.over === index,
    /** 该行下方是否要画插入线（列表最后一行）。 */
    showLineAfter: (index: number) =>
      drag.from !== null && index === items.length - 1 && drag.over === items.length,
  }
}

/** 兼容旧名：成员编辑器仍用 `useMemberReorder`。 */
export const useMemberReorder = useListReorder
