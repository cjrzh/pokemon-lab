# Pokémon Lab · 宝可梦研究所

个人兴趣项目：**图鉴与搜索 · 属性克制计算器 · 个人收藏与笔记 · 大师考试**，
并预留 LLM 战术教练、Showdown 自动对战、强化学习与安卓端扩展。

> 当前进度：**P0 骨架完成**（前后端可运行、可测试、可连通）。属性克制、图鉴、收藏、考试等功能
> 在 P1–P5 逐步交付；未实现的页面会明确标注计划阶段，不使用演示数据冒充已完成功能。

## 技术栈

| 端 | 技术 |
| --- | --- |
| 前端 `apps/web` | React 19 · TypeScript · Vite · Tailwind CSS v4 · shadcn/ui · TanStack Query · React Router · Vitest |
| 后端 `services/api` | Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy(async) · SQLite · httpx · pytest · ruff · **uv** 管理环境 |
| 数据 | 仓库内规范数据（`data/`）+ PokéAPI（外部公开接口）+ 本地 SQLite 缓存 |

## 快速开始

### 1. 后端

```bash
cd services/api
uv sync                          # 创建虚拟环境并安装依赖
uv run uvicorn app.main:app --reload --port 18000
```

- 接口文档：<http://127.0.0.1:18000/docs>
- 健康检查：<http://127.0.0.1:18000/api/v1/health>

### 2. 前端

```bash
cd apps/web
npm install
npm run dev
```

浏览器打开 <http://127.0.0.1:5173>。

> **本机环境注意**：如果 `localhost:5173` 被其他 Vite 服务（如 ScholarHub）占用，
> 本项目显式绑定 `127.0.0.1:5173`，请使用该地址访问，避免浏览器解析到 IPv6 上的其他服务。

### 3. 测试与检查

```bash
# 后端（services/api 下）
uv run pytest            # 单元测试（当前 10 个）
uv run ruff check .      # 静态检查

# 前端（apps/web 下）
npm test                 # Vitest（当前 21 个）
npm run typecheck        # tsc 类型检查
npm run build            # 生产构建
npm run lint             # oxlint
```

## 目录结构

```
pokemon-lab/
├── apps/web/            # React + TS 前端（features 按领域切分，页面不写业务逻辑）
├── services/api/        # FastAPI 后端（api / services / domain 分层）
├── data/                # 跨前后端共享的规范数据（属性克制表等，P1 生成）
├── docs/                # PRD / ARCHITECTURE / ROADMAP / DATA_SOURCES
├── plan.md              # 早期规划稿（保留）
└── .gitignore / .gitattributes / .editorconfig
```

架构约束详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，数据来源与版权说明见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。

## 数据与版权声明（摘要）

- 图鉴数据来自 **PokéAPI**（公开接口），同步到本地 SQLite 后离线可用；同步脚本手动触发。
- 属性克制关系为官方 Gen 6+ 规则，整理为仓库内规范数据（P1 生成），前后端共享同一份来源。
- 所有演示数据带显式标记；**不虚构数据来源**。
- 宝可梦相关名称、形象与商标归 任天堂 / GAME FREAK / Creatures Inc. 所有；本项目为非商业个人学习用途。
- 完整说明见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。

## 阶段状态

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| P0 | monorepo 骨架、前端设计系统、后端 /health、文档、Git | ✅ 完成 |
| P1 | 世代/规则种子、属性克制数据与引擎、PokéAPI 客户端 | ⏳ 下一个 |
| P2 | 图鉴与搜索 | 未开始 |
| P3 | 属性克制计算器 UI | 未开始 |
| P4 | 收藏与笔记 | 未开始 |
| P5 | 大师考试 v0 | 未开始 |
| P6 | 验收、响应式走查、留档 | 未开始 |

每个阶段完成后会在会话中输出：修改文件清单 / 运行方法 / 测试结果 / 已知问题。

> AI生成
