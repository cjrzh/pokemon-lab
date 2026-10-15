import { ArrowRight, CircleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="页面不存在" description="这个地址没有对应的页面。" />
      <Card>
        <CardContent className="space-y-4">
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
            请检查地址是否拼写正确，或从下面的入口返回。
          </p>
          <Button asChild size="sm" variant="outline">
            <Link to="/">
              返回研究所
              <ArrowRight aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        </CardContent>
      </Card>
    </>
  )
}