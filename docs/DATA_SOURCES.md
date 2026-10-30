# DATA_SOURCES.md · 数据来源与版权说明

> 原则：**不虚构数据来源**。每条数据都要能说清楚「来自哪里、什么时候拿的、怎么验证」。
> 演示数据一律显式标记，绝不冒充真实数据。

## 1. 属性克制关系（游戏规则数据）

| 项目 | 内容 |
| --- | --- |
| 来源 | 官方宝可梦系列游戏自第 6 代起生效的属性相克关系（Gen 6/7/8/9 一致） |
| 生成方式 | `services/api/scripts/gen_type_chart.py` 从 PokéAPI `/type/{id}` 的 `damage_relations` 反推，生成 `data/type-chart.json`（P1 交付） |
| 版本范围 | MVP 仅实现 Gen 6+；Gen 1–5 的历史差异（如第 1 代虫系反克、第 2–5 代钢系抗性、幽灵/恶对钢）在数据结构中预留，逐步补齐 |
| 属性配色 | `apps/web/src/styles/tokens.css` 采用社区通用配色表（与 Bulbapedia / Pokémon Showdown 客户端一致），属配色参考，非官方美术素材 |

## 2. 图鉴数据（PokéAPI）

- **来源**：<https://pokeapi.co/> —— 公开 REST 接口，无需密钥。
- **覆盖范围**：全国图鉴 **#1–1025（Gen 1–9）**，按 `/pokemon/{id}` 与
  `/pokemon-species/{id}` 的 ID 一一对应（已验证默认形态 ID 与全国图鉴编号一致）。
- **分批同步**：`scripts/sync_pokeapi.py --gen N`（N=1–9）按世代同步；`--resume`
  跳过已同步记录，便于中断后续传。管理页 `/admin/sync` 提供分世代覆盖看板。
- **用途**：宝可梦名称（中/英/日）、属性、种族值、特性、进化链、招式等基础图鉴数据。
- **列表排序**：`GET /pokemon` 支持 `sort=dex`（默认，编号升序）/ `dex_desc` /
  `total_stats` / `total_stats_asc`。种族值合计在 SQL 里用 `json_extract` 对
  `stats_json` 六项求和，`ORDER BY` 发生在属性 / 世代 / 搜索筛选之后 ——
  即「先筛子列表，再在子列表内排序」；没有种族值的记录（`{}`）在升降序中都排在最后。
- **落地方式**：后端 `clients/pokeapi.py`（P1）代理请求并缓存到本地 SQLite；`sync_pokeapi.py` 手动预拉取，站点离线可用。
- **许可注意**：PokéAPI 提供的是整理后的游戏数据，宝可梦**形象与商标版权仍归 任天堂 / GAME FREAK / Creatures Inc.**，本项目为非商业个人学习用途，不使用官方美术素材。

## 2.1 图鉴立绘与图鉴文本

| 项目 | 内容 |
| --- | --- |
| 立绘来源 | <https://assets.pokemon.com/assets/cms2/img/pokedex/full/{编号}.png> —— 官方宝可梦图鉴公开资源，475×475 PNG |
| 落地方式 | 同步时下载到 `services/api/var/media/artwork/{编号}.png`，由后端 `/media` 静态托管；本地优先，缺失时回落到远程地址 |
| 兜底图片 | PokéAPI sprites 仓库的 official-artwork，经 <https://wsrv.nl> 图片代理访问（本机直连 raw.githubusercontent.com 不稳定） |
| 小图标 | PokéAPI sprites 仓库的普通 sprite（`sprites/pokemon/{编号}.png`，96×96，约 1 KB），同样经 wsrv 代理；同步时缓存到 `services/api/var/media/sprites/{编号}.png`，由 `/media` 托管。用于图鉴列表行、使用率排行与特性页「拥有者」；本地缺失时回落到远程小图。可用 `sync_pokeapi.py --sprites` 单独补齐 |
| 图鉴文本 | PokéAPI `pokemon-species` 的 `genera`（分类）与 `flavor_text_entries`（图鉴描述，取最新版本的 zh-hans，缺失回落 zh-hant） |
| 中文缺失情况 | 部分世代（尤其第 9 世代朱／紫条目）上游只有英文图鉴文本，共 **303 只**；分类缺失 15 只 |
| 中文兜底译文 | 上述缺口由 `data/flavor-zh/gen-XX.json` 的**项目自译**补齐（303 条描述 + 15 条分类）。译文由 AI 辅助翻译、项目维护者校对，**不是官方文本**；数据库 `flavor_zh_source` / `genus_zh_source` 记录来源，详情页显示「项目自译」标记 |
| 为何不用 52poke | 神奇宝贝百科含官方简中图鉴文本，但 `robots.txt` 要求 `Crawl-delay: 500`（每请求约 8 分钟），批量抓取不符合站点声明；内容许可为 CC BY-NC-SA 3.0。仅在人工核对时参考，不做自动入库 |

### 中文译文文件格式

