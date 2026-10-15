import { PageHeader } from '@/components/common/PageHeader'
import { RoadmapCard } from '@/components/common/RoadmapCard'

export function TypeCalcPage() {
  return (
    <>
      <PageHeader
        title="属性克制"
        description="给定进攻属性与 1–2 个防守属性，计算最终倍率；也支持反向查询「谁克我」。"
      />
      <RoadmapCard
        phase="P3"
        title="属性克制计算器"
        description="核心计算逻辑放在纯函数中，前后端共用同一份测试向量。"
        items={[
          '18 属性单属性倍率表，以及与后端共享的规范数据文件',
          '双属性相乘计算，覆盖 0 倍免疫与 4 倍双重克制等边界',
          '反向查询：给定防守属性组合，列出所有克制它的进攻属性及倍率',
          '世代切换（Gen 1–9）；MVP 先交付 Gen 6+，1–5 逐步补齐并在补齐前明确标注',
          '关键计算逻辑的单元测试：后端 pytest 与前端 Vitest 使用同一份 cases 文件',
          '输入非法或超范围时给出明确提示，而不是静默返回错误结果',
        ]}
        note="计算在浏览器本地完成（数据随包加载），不依赖网络，因此断网也能用。"
      />
    </>
  )
}