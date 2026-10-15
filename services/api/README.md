# Pokémon Lab · 后端（services/api）

FastAPI + Pydantic + SQLAlchemy(async) + SQLite。仅实现产品 API：图鉴检索、属性克制计算、
个人收藏与笔记、大师考试。对战模拟与强化学习**不在**本服务内。

## 运行

```bash
cd services/api

uv sync                                  # 安装依赖（含开发依赖）
uv run uvicorn app.main:app --reload     # 启动开发服务，默认 http://127.0.0.1:8000
```

- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

## 测试与静态检查

```bash
cd services/api
uv run pytest          # 单元测试
uv run ruff check .    # 静态检查
uv run ruff format .   # 格式化（可选）
```

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
