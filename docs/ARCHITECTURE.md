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

图鉴列表的排序同样遵循「后端出结论」：`GET /pokemon?sort=…` 把 `ORDER BY` 放在
筛选之后的同一条 SQL 里（`WHERE` → `ORDER BY` → `LIMIT/OFFSET`），前端只维护排序
偏好并展示表头箭头，不在客户端对当前页重排 —— 否则跨页排序会错乱。

## 3. 数据模型（世代与规则版本）

```
generations(id, label, region, released_at)
rulesets(id, label, generation_id, notes)        # 如 gen9-standard
pokemon_form(name, dex_number, suffix, zh, name_en_label, types_json, stats_json,
             abilities_json, height_dm, weight_hg, artwork_path, artwork_url,
             sprite_path, sprite_url, position)
                                                 # P2+；同一图鉴编号下机制不同的其它形态
                                                 # 只收录属性/种族值/特性/体重有差异的；纯外观形态不建行
pokemon(dex_number, name_en/zh/ja, types_json, stats_json, abilities_json,
        evolution_json, moves_json, genus_zh/en, flavor_zh/en,
        flavor_zh_source, genus_zh_source,   # pokeapi 官方 / project 项目自译
        artwork_path, artwork_url, sprite_url, sprite_path, is_legendary/mythical/baby,
        gender_rate, capture_rate, base_happiness, hatch_counter,
        growth_rate, habitat, color, shape, egg_groups_json,
        source, synced_at, is_demo)                   # P2；source=pokeapi|manual
api_cache(cache_key, url, payload, etag, expires_at)  # PokéAPI 落盘缓存（P1）
admin_op_log(action, target, detail, operator)   # P2；后台写操作审计
ability(name, zh, effect_zh, effect_en, tier, rating_note, rating_source)  # P2+；特性参考表
item_ref(name, zh, name_en, category, effect_en, cost, icon_path, icon_url)
                                                 # P2+；道具参考表（双打统计里出现的约 257 个）
                                                 # 图标缓存在 media/items/{slug}.png，随同步脚本下载
move_ref(name, zh, name_en, type, damage_class, power, accuracy, pp, description_zh,
         is_machine, learner_count)              # P2+；招式数值参考数据（797 行，跨宝可梦共享）
                                                 # pokemon.moves_json 只存版本组 × 学习方式 → 招式名/等级
move_learner(move_name, dex_number, version_groups_json, methods_key)
                                                 # P2+；从 moves_json 展开的派生索引（约 7.9 万行）
                                                 # 可整表重建，不是手工数据
doubles_format(key, label, short_label, game, ruleset, smogon_format, month, cutoff,
               points_kind, battles, trade_prefix, default_level, note, source_url)
                                                 # P2+；双打统计格式快照（含导出参数）
doubles_pokemon_stat(format_key, showdown_name, dex_number, rank, usage,
               abilities_json, items_json, moves_json, spreads_json,
               teammates_json, tera_types_json)          # P2+；每个格式 × 形态的配装统计
team(id, owner_key, name, format_key, note, analysis_json, analysis_at,
     analysis_members_hash, created_at, updated_at)
                                                 # P3；双打队伍。owner_key 为历史遗留列，
                                                 # 个人自用已不做隔离（不再参与过滤）
team_member(team_id, position, dex_number, showdown_name, nickname, item,
            ability, nature, evs_json, ivs_json, moves_json, tera_type,
            gender, shiny, level)                # P3；槽位 0–5，配置以 JSON 整存
                                                 # 合法性（编号/道具唯一、招式特性可用）在
                                                 # domain/team_rules.py 校验，不写进表约束
schema_meta(key, value)                          # 结构版本记录（已有）
```

核心原则：
- **参考数据**（世代、规则、克制表、题库）只有一份规范来源，即 `data/` + 种子脚本。
- **用户数据**为单实例共享（个人自用，不做隔离）；`team.owner_key` 是历史遗留列，
  将来接账号体系时可直接改造成账号 id，改动集中在 `app/api/deps.py`。
- **错题本不建表**：由 `exam_answers.is_correct=0` 派生，避免两处数据漂移。

## 3.5 编辑/浏览分离（P2 起）

- 公开站点（`/`、`/dex`…）**只读**：只调用 `GET /api/v1/pokemon` 等查询接口，前端
  代码不 import 任何 admin 模块 —— 边界在目录结构上可见。
- 一切写操作集中在 `/admin`（前端）与 `/api/v1/admin/*`（后端）：手动同步触发、
  字段编辑、手动新增，全部写 `admin_op_log`。
- 同步与编辑共存规则：`pokemon.source=manual` 的记录默认不被同步覆盖（管理端可显式
  force）—— 人工修正优先于上游数据。
- **MVP 安全边界（如实声明）**：admin 接口无认证，仅适用于本地个人部署。若暴露公网，
  必须先在网关层加认证；这是「本地优先」项目边界的明确决定，不假装有安全。

## 6.5 双打对战辅助：统计快照的三层数据流

