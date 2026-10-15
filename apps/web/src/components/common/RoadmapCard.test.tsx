import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RoadmapCard } from './RoadmapCard'

describe('RoadmapCard', () => {
  it('渲染阶段标记、标题、描述与全部计划条目', () => {
    render(
      <RoadmapCard
        phase="P2"
        title="图鉴与搜索"
        description="数据来自 PokéAPI。"
        items={['第一条计划', '第二条计划']}
        note="补充说明"
      />,
    )

    expect(screen.getByText('P2')).toBeInTheDocument()
    expect(screen.getByText('图鉴与搜索')).toBeInTheDocument()
    expect(screen.getByText('数据来自 PokéAPI。')).toBeInTheDocument()
    expect(screen.getByText('第一条计划')).toBeInTheDocument()
    expect(screen.getByText('第二条计划')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('补充说明')).toBeInTheDocument()
  })

  it('未提供 note 时不渲染补充说明', () => {
    render(<RoadmapCard phase="P3" title="标题" description="描述" items={['唯一计划']} />)

    expect(screen.getByText('唯一计划')).toBeInTheDocument()
    expect(screen.queryByText('补充说明')).not.toBeInTheDocument()
  })

  it('明确声明该页面尚未实现，不使用假界面', () => {
    render(<RoadmapCard phase="P4" title="标题" description="描述" items={['计划']} />)

    expect(screen.getByText(/尚未实现/)).toBeInTheDocument()
  })
})