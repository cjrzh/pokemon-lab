# Pokémon Lab · 前端（apps/web）

React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui + TanStack Query + React Router。

## 常用命令

```bash
npm install        # 安装依赖
npm run dev        # 启动开发服务器（127.0.0.1:5173，/api 代理到 http://127.0.0.1:8000）
npm run build      # tsc -b && vite build 生产构建
npm run preview    # 预览生产构建
npm run test       # Vitest 单元测试
npm run test:watch # 测试监听模式
npm run typecheck  # TypeScript 类型检查
npm run lint       # oxlint
```

## 结构约定

```
src/
├── app/            # 应用装配：providers / router / layout / theme / queryClient
├── pages/          # 路由级页面：只做装配，不写业务逻辑
├── features/       # 领域切分（dex / type-matchup / collection / exam / health）
│                   #   engine.ts / session.ts = 纯函数，必须可单测
├── components/
│   ├── ui/         # shadcn/ui 生成物（不手改结构）
│   └── common/     # 项目通用组件
├── lib/            # apiClient（超时/错误分类/身份头）、ownerKey（匿名身份）、utils
├── styles/tokens.css  # 设计令牌：18 属性色、语义状态色
└── test/setup.ts   # Vitest 环境配置
```

## 设计系统

- 令牌集中在 `src/styles/tokens.css`，Tailwind 由此生成 `bg-type-fire` 等工具类。
- 属性配色采用社区通用配色表（配色参考，非官方素材），前景色按对比度择取。
- 深色模式：class 策略（`html.dark`），跟随系统 + 手动切换，预加载脚本防闪烁。
- 响应式：桌面侧边栏 / 移动端顶部栏 + 底部标签栏，同一套代码。

> AI生成
