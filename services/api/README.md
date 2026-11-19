# Pokémon Lab · 后端（services/api）

FastAPI + Pydantic + SQLAlchemy(async) + SQLite。仅实现产品 API：图鉴检索、属性克制计算、
个人收藏与笔记、大师考试。对战模拟与强化学习**不在**本服务内。

## 运行

```bash
cd services/api

uv sync                                  # 安装依赖（含开发依赖）
uv run uvicorn app.main:app --reload --port 18000   # 启动开发服务，http://127.0.0.1:18000
```

- 接口文档：<http://127.0.0.1:18000/docs>
- 健康检查：<http://127.0.0.1:18000/api/v1/health>

## 测试与静态检查

```bash
cd services/api
uv run pytest          # 单元测试
uv run ruff check .    # 静态检查
uv run ruff format .   # 格式化（可选）
```

## 数据脚本（P1 起）

```bash
cd services/api

# 生成/更新仓库根 data/type-chart.json（从 PokéAPI 反推，并校验共享测试向量）
uv run python scripts/gen_type_chart.py
# 只校验本地数据与上游一致，不写入（CI 用）
uv run python scripts/gen_type_chart.py --check

# 世代与规则版本种子（幂等）
uv run python scripts/seed_generations.py

# 图鉴同步（P2）：预拉取到本地 SQLite，站点离线可用
uv run python scripts/sync_pokeapi.py              # #1-151（默认关都范围）
uv run python scripts/sync_pokeapi.py --range 1-25 # 指定区间
uv run python scripts/sync_pokeapi.py --force      # 覆盖手动编辑过的记录
```

- 克制表与测试向量入库：`data/type-chart.json`、`data/type-chart.cases.json`。
  后端 pytest 与前端 Vitest 读**同一份**向量，保证两端计算一致。
- 克制接口：`GET /api/v1/types`（完整克制表）、`POST /api/v1/types/evaluate`（倍率计算）、
  `POST /api/v1/types/reverse`（谁克我）。
- 图鉴公开接口（只读）：`GET /api/v1/pokemon`（分页/搜索/筛选）、`GET /api/v1/pokemon/{dex}`。
  `battle_class` 参数按对战分类筛选（`normal` / `pseudo_legendary` / `restricted` /
  `sub_legendary` / `mythical` / `paradox`），响应同时带各分类计数。
- 建队接口：`GET/POST /api/v1/teams`、`PUT/DELETE /api/v1/teams/{id}`、
  `GET /api/v1/teams/{id}/showdown`（导出）、`PUT /api/v1/teams/order`（保存拖拽顺序）、
  `POST /api/v1/teams/import`（导入）、
  `POST /api/v1/teams/batch`（批量改闪光 / 等级 / 性别）—— 后两者都不落库；
  `POST /api/v1/teams/analyze`（队伍评价，草稿不落库）、
  `POST /api/v1/teams/{id}/analyze`（评价并保存到队伍；`?use_llm=false` 只算数据）。
  以上两个各有一个 `/stream` 变体（SSE 流式，先推计算结果再逐段推 AI 正文）——
  模型是推理模型，一次回答要 10–50 秒，流式才不会撞上前端 10 秒超时；
  `GET /api/v1/pokemon/{dex}/team-options`。
- 历史使用率（Smogon）：`GET /api/v1/usage`（月份 / 格式 / 等级线查询）、
  `POST /api/v1/usage/sync`（后台增量同步）、`GET /api/v1/usage/sync/{id}`（进度）、
  `GET /api/v1/usage/sync/latest`、`POST /api/v1/usage/sync/{id}/cancel`。
- 官方赛事（Limitless VGC）：`GET /api/v1/tournaments`（规则 / 类型 / 年份 / 搜索）、
  `GET /api/v1/tournaments/{id}`（名次 + 队表 + 赛事使用率）、
  `GET /api/v1/tournaments/{id}/teams/{team_id}`（一键建队草稿，不落库）、
  `POST /api/v1/tournaments/sync`（后台增量同步）、`GET /api/v1/tournaments/sync/{id}`、
  `GET /api/v1/tournaments/sync/latest`、`POST /api/v1/tournaments/sync/{id}/cancel`。
- 形态招式：`scripts/sync_form_moves.py`（回填 `pokemon_form_move`；队伍校验按编号
  合并形态专属招式 / 特性，如连击流的水流连打、蕾冠王的人马一体）。
- 出卷接口：`POST /api/v1/quiz`（按世代 / 编号区间出卷，随机或全量）、
  `GET /api/v1/quiz/{id}`、`POST /api/v1/quiz/{id}/answer`（中英文名判分）、
  `GET /api/v1/quiz/mistakes`、`DELETE /api/v1/quiz/mistakes[/{dex}]`。
- 管理接口（写操作，本地使用无认证）：`POST /api/v1/admin/pokemon/sync`、
  `GET /api/v1/admin/pokemon/sync/status`、`PUT /api/v1/admin/pokemon/{dex}`、
  `POST /api/v1/admin/pokemon`、`GET /api/v1/admin/ops`。

## 目录职责

| 目录 | 职责 | 硬性约束 |
| --- | --- | --- |
| `app/api/` | 路由、依赖注入 | 只做参数校验与响应组装，不写业务规则 |
| `app/services/` | 编排：串起领域逻辑、仓储与外部客户端 | 事务边界在这一层 |
| `app/domain/` | 属性倍率、组卷、评分等规则计算 | **纯函数、无 IO、不用随机与当前时间** |
| `app/repositories/` | SQL / ORM 读写（P1 起） | 不含业务判断 |
| `app/clients/` | PokéAPI 等外部接口（P1 起） | 负责超时、重试、缓存、降级 |
| `app/schemas/` | Pydantic 请求 / 响应模型 | 对外契约 |
| `app/db/` | 引擎、会话、ORM 模型 | 其他层不直接创建连接 |
| `app/core/` | 配置与日志 | 配置只有这一处来源 |

## 配置

所有参数集中在 `app/core/config.py`，可用 `POKEMON_LAB_*` 环境变量覆盖，
或写入 `services/api/.env`（不入库）。可参考 `.env.example`。

## 数据

- SQLite 文件与 PokéAPI 缓存落在 `services/api/var/`（已忽略，不入库）。
- 跨前后端共享的规范数据（属性克制表等）在仓库根 `data/`。
- 属性克制数据在 **P1** 生成；在那之前 `/health` 的 `datasets` 检查项会如实显示为 `degraded`。

> AI生成
