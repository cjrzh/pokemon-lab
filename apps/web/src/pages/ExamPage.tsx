import { PageHeader } from '@/components/common/PageHeader'
import { RoadmapCard } from '@/components/common/RoadmapCard'

export function ExamPage() {
  return (
    <>
      <PageHeader
        title="大师考试"
        description="从属性克制与图鉴事实中组卷，答完评分并自动收录错题。"
      />
      <RoadmapCard
        phase="P5"
        title="大师考试 v0"
        description="MVP 采用规则模板组卷，不接入 LLM 出题。"
        items={[
          '题库：选择题与判断题，由本地事实规则生成（属性倍率、种族值、特性等）',
          '组卷配置：知识范围、题量、题型、世代 / 规则版本',
          '逐题作答、交卷评分、成绩记录',
          '错题本：由答题记录派生，不单独维护一份可能不同步的数据',
          '每道题展示其来源（source_ref），不出现无来源的题目',
          '组卷与评分逻辑为纯函数，带单元测试，保证同种子可复现',
        ]}
        note="题库只基于仓库内可追溯的事实数据生成，答案可回溯到具体数据来源。"
      />
    </>
  )
}