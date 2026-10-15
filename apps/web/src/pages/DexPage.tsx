import { PageHeader } from '@/components/common/PageHeader'
import { RoadmapCard } from '@/components/common/RoadmapCard'

export function DexPage() {
  return (
    <>
      <PageHeader
        title="图鉴"
        description="检索宝可梦，查看属性、种族值、特性与进化信息。"
      />
      <RoadmapCard
        phase="P2"
        title="图鉴与搜索"
        description="数据来自 PokéAPI，同步到本地 SQLite 后离线可用。"
        items={[
          '列表分页 + 按属性 / 世代筛选',
          '名称搜索（中文名与英文名），带输入防抖',
          '详情页：属性、种族值、特性、进化链、第几代登场',
          '列表与详情统一处理「加载中 / 空结果 / 请求失败 / 缓存过期」四种状态',
          '同步脚本 scripts/sync_pokeapi.py 手动预拉取首批 #1-151',
          '每条记录展示数据来源与同步时间；演示数据带显式标记',
        ]}
        note="PokéAPI 不可用时会回退到本地已同步数据，并在界面上标注「数据可能过期」。"
      />
    </>
  )
}