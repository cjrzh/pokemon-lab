import {
  Backpack,
  BookOpen,
  Boxes,
  Database,
  Calculator,
  House,
  NotebookPen,
  Sparkles,
  Swords,
  Trophy,
  Medal,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  description: string
  icon: LucideIcon
  /**
   * 是否已交付。未交付的入口在导航与首页如实标注「规划中」，
   * 而不是给出一个看起来可用的假入口。
   */
  delivered: boolean
}

export const NAV_ITEMS: readonly NavItem[] = [
  {
    to: '/',
    label: '研究所',
    description: '项目总览与运行状态',
    icon: House,
    delivered: true,
  },
  {
    to: '/dex',
    label: '图鉴',
    description: '检索宝可梦并查看属性、种族值、形态与进化信息',
    icon: BookOpen,
    delivered: true,
  },
  {
    to: '/abilities',
    label: '特性',
    description: '特性说明、S 级评级与拥有者',
    icon: Sparkles,
    delivered: true,
  },
  {
    to: '/moves',
    label: '招式',
    description: '招式数值、说明与「谁会这招」',
    icon: Swords,
    delivered: true,
  },
  {
    to: '/items',
    label: '道具',
    description: '携带道具的说明、分类与图标',
    icon: Backpack,
    delivered: true,
  },
  {
    to: '/usage',
    label: '使用率',
    description: 'BDSP / 剑盾 / 朱紫 / 冠军双打使用率排行',
    icon: Trophy,
    delivered: true,
  },
  {
    to: '/teams',
    label: '建队',
    description: '双打队伍编辑与 Showdown 导出',
    icon: Boxes,
    delivered: true,
  },
  {
    to: '/quiz',
    label: '出卷',
    description: '看图识宝可梦：按世代 / 编号范围出题，自动评分与错题集',
    icon: NotebookPen,
    delivered: true,
  },
  {
    to: '/usage/history',
    label: '历史使用率',
    description: 'Smogon 任意月份 / 规则 / 等级线的双打使用率，支持增量同步',
    icon: Database,
    delivered: true,
  },
  {
    to: '/tournaments',
    label: '官方赛事',
    description: 'VGC 地区赛 / 国际赛 / 世锦赛的成绩、队表与赛事使用率',
    icon: Medal,
    delivered: true,
  },
  {
    to: '/type-calc',
    label: '属性克制',
    description: '属性倍率计算与「谁克我」反向查询',
    icon: Calculator,
    delivered: true,
  },
]
