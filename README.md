# Pokémon Lab · 宝可梦研究所

个人兴趣项目：**全国图鉴 · 特性 · 招式 · 道具 · 属性克制计算器 · 双打使用率**，
本地优先、离线可用。

> 当前进度：**全国图鉴（Gen 1–9，#1–1025）已完成同步**：官方立绘、分类与图鉴描述、
> 特性说明、进化条件、**全招式表**（升级 / 学习器 / 蛋招式 / 教学，覆盖 26 个版本组，表头可排序）；
> 官方中文缺失的 303 条描述由项目自译补齐并在界面标注来源；
> 特性页收录 284 个特性（77 个 S 级为 LLM 预评，可在页面人工修改），图鉴中 S 级特性标红加粗；
> 新增**招式页**（797 个招式的数值、说明与「谁会这招」），与图鉴、特性并列；
> 招式表与宝可梦详情双向链接。
> 图鉴首页支持卡片 / 列表切换、卡片缩放、列表分页条数（25–200）与**排序**
> （编号升 / 降序、种族值合计升 / 降序，在属性 / 世代 / 搜索筛选后的子列表内排序）。
> 新增**使用率排行页**（`/usage`）：BDSP / 剑盾 / 朱紫 / 冠军四个双打格式的榜单，
> 含名次、出场率、属性、前四项招式与前三个特性 / 道具、主流配点，可搜索与分页，
> 并链接到图鉴详情。
> 新增**小图标**：全部 1025 只的 96×96 sprite 缓存到本地，图鉴列表、使用率排行与
> 特性页的「拥有者」都显示小图标。断网时同样可加载。
> 新增**道具参考表与图标**：双打统计里出现的 257 个道具从 PokéAPI 同步中文名、
> 分类与说明，30×30 图标缓存到本地，双打辅助与使用率排行的道具条目都显示图标；
> 另有独立的**道具页**（`/items`），支持搜索、按分类筛选与分页。
> 详情页新增**双打对战辅助**：冠军 / 朱紫 / 剑盾 / BDSP 四个格式的 Smogon 使用率统计，
> 含推荐性格 / 配点 / 特性 / 道具 / 招式、出场率、常见队友与**可编辑的 Showdown 导出代码**
> （BDSP / 剑盾 / 朱紫自动加 `!tradeBDSP` / `!tradeSWSH` / `!tradeSV` 交换前缀）；
> 后台管理可同步与编辑（支持按世代分批、断点续传，带分世代覆盖看板）。
> 图鉴详情页顶部常驻**宝可梦搜索栏**：中文名 / 英文名 / 编号即时搜索，下拉结果带小图标与属性，
> 点击或回车即可切换，无需先返回列表。
> 详情页支持**形态切换**：同一图鉴编号下机制上不同的形态（如武道熊师「一击流 / 连击流」、
> 洛托姆六种家电、固拉多原始回归）以可点击菜单呈现，切换后属性、种族值、特性、立绘随之更新；
> 纯外观形态（超极巨化、霸主、骑乘姿态）不收录。
> 属性克制计算器已上线：倍率计算、反向查询「谁克我」与 18 属性进攻速查，
> 计算在浏览器本地完成（克制表随包加载）。
> 新增**双打建队**：每队 6 只、编号与道具不可重复、招式 / 特性按版本校验；
> 按中文名 / 英文名 / 编号搜索加入（前缀匹配，输入「喷火」即可）；
> 加入后自动填好该格式的使用率推荐（特性 / 道具 / 招式 / 配点），可逐项改；
> 特性与道具是带使用率的下拉框、招式可点进详情页；
> 队伍可命名保存，并导出成带交易前缀的 Showdown 代码（独立页面）；
> 也能把 Showdown 代码**粘贴导入**回来（单只或整队、可多次导入拼队），
> 解析后追加进编辑器确认再保存；招式合法性包含**进化链前代**继承的招式
> （如雷丘的 Fake Out 来自皮丘）。
> 支持**批量设置**闪光 / 等级 / 性别（尼多朗这类只能单性别的会自动跳过并说明）、
> 每只可选导出语言；队伍不限数量，可按游戏版本筛选。
> 队伍可一键**生成评价**：打击面 / 缺失面 / 共同弱点按属性算出（可复现），
> 改进建议与玩法推荐由 LLM **流式生成**（边生成边显示，思考阶段有提示；
> 未配置 LLM 时只少了这两段，不影响计算）；
> 评价存到队伍上，下次打开直接显示，可随时**更新**（队伍改过会提示「评价已过期」）。

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