```
data/flavor-zh/
├── gen-02.json … gen-09.json   # 按世代分文件，entries: {"152": "……"}
└── genus-zh.json               # 分类译文
```

每个文件带 `source: "project-translation"`、`source_label`、`translated_at`。
上游此后若补上官方中文，同步会**优先使用上游文本**并把来源改回 `pokeapi`，译文自动失效。
新增/修订译文后运行：

```bash
cd services/api
uv run python scripts/backfill_flavor_zh.py   # 只读本地库 + 译文文件，不访问网络
```
| 特性说明 | PokéAPI `/ability/{name}` 的中文名与 zh-hans 图鉴说明；英文 `short_effect` 作为补充 |
| 招式数据 | PokéAPI `/pokemon` 的**全部**版本组与学习方式（升级 / 招式学习器 / 蛋招式 / 教学 / 特殊教学 / 净化 / 活动），共 26 个版本组；数值来自 `/move/{name}` 的中文名、属性、分类、威力/命中/PP 与图鉴说明 |
| 招式存储 | `pokemon.moves_json` 只存「版本组 → 学习方式 → 招式名/等级」；592 个招式的数值单独存 `move_ref` 表，避免在 151 只宝可梦间重复 |
| 进化条件 | PokéAPI `/evolution-chain` 的 `evolution_details`，解析为「等级 16」「使用水之石」「亲密度 ≥ 160 · 白天」等中文描述 |
| 版权注意 | 立绘与名称版权归 任天堂 / GAME FREAK / Creatures Inc. 所有，本项目为非商业个人学习用途；若将来公开分发，需先核对素材使用条件 |

## 2.2 特性数据与 S 级评级

| 项目 | 内容 |
| --- | --- |
| 特性名称与说明 | 从已同步宝可梦的 `abilities_json` 汇总到 `ability` 表（同一特性跨宝可梦共享）；第 9 世代 36 条缺少中文说明的特性，由 `data/flavor-zh/abilities-zh.json` 项目自译兜底 |
| S 级评级 | `data/abilities/s-tier.json`：由 LLM 按当前对战环境预评，共 77 个 S 级，每条带评级理由；文件头记录评级标准（`criteria`） |
| 人工覆盖 | 特性页可把任意特性改为 S 级或普通并填写理由；修改后 `rating_source=manual`，之后的自动预评**不会覆盖**人工结论；后台操作日志记录每次修改 |
| 免责说明 | 评级是**主观判断**，不是官方数据；页面同时显示评级来源（LLM 预评 / 人工修改） |

## 2.3 双打对战辅助（Smogon 使用率统计）

