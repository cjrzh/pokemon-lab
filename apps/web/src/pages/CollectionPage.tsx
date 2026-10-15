import { PageHeader } from '@/components/common/PageHeader'
import { RoadmapCard } from '@/components/common/RoadmapCard'

export function CollectionPage() {
  return (
    <>
      <PageHeader title="收藏" description="收藏宝可梦，并记录自己的备注与使用心得。" />
      <RoadmapCard
        phase="P4"
        title="我的收藏"
        description="数据持久化在后端 SQLite，按匿名身份隔离。"
        items={[
          '在图鉴与详情页收藏 / 取消收藏宝可梦',
          '收藏列表：支持排序与备注编辑',
          '每条收藏可关联规则版本（ruleset），便于区分不同对战场合',
          '通过匿名 owner key 隔离数据：同一浏览器内跨页面、刷新后依然保留',
          '空状态、加载中、保存失败三态可见，保存失败不会静默丢数据',
        ]}
        note="MVP 不做账号体系：换设备或清理浏览器数据会得到一个新的空白身份，该限制会写入 README。"
      />
    </>
  )
}