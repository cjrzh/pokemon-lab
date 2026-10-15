import { PageHeader } from '@/components/common/PageHeader'
import { RoadmapCard } from '@/components/common/RoadmapCard'

export function NotesPage() {
  return (
    <>
      <PageHeader
        title="笔记"
        description="记录研究所的发现、队伍构想与待验证的猜想。"
      />
      <RoadmapCard
        phase="P4"
        title="研究所笔记"
        description="与收藏共用同一套数据层与匿名身份机制。"
        items={[
          '自由笔记正文，支持 Markdown 文本',
          '标签（tag）与规则版本（ruleset）关联',
          '按标题 / 标签搜索，按更新时间排序',
          '笔记的创建、编辑、删除与失败回滚',
          '空状态与加载状态可见，避免「白屏不知道发生了什么」',
        ]}
        note="后续阶段的「实验日志」页面会复用这里的笔记数据层，不另起一套存储。"
      />
    </>
  )
}