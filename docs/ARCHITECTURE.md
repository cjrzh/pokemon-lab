# ARCHITECTURE.md

## 1. 系统形态

```
浏览器（桌面/手机）
   │  http://127.0.0.1:5173（Vite dev，/api 同源代理）
   ▼
apps/web  React 19 + TS + Tailwind v4 + shadcn/ui + TanStack Query
   │        features/ 按领域切分；页面只做装配
   ▼
services/api  FastAPI + Pydantic v2 + SQLAlchemy(async) + SQLite
   │        api/ → services/ → domain/（纯函数）
   ▼
data/（仓库内规范数据，跨端共享唯一真相来源）
   + PokéAPI（外部公开接口，经 clients/ 代理 + SQLite 缓存）
```

未来扩展的 `battle/`（Showdown 适配器）与 `rl/`（训练）不在本仓库现有目录，不提前建。

## 2. 分层职责与依赖方向

| 层 | 职责 | 禁止 |
| --- | --- | --- |
| `app/api/v1/` | 参数校验、依赖注入、响应组装 | 写业务规则 |
| `app/services/` | 编排领域逻辑、仓储、外部客户端；事务边界 | 直接拼 SQL 细节 |
| `app/domain/` | 属性倍率、组卷、评分等**纯函数** | IO、随机、时间、框架依赖 |
| `app/db/` | 引擎、会话、ORM 模型 | 其他层自行创建连接 |
| `app/core/` | 配置（单例）、日志 | 配置散落各处 |
| `app/clients/`（P1） | PokéAPI 超时/重试/缓存/降级 | 泄漏到路由层 |

前端对应约束：`pages/` 只装配；`features/*/engine.ts`、`features/*/session.ts` 为纯函数；
数据请求统一走 `lib/apiClient`（超时、错误分类、身份头）+ TanStack Query（缓存、重试、状态）。

## 3. 数据模型（世代与规则版本）

```
generations(id, label, region, released_at)
rulesets(id, label, generation_id, notes)        # 如 gen9-standard
pokemon(…, generation_introduced, types_json, …) # P2
api_cache(cache_key, url, payload, etag, expires_at)  # PokéAPI 落盘缓存（P1）
collections / notes / exam_sessions / exam_answers / questions  # P4–P5，均带 owner_key
schema_meta(key, value)                          # 结构版本记录（已有）
```

核心原则：
- **参考数据**（世代、规则、克制表、题库）只有一份规范来源，即 `data/` + 种子脚本。
- **用户数据**带 `owner_key` 与可选的 `ruleset_id`，未来接账号体系只改一处。
- **错题本不建表**：由 `exam_answers.is_correct=0` 派生，避免两处数据漂移。

## 7. 属性克制表：一份数据、两端共用

- `data/type-chart.json`：规范克制表（P1 由脚本从 PokéAPI `/type/*` 的 damage_relations 反推生成，带 source 标注）。
- `data/type-chart.cases.json`：测试向量；pytest 与 Vitest **读取同一文件**，保证两端结果一致。
- 前端通过 Vite alias 直接 import，克制计算**离线即时**；后端暴露 `/types/evaluate` 供校验。
- 版本策略：MVP 只实现 **Gen 6+**（第 6 代起规则一致），`generation` 维度预留在数据结构中；
  Gen 1–5 差异（如钢系抗性、虫系反克）由后续版本逐代补齐，补齐前界面明确标注，绝不虚报。

## 8. 外部 API 策略（PokéAPI）

1. 超时：connect 5s / read 10s（可配置）。
2. 重试：最多 2 次指数退避，仅对可恢复错误。
3. 缓存：SQLite `api_cache`，TTL 7 天；命中缓存返回 `X-Cache: hit`。
4. 降级：上游失败且本地有旧缓存 → 返回旧数据并标 `X-Cache: stale`；无缓存 → 503 + 可读 detail。
5. 离线：`scripts/sync_pokeapi.py` 手动预拉取（建议 #1–151），站点脱网可用。
6. 前端四种状态：加载中 / 空结果 / 失败重试 / 数据可能过期，统一封装。

## 9. 测试策略

- 后端：domain 纯函数测试；clients 用 respx 模拟 httpx；接口测试用 httpx ASGITransport + 临时 SQLite。
- 前端：engine/session 纯函数测试；apiClient 用 stub fetch；组件测试 RTL。
- 交叉一致性：属性/倍率用例由 `data/type-chart.cases.json` 同一份向量覆盖两端。

## 10. 已记录的技术决策（ADR 摘要）

| 决策 | 理由 |
| --- | --- |
| 属性表只存在 `data/`，不复制进两端代码 | 单一真相来源 |
| 匿名 owner_key 而非登录 | MVP 复杂度可控，接口单一替换点 |
| SQLAlchemy async + aiosqlite | 与既有工程习惯一致，支持后续迁移 |
| 克制计算前端本地做 + 后端可校验 | 离线可用、即时反馈 |
| 用 uv 管 Python、npm 管前端 | 各自生态的标准工具 |

## 11. 已知环境注意（本机）

`localhost:5173` 可能与既有 Vite 服务（IPv6 `::1`）并存：本项目绑定 `127.0.0.1:5173`（IPv4），
浏览器若解析到 IPv6 会看到其他服务，访问时请用 `127.0.0.1:5173`。

> AI生成