> **本机常驻运行**：本开发机已把后端注册为 systemd 服务 `pokemon-lab-api`
> （`systemctl status pokemon-lab-api`）。它监听 `127.0.0.1:18000`，崩溃或被杀后
> 3 秒自动拉起，避免前端 Vite 代理出现 502。改了代码需要重启时用
> `sudo systemctl restart pokemon-lab-api`；想看日志用 `journalctl -u pokemon-lab-api -f`。
> 上面的 `uv run uvicorn --reload` 仅用于临时调试（会与原服务抢同一个端口，先停服务）。

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
uv run pytest            # 单元测试（当前 222 个）
uv run ruff check .      # 静态检查

# 前端（apps/web 下）
npm test                 # Vitest（当前 211 个）
npm run typecheck        # tsc 类型检查
npm run build            # 生产构建
npm run lint             # oxlint
```

### 4. 图鉴数据同步

> 仓库自带 `services/api/var/media/` 下的图鉴图片（1025 张立绘 + 1025 张小图标 +
> 256 张道具图标 + 约 490 张形态图片，均为公开图鉴素材，来源见 `docs/DATA_SOURCES.md`），
> clone 后图片直接可用。
> SQLite 数据库**不入库**（可由下述脚本重新生成），因此首次运行需同步一次数据。

```bash
cd services/api
uv run python scripts/sync_pokeapi.py            # 同步全国图鉴 #1-1025
uv run python scripts/sync_pokeapi.py --gen 2-3   # 按世代同步（城都 + 丰缘）
uv run python scripts/sync_pokeapi.py --gen 4 --resume  # 跳过已同步，断点续传
uv run python scripts/sync_pokeapi.py --range 1-9  # 或在后台 /admin/sync 页面点击触发
```

同步后数据落在本地 SQLite，断网也能浏览图鉴；手动编辑过的条目不会被同步覆盖。
全国图鉴共 **1025 只**（Gen 1–9），首轮全量同步较慢；建议按世代分批：
`--gen 1`、`--gen 2`、…、`--gen 9`，中断后加 `--resume` 继续。
官方立绘（pokemon.com 公开图鉴资源）会下载到 `services/api/var/media/artwork/`，
小图标（PokéAPI sprites，96×96）会下载到 `services/api/var/media/sprites/`，
都由后端 `/media` 静态托管 —— 断网时图片同样可用。

> 首次全量同步需要逐条拉取特性 / 招式详情并下载立绘，约数分钟；之后命中缓存会快很多。
> 同步逐条提交，进行中仍可正常浏览站点。

只补立绘（不重新拉数据）：

```bash
uv run python scripts/sync_pokeapi.py --force-artwork --range 1-151
```

只补小图标（不重新拉数据）：

```bash
uv run python scripts/sync_pokeapi.py --sprites
```

特性参考表（名称、S 级评级）随图鉴同步自动汇总；也可以单独回填：

```bash
uv run python scripts/backfill_abilities.py
```

补录 `move_ref` 缺失的招式（PokéAPI 的宝可梦招式表偶尔漏招，导致双打统计里的招式没有属性）：

```bash
uv run python scripts/backfill_move_refs.py            # 只补双打统计里缺失的招式
uv run python scripts/backfill_move_refs.py --slugs surging-strikes
```

双打对战辅助数据（Smogon 月度统计，四个格式）：

```bash
uv run python scripts/fetch_doubles_stats.py      # 联网抓取 -> 仓库 data/doubles/*.json
uv run python scripts/sync_doubles.py             # 导入 SQLite（后台 /admin/sync 也可触发）
uv run python scripts/sync_doubles.py --fetch     # 抓取 + 导入一步完成
```

道具参考表与图标（双打统计里出现的全部道具）：

```bash
uv run python scripts/sync_items.py               # PokéAPI 拉取中文名/说明 + 下载 30×30 图标
uv run python scripts/sync_items.py --no-icons    # 只拉元数据
```

宝可梦形态（机制上不同的其它样子，约 190 个物种 / 240 个形态）：

```bash
uv run python scripts/sync_forms.py               # 全量同步（并发抓取 + 下载形态图片）
uv run python scripts/sync_forms.py --dex 892     # 只同步指定编号
```

## 页面一览

| 页面 | 路径 | 内容 |
| --- | --- | --- |
| 研究所（首页） | `/` | 能力入口、后端健康状态、数据来源与边界 |
| 图鉴 | `/dex` | 卡片 / 列表、搜索、属性 / 世代 / **对战分类**筛选、排序；详情含形态切换、双打辅助 |
| 特性 | `/abilities` | 特性说明、S 级评级、拥有者（可跳转图鉴） |
| 招式 | `/moves` | 招式数值、说明、「谁会这招」 |
| 道具 | `/items` | 道具中文名、分类、**中文说明**（项目自译 · 可看英文原文）与图标 |
| 使用率 | `/usage` | BDSP / 剑盾 / 朱紫 / 冠军四个双打格式的排行榜 |
| 历史使用率 | `/usage/history` | Smogon 任意月份 / 规则 / 等级线（1500/1630/1760）的双打使用率；页内同步按钮，增量抓取；可只同步当前选中的规则或单个快照 |
| 官方赛事 | `/tournaments` | VGC 官方比赛（地区赛 / 国际赛 / 世锦赛…）列表：规则、人数、冠军、队表数；页内增量同步 |
| 赛事详情 | `/tournaments/:id` | 单场赛事的**选手完整队表**（Showdown 复制 / **一键建队**；代码默认 100 级 / 闪光，超极巨化统一写 `Gigantamax: Yes`）、**赛事使用率**与名次，三个视图分页 |
| 出卷 | `/quiz` | 看图识宝可梦：按世代 / 编号范围出题（随机 N 或全量），中英文名判分，自动评分与错题集 |
| 属性克制 | `/type-calc` | 倍率计算（进攻 × 1–2 防守）、谁克我、进攻速查 |
| 建队 | `/teams` | 双打队伍编辑（6 只、编号/道具不重复、招式特性合法性校验，中文名前缀搜索加入；**多形态宝可梦可选形态**（洛托姆 / 厄诡椪 / 超级进化…），默认取使用率最高的形态；**拖动或上下按钮调整出场顺序，队伍列表也可拖动排序**；新加入的默认闪光 / 100 级 / 雌性；EV 可手动输入并校验，性格标注增减；批量设置闪光/等级/性别，按版本筛选，不限队伍数；每只可一键复制带交易前缀的 Showdown 代码（剑盾含极巨化等级与超极巨化，超极巨化写 `Gigantamax: Yes`）；改动可按内容比对标记，一键恢复上次保存；评价保存到队伍） |
| Showdown 代码 | `/teams/:id/showdown` | 整队导出，含交易前缀，可复制 / 下载 |

所有入口均为可用功能；数据来自 PokéAPI、Smogon 公开统计与 Limitless VGC（官方赛事），页面标注来源。

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
| P1 | 世代/规则种子、属性克制数据与引擎、PokéAPI 客户端 | ✅ 完成 |
| P2 | 图鉴与搜索（含后台管理：同步 + 编辑） | ✅ 完成 |
| P2+ | 特性页、全国图鉴 Gen 2–9、双打对战辅助（冠军 / 朱紫 / 剑盾 / BDSP） | ✅ 完成 |
| P3 | 属性克制计算器 UI（倍率 / 反向 / 进攻速查）+ 双打建队 | ✅ 完成 |
| P4 | 收藏与笔记 | 已移除（不在当前范围内） |
| P5 | 大师考试 | 已移除（不在当前范围内） |
| P6 | 出卷（看图识宝可梦）与错题集 | ✅ 完成 |
| P7 | Smogon 历史使用率（任意月份 / 规则 / 等级线，增量同步） | ✅ 完成 |
| P8 | 官方赛事（Limitless VGC）：成绩、队表、赛事使用率与一键建队 | ✅ 完成 |

每个阶段完成后会在会话中输出：修改文件清单 / 运行方法 / 测试结果 / 已知问题。

> AI生成