```
Smogon 月度统计文本
   ↓ scripts/fetch_doubles_stats.py（纯解析在 domain/smogon_stats.py）
data/doubles/*.json（仓库内，带格式 / 月份 / cutoff 元数据）
   ↓ services/doubles_service.py:import_datasets（名称映射到全国图鉴）
SQLite doubles_format / doubles_pokemon_stat
   ↓ GET /pokemon/{dex}/doubles          → 详情页 features/doubles/DoublesCard
   ↓ GET /usage-ranking?format=…         → 排行榜页 pages/UsageRankingPage
```

边界与约定：
- **domain 不联网**：`smogon_stats.py` 只解析文本、推断 IV；抓取脚本负责 HTTP 与写文件。
- **公开路由只读**：导入走 `/api/v1/admin/doubles/sync`（读仓库文件，不访问网络）；页面
  不提供「立即抓取」，避免浏览时意外打上游。
- **快照必须可追溯**：`month` / `cutoff` / `source_url` 随每条响应返回，页面显著展示；
  数据文件与库都不混用不同月份。
- **形态与物种**：统计以 Showdown 显示名为主键，`dex_number` 是映射结果；同一编号在
  一个格式下可有多个形态（如 `Charizard-Mega-Y` 与 `Charizard`），按使用率降序返回。
- **IV 是推断**：Smogon 不统计 IV，`infer_ivs()` 的规则是纯函数且有测试，响应带
  `inferred=true`，界面必须标注「推断 · 非数据源字段」。
- **Showdown 导出**：`features/doubles/showdown.ts` 是纯函数（默认草稿 → 文本），
  交易前缀与默认等级来自格式定义（`domain/doubles_formats.py`）。
  英文名来自 `data/doubles/labels.json` 的 `*_en`（Showdown 公开客户端数据），
  中文名只用于页面展示。导出格式遵循 Showdown `Teams.exportSet`：
  IV 全 31 时不输出 IV 行、EV 为 0 的项省略。
- **排行榜与详情共用一张表**：`/usage-ranking` 只做「左连接图鉴 → 按 rank 排序 →
  分页 → 组装摘要」，名次直接来自统计数据，不在前端重算。四个格式的标签始终返回
  （未导入的 `entries=0`），让「没有数据」与「请求失败」在界面上可区分。
- **道具与统计弱关联**：统计数据只存道具 slug，展示时按 slug 批量查 `item_ref`
  （`item_icon_lookup`），图标地址本地优先、缺失为 null；未同步的道具显示占位，
  不拼可能 404 的远程地址。
- **形态是独立维度，不是第二条宝可梦**：`pokemon` 一个编号一行，机制上有差异的其它形态
  放 `pokemon_form`（`services/form_service.py`）。详情页只返回菜单摘要，切换时按需请求
  `/pokemon/{dex}/forms/{slug}`；默认形态直接用详情数据，不额外发请求。
- **招式的数值与学习记录分离**：`move_ref`（数值）来自 `/move/{slug}`，`move_learner`
  来自 `pokemon.moves_json`（学习记录）。上游宝可梦招式表漏招时，用
  `scripts/backfill_move_refs.py` 只补数值，不伪造学习记录 —— 属性徽章能显示，
  但「谁会这招」仍只反映真实数据。

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
5. 离线：`scripts/sync_pokeapi.py` 手动预拉取（全国图鉴 #1–1025，建议按世代分批
   `--gen N`，中断后用 `--resume` 续传），站点脱网可用。
   官方立绘同时下载到 `var/media/artwork`，由 `/media` 静态托管；图片下载失败不阻塞数据落库。
6. 并发：SQLite 开启 WAL + busy_timeout；批量同步逐条提交，避免长时间占用写锁导致
   浏览请求拿到 `database is locked`。
7. 结构演进：`init_db()` 在建表后用 `ALTER TABLE ... ADD COLUMN` 幂等补齐 P2 新增列，
   本地旧库无需手工迁移；正式迁移工具引入后由其接管。
6. 前端四种状态：加载中 / 空结果 / 失败重试 / 数据可能过期，统一封装。

## 9. 测试策略

- 后端：domain 纯函数测试；clients 用 respx 模拟 httpx；接口测试用 httpx ASGITransport + 临时 SQLite。
- 前端：engine/session 纯函数测试；apiClient 用 stub fetch；组件测试 RTL。
- 交叉一致性：属性/倍率用例由 `data/type-chart.cases.json` 同一份向量覆盖两端。

## 10. 已记录的技术决策（ADR 摘要）

| 决策 | 理由 |
| --- | --- |
| 属性表只存在 `data/`，不复制进两端代码 | 单一真相来源 |
| 不做登录 / 不做浏览器隔离（个人自用） | 单实例复杂度最低；隔离会让「换浏览器就看不到队伍」 |
| SQLAlchemy async + aiosqlite | 与既有工程习惯一致，支持后续迁移 |
| 克制计算前端本地做 + 后端可校验 | 离线可用、即时反馈 |
| 用 uv 管 Python、npm 管前端 | 各自生态的标准工具 |

## 11. 已知环境注意（本机）

`localhost:5173` 可能与既有 Vite 服务（IPv6 `::1`）并存：本项目绑定 `127.0.0.1:5173`（IPv4），
浏览器若解析到 IPv6 会看到其他服务，访问时请用 `127.0.0.1:5173`。

> AI生成
