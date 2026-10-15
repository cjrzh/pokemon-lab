import { Construction } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export interface RoadmapCardProps {
  /** 交付阶段，例如 "P2" */
  phase: string
  title: string
  description: string
  items: readonly string[]
  note?: string
}

/**
 * 未实现页面的统一说明卡。
 *
 * 刻意不提供任何「假的可用界面」：明确告诉用户该功能尚未交付、计划做什么，
 * 避免用演示数据伪装成已完成功能。
 */
export function RoadmapCard({ phase, title, description, items, note }: RoadmapCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{phase}</Badge>
          <CardTitle>{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Construction aria-hidden="true" className="size-4 shrink-0" />
          该页面尚未实现，以下为本阶段计划交付的内容。
        </p>
        <ul className="space-y-1.5 text-sm">
          {items.map((item) => (
            <li key={item} className="flex gap-2.5">
              <span
                aria-hidden="true"
                className="mt-2 size-1.5 shrink-0 rounded-full bg-muted-foreground/50"
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
      </CardContent>
    </Card>
  )
}