| 项目 | 内容 |
| --- | --- |
| 来源 | <https://www.smogon.com/stats/> —— Smogon University 每月公开的 Showdown 天梯统计（纯文本），非游戏客户端数据，无需密钥 |
| 采集方式 | `services/api/scripts/fetch_doubles_stats.py` 抓取「使用率总表 + 招式 / 道具 / 配点明细」，写入仓库 `data/doubles/{format}.json`；`scripts/sync_doubles.py` 再导入 SQLite。抓取是手动低频操作（每月一次即可），站点运行时不访问 Smogon |
| 格式与快照 | 冠军（`gen9championsvgc2026regmc`，2026-09，cutoff 1760）· 朱紫 Reg I（`gen9vgc2026regi`，2026-04，1630）· 剑盾 VGC 2022（`gen8vgc2022`，2022-11，1630）· BDSP 双打（`gen8bdspdoublesou`，2021-12，1500）。**每个格式固定一个历史月份**，页面始终展示「月份 + cutoff」，不把旧统计冒充当前环境 |
| 为什么选这些档位 | BDSP / 剑盾 后期天梯样本很少；moveset 明细在高分段只收录样本足够的宝可梦，因此这两档选较低 cutoff 以覆盖更多宝可梦。朱紫 Reg I 是最后一个朱紫官方双打规则；冠军取最新完整月份 |
| 展示内容 | 使用率排名与出场率、主流配点（性格 + 六项 EV / 能力点）、特性、道具、招式、常见队友（可跳转图鉴）、太晶属性（仅朱紫）。招式条目带属性徽章（配色与招式列表页一致，来自 `move_ref.type`） |
| 配点含义 | 剑盾 / BDSP / 朱紫的配点是 EV（单项 0–252）；**宝可梦冠军没有 IV 系统**，统计里的数字是能力点（单项上限 32，社区常见合计 66），页面标注「点」而非 EV |
| 个体值（IV） | **Smogon 不统计 IV**。页面上的 IV 是按配点与招式推断的**建议值**（如特攻向 0 攻、空间队 0 速），明确标注「推断 · 非数据源字段」，不代表真实对局数据 |
| 中文名称 | 道具 / 招式 / 特性 / 性格的中文名来自 PokéAPI `zh-hans`，汇总在 `data/doubles/labels.json`；PokéAPI 尚未收录的新特性（`aura-guard` / `eelevate` / `fire-mane`）保留英文名，不猜译 |
| 道具参考表 | `item_ref`：`scripts/sync_items.py` 从 PokéAPI `/item/{slug}` 拉取双打统计里出现的 **257 个道具**的中文名（zh-hans → zh-hant）、分类、英文短说明与成本，并把 30×30 图标缓存到 `var/media/items/{slug}.png`（wsrv 代理 PokéAPI sprites 仓库）。`leek` 在 PokéAPI 里叫 `stick`（地址映射，slug 不变）；`pretty-feather` 上游没有条目，保留手写中文名「美丽之羽」、不虚构图标。说明字段只有英文（PokéAPI 的中文说明覆盖不全），界面不猜译 |
| 名称映射 | Smogon 用的是 Showdown 显示名（含超级进化与形态，如 `Charizard-Mega-Y`）。导入时按「精确 → 逐级去形态后缀 → 唯一词根」映射到全国图鉴编号；词根有歧义时（如 `Nidoran`）不猜，保留记录但不链接图鉴 |
| 格式顺序 | 页面按 **BDSP → 剑盾 → 朱紫 → 冠军** 排列（与交换机器人的使用频率一致） |
| 使用率排行页 | `/usage`（`GET /usage-ranking?format=…`）与详情页同源，读取同一张 `doubles_pokemon_stat` 表：按名次升序展示排名、使用率、属性、前 4 个招式 / 前 3 个特性与道具、最常见配点与样本数。支持中文名 / 英文名 / Showdown 名 / 图鉴编号搜索和分页；未导入数据的格式仍显示标签（`entries=0`），与「接口失败」区分 |
| Showdown 导出 | 详情页可为每个格式生成 Showdown 代码：默认 IV 全 31、闪光、CHS、雌性，性格 / EV（或能力点）/ 特性 / 道具 / 招式取推荐值，均可手动修改（特性与招式是下拉框，选项按使用率降序、显示「中文（English）· 比例」，招式下拉框旁显示属性徽章，写进代码的始终是英文）；BDSP / 剑盾 / 朱紫分别在第一行加 `!tradeBDSP` / `!tradeSWSH` / `!tradeSV`，冠军不添加前缀。英文名来自 Showdown 公开客户端数据（`data/doubles/labels.json` 的 `*_en` 字段） |
| 版权注意 | 统计文本由 Smogon 社区整理，数据本身属于游戏事实；本项目引用时注明来源与统计月份。宝可梦名称与形象版权归 任天堂 / GAME FREAK / Creatures Inc. 所有 |

## 2.4 招式百科（学习者索引）

| 项目 | 内容 |
| --- | --- |
| 数值来源 | 与图鉴招式表相同：PokéAPI `/move/{name}`（中文名、属性、分类、威力/命中/PP、说明） |
| 学习者来源 | 从 `pokemon.moves_json` 展开：每个 (招式, 宝可梦) 一行，记录该宝可梦在哪些版本组、用什么方式（升级 / 学习器 / 教学 / 蛋招式…）学会 |
| 派生表 | `move_learner` 是纯派生数据，同步结束时整表重建（`services/move_service.py:rebuild_move_index`，约 7.9 万行）；不接受手工编辑，不会成为第二份真相来源 |
| 页面 | `/moves` 列表（搜索、属性 / 分类 / 仅学习器筛选、按威力 / 命中 / PP / 学习者排序、分页）与 `/moves/{slug}` 详情（数值、说明、按版本分组的「谁会这招」） |
| 双向链接 | 宝可梦详情页招式表 → `/moves/{slug}`；招式详情页学习者 → `/dex/{dex}` |
| 版本顺序 | 详情页版本标签按作品代次从新到旧（朱紫 → 剑盾 → … → 红绿），标签复用后端 `VERSION_GROUP_ZH` |

## 3. 演示数据

- 用途：无网络首启演示与自动化测试。
- 约定：文件与记录带 `is_demo: true`，界面上可见「演示数据」标记；数量极小（约 12 只），不代表真实图鉴。

## 4. 考试题库

- MVP 由本地事实规则生成：属性倍率（来自 `data/type-chart.json`）、图鉴事实（来自已同步的 PokéAPI 数据）。
- 每题带 `source_ref`（如 `type-chart:water->fire`），题目下方展示出处；**无来源的题目不允许存在**。

## 5. 版权与分发

- Pokémon Showdown 的 MIT 许可证**不代表**宝可梦品牌与素材可自由分发。
- 本项目当前为非商业个人学习用途；若将来公开分发安卓应用，需先核对所涉及素材与商标的条件。
- 站内使用的图标来自 lucide（MIT）、字体 Geist（OFL），界面为原创绘制，不使用官方美术素材。

## 6. 第三方许可清单（待 P1 补充）

| 组件 | 许可 |
| --- | --- |
| lucide-react | ISC |
| Geist 字体 | SIL OFL 1.1 |
| react / vite / tailwindcss 等 | 各自 MIT / BSD 许可，见各 package license |

> AI生成
