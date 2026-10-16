import {
  BookOpen,
  Calculator,
  FileText,
  GraduationCap,
  House,
  Star,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  description: string
  icon: LucideIcon
  /** 计划交付阶段。用于在界面上如实标注「还没做」，而不是给出假的可用入口。 */
  phase: string
}

export const NAV_ITEMS: readonly NavItem[] = [
  {
    to: '/',
    label: '研究所',
    description: '项目总览与运行状态',
    icon: House,
    phase: 'P0',
  },
  {
    to: '/dex',
    label: '图鉴',
    description: '检索宝可梦并查看属性、种族值与进化信息',
    icon: BookOpen,
    phase: 'P0',
  },
  {
    to: '/type-calc',
    label: '属性克制',
    description: '属性倍率计算与「谁克我」反向查询',
    icon: Calculator,
    phase: 'P3',
  },
  {
    to: '/collection',
    label: '收藏',
    description: '收藏宝可梦并记录个人备注',
    icon: Star,
    phase: 'P4',
  },
  {
    to: '/notes',
    label: '笔记',
    description: '研究所笔记、标签与规则版本关联',
    icon: FileText,
    phase: 'P4',
  },
  {
    to: '/exam',
    label: '大师考试',
    description: '规则组卷、答题评分与错题本',
    icon: GraduationCap,
    phase: 'P5',
  },
]