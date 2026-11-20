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

## 2.0 宝可梦形态（同一图鉴编号下的其它样子）

| 项目 | 内容 |
| --- | --- |
| 来源 | PokéAPI `pokemon-species/{dex}` 的 `varieties`，形态本身取 `/pokemon/{name}`，英文形态名取 `/pokemon-form/{id}` |
| 收录规则 | **只收录机制上不同的形态**：属性 / 种族值 / 特性 / 体重任一不同。体重会影响「重磅冲撞」「踢倒」等招式的伤害，因此算机制差异；身高只影响图鉴展示，不算 |
| 排除 | 纯外观形态：超极巨化（`*-gmax`）、霸主（`totem-*`）、只差身高的载具形态（故勒顿 / 密勒顿的 build 形态） |
| 规模 | 约 186 个物种 / 242 个形态，例如武道熊师「一击流 / 连击流」、洛托姆的五种家电形态、喷火龙两种超级进化… |
| 中文名 | `data/forms/zh-hans.json`：`suffixes` 是通用后缀（超级进化、阿罗拉的样子…），`forms` 是针对具体形态的覆盖（同一后缀在不同物种下含义不同）。查不到时不猜译，界面回落英文形态名 |
| 图片 | 形态立绘与 96×96 小图标缓存到 `services/api/var/media/forms/{artwork,sprites}/`，经 wsrv 代理下载（直连 raw.githubusercontent 不稳定） |
| 接口 | `GET /pokemon/{dex}` 的 `forms` 菜单；`GET /pokemon/{dex}/forms/{slug}` 返回该形态的属性 / 种族值 / 特性 / 身高体重 / 立绘（`slug=default` 表示默认形态） |
| 为什么单独建表 | 图鉴编号是 1–1025 的一对一主键，详情、搜索、双打映射都依赖它；形态是「同一只宝可梦的另一个样子」，放 `pokemon_form` 避免列表出现重复编号 |

## 2.05 对战分类（普通 / 准神 / 一级神 / 二级神 / 幻兽 / 悖谬）

| 项目 | 内容 |
| --- | --- |
| 来源 | **项目整理的社区通用分类**，不是官方字段：名单在 `data/battle-classes.json`（带 `criteria` 说明判定标准） |
| 为什么单独建表 | 准神是社区约定（三段进化最终形态、合计 600，超级进化不算）；一级神 / 二级神的界限来自官方规则「限制传说的宝可梦」，**不是种族值** —— 超梦 680 属二级神，无极汰那 690、太乐巴戈斯 600 属一级神；悖谬按物种名固定，PokéAPI 没有对应字段 |
| 判定顺序 | 悖谬 > 幻兽 > 一级神 > 二级神 > 准神 > 普通（一只只归一类） |
| 依赖字段 | `is_mythical` → 幻兽；`is_legendary` 且不在 restricted 名单 → 二级神；名字在 `pseudo_legendary` / `restricted` / `paradox` 名单 → 对应分类；其余为普通 |
| 实现 | `domain/battle_class.py`（纯函数，进程内缓存）；列表接口返回 `battle_class` / `battle_class_zh`，并支持 `?battle_class=` 筛选（翻译成 SQL 条件，分页正确） |
| 数量 | 普通 901 · 准神 10 · 一级神 25 · 二级神 46 · 幻兽 23 · 悖谬 20（合计 1025） |
| 数据缺失时 | 分类降级为「普通」，不阻断图鉴浏览 |
| 界面 | 图鉴页顶部筛选条（带各分类数量）；**列表 / 卡片**与**详情页 Hero**都显示分类徽章（列表隐藏「普通」以免噪声；详情页显示，便于确认）；悬停提示「项目整理，非官方字段」 |

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
| 特性名称与说明 | 从已同步宝可梦的 **`pokemon` 与 `pokemon_form` 两张表**的 `abilities_json` 汇总到 `ability` 表（同一特性跨宝可梦共享）。形态独有特性（如蕾冠王的「人马一体」`as-one-glastrier` / `as-one-spectrier`）只存在于形态表，必须一并汇总，否则参考表里只有 slug、界面显示不出中文。中文说明由 `data/flavor-zh/abilities-zh.json` 的 `entries` 兜底，中文名由同文件的 `names` 兜底 |
| S 级评级 | `data/abilities/s-tier.json`：由 LLM 按当前对战环境预评，共 77 个 S 级，每条带评级理由；文件头记录评级标准（`criteria`） |
| 人工覆盖 | 特性页可把任意特性改为 S 级或普通并填写理由；修改后 `rating_source=manual`，之后的自动预评**不会覆盖**人工结论；后台操作日志记录每次修改 |
| 免责说明 | 评级是**主观判断**，不是官方数据；页面同时显示评级来源（LLM 预评 / 人工修改） |

## 2.3 双打对战辅助（Smogon 使用率统计）

| 项目 | 内容 |
| --- | --- |
| 来源 | <https://www.smogon.com/stats/> —— Smogon University 每月公开的 Showdown 天梯统计（纯文本），非游戏客户端数据，无需密钥 |
| 采集方式 | `services/api/scripts/fetch_doubles_stats.py` 抓取「使用率总表 + 招式 / 道具 / 配点明细」，写入仓库 `data/doubles/{format}.json`；`scripts/sync_doubles.py` 再导入 SQLite。抓取是手动低频操作（每月一次即可），站点运行时不访问 Smogon |
| 格式与快照 | 冠军（`gen9championsvgc2026regmc`，2026-10，cutoff 1760）· 朱紫 Reg I（`gen9vgc2026regi`，2026-04，1630）· 剑盾 VGC 2022（`gen8vgc2022`，2022-11，1630）· BDSP 双打（`gen8bdspdoublesou`，2021-12，1500）。**每个格式固定一个历史月份**，页面始终展示「月份 + cutoff」，不把旧统计冒充当前环境 |
| 为什么选这些档位 | BDSP / 剑盾 后期天梯样本很少；moveset 明细在高分段只收录样本足够的宝可梦，因此这两档选较低 cutoff 以覆盖更多宝可梦。朱紫 Reg I 是最后一个朱紫官方双打规则；冠军取最新完整月份 |
| 展示内容 | 使用率排名与出场率、主流配点（性格 + 六项 EV / 能力点）、特性、道具、招式、常见队友（可跳转图鉴）、太晶属性（仅朱紫）。招式条目带属性徽章（配色与招式列表页一致，来自 `move_ref.type`） |
| 配点含义 | 剑盾 / BDSP / 朱紫的配点是 EV（单项 0–252）；**宝可梦冠军没有 IV 系统**，统计里的数字是能力点（单项上限 32，社区常见合计 66），页面标注「点」而非 EV |
| 个体值（IV） | **Smogon 不统计 IV**。页面上的 IV 是按配点与招式推断的**建议值**（如特攻向 0 攻、空间队 0 速），明确标注「推断 · 非数据源字段」，不代表真实对局数据 |
| 中文名称 | 道具 / 招式 / 特性 / 性格的中文名来自 PokéAPI `zh-hans`，汇总在 `data/doubles/labels.json`；PokéAPI 尚未收录的新特性（`aura-guard` / `eelevate` / `fire-mane`）保留英文名，不猜译 |
| 道具参考表 | `item_ref`：`scripts/sync_items.py` 从 PokéAPI `/item/{slug}` 拉取双打统计里出现的 **257 个道具**的中文名（zh-hans → zh-hant）、分类、英文短说明与成本，并把 30×30 图标缓存到 `var/media/items/{slug}.png`（wsrv 代理 PokéAPI sprites 仓库）。`leek` 在 PokéAPI 里叫 `stick`（地址映射，slug 不变）；`pretty-feather` 上游没有条目，保留手写中文名「美丽之羽」、不虚构图标。说明字段只有英文（PokéAPI 的中文说明覆盖不全），界面不猜译 |
| 道具页 | `/items`（`GET /items`）：搜索（中英文名 / 说明）、按 PokéAPI 分类筛选（分类中文名由后端 `CATEGORY_ZH` 映射，未列出的原样展示 slug）、分页；每行展示 30×30 图标、中文名 + 英文名、分类与**中文说明**（英文原文可折叠查看） |
| 道具说明中文 | 上游 PokéAPI 的 `effect_entries` 只有英文，且 62 个道具没有说明。`data/items/effects-zh.json` 是**项目自译**，覆盖全部 257 个道具（含 39 个上游无说明的超级进化石，按「让 X 进行超级进化」统一句式补写）。`scripts/backfill_item_effects_zh.py` 写入 `item_ref.effect_zh` 并标 `effect_zh_source=project`，界面折叠区标注「项目自译」，**不冒充官方文本** |
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
| 补录缺失招式 | `move_ref` 平时只收录「某只宝可梦的招式表里出现过」的招式。PokéAPI 的 `/pokemon/{id}` 偶尔漏招（如 Urshifu #892 没有「水流连打」），而双打统计又用到它，表现为详情页 / 排行页的招式缺属性。`scripts/backfill_move_refs.py` 按 slug 直接拉 `/move/{slug}` 补齐数值，**不修改 `pokemon.moves_json`**（不伪造学习记录，「谁会这招」不受影响） |

## 2.5 双打建队与 Showdown 导出

| 项目 | 内容 |
| --- | --- |
| 数据来源 | 复用已有数据：招式合法性来自 `pokemon.moves_json`（按版本组）、特性来自 `abilities_json`、推荐配置来自 `doubles_pokemon_stat`（Smogon 使用率统计）；不引入新上游 |
| 版本映射 | BDSP → `brilliant-diamond-shining-pearl`、剑盾 → `sword-shield`、朱紫 → `scarlet-violet`、冠军 → `champions`，与格式定义 `domain/team_rules.py:FORMAT_VERSION_GROUP` 一一对应 |
| 合法性规则 | 编号不重复、道具不重复（非空时）、最多 6 只、招式 ≤ 4 且能在该版本学会、特性必须属于该宝可梦、EV 单项 ≤252 / 合计 ≤508、能力点单项 ≤32 / 合计 ≤66、IV 0–31。规则是纯函数（`domain/team_rules.py`），有独立单测 |
| 前代招式继承 | 合法招式 = 自己的招式表 ∪ **进化链上前代的招式表**（`pokemon.evolution_json` 往上游走）。宝可梦保留进化前学过的招式，只看自己的表会把合法配置误判为非法 —— 例：雷丘的 Fake Out 是皮丘的蛋招式（SV/SwSh/BDSP 都合法）。Showdown 官方校验器用的是同一规则（`getFullLearnset`）。只向上游继承，不反向（皮丘拿不到雷丘独有的招式） |
| 名称归一化 | 建队时招式 / 特性存 Showdown 显示名（`Blaze`、`Flamethrower`），本地数据是 slug（`blaze`、`flamethrower`）；校验前统一 `showdown_slug()` 归一化，避免大小写与空格差异误判 |
| 数据缺失时 | 本地没有某只宝可梦在该版本的招式数据时，**不把「不知道」当成「不合法」**：跳过招式校验并在 `warnings` 里如实提示 |
| 队伍存储 | SQLite `team` / `team_member`（**不限数量**；个人自用，不做浏览器隔离，所有队伍对所有访问者可见）；`team.owner_key` 列保留以兼容旧数据，但不再参与查询过滤 |
| 批量设置 | `POST /teams/batch`：对一组成员统一设置闪光 / 等级 / 性别，返回改好的成员（**不落库**，进草稿）。性别不是自由选择的 —— `gender_rate` 为 0 只能雄性（尼多朗）、8 只能雌性（尼多兰）、-1 无性别（超梦）—— 这些成员**保持原样**并在 `skipped` 里说明原因，而不是被改成非法值。规则是纯函数（`domain/team_rules.py`） |
| 语言选项 | 每只可单独选导出语言（CHS / CHT / ENG / JPN / KOR / FRA / GER / ITA / ESP），导出时输出 `Language: XX`；**剑盾格式不输出这一行**（复制给交换机器人不需要），导入缺省 CHS（代码里带 `Language:` 行则原样带回）。取值受白名单校验 |
| 极巨化等级 | 仅剑盾（`format_key=swsh`）的成员有「极巨化等级」0–10，默认 **10**（Showdown 的默认值），落库为 `team_member.dynamax_level`（NULL 与 10 等价，界面显示 10）。导出**始终写一行** `Dynamax Level: N`（未设置按 10），复制出去的代码明确带上这个参数；导入识别该行，超出 0–10 的取值忽略。朱紫没有极巨化、冠军不输出这一行 |
| 超极巨化 | 仅剑盾、且只有带 G 形态的物种 / 形态可以开启，落库为 `team_member.gigantamax`（布尔）。清单来自 Showdown `pokedex.json` 的 `canGigantamax`（34 个物种 / 形态，含连击流等形态差异），由 `scripts/gen_form_showdown.py` 写入 `data/forms/showdown.json:gigantamax`（键为 Showdown 名，避免本地默认名带后缀时漏匹配）；`/team-options` 返回 `can_gigantamax` 与 G 招式名（如 `G-Max Wildfire`），编辑器的「超极巨化」开关在剑盾**始终出现**：有 G 形态时可勾选，没有时禁用并标「无 G 形态」，这样两个参数在页面上都能看到。导出写 `Gigantamax: Yes`（紧跟在 `Dynamax Level` 之后，两行相对顺序与 Showdown 一致；解析按行识别，整体行序不影响导入）；导入识别该行。保存校验拒绝：非剑盾格式开启、没有 G 形态的物种开启。导入 `Charizard-Gmax`（后缀）或 Limitless 队表的 `Gigantamax Charizard`（前缀）时都会剥掉别名、解析到基础物种并自动标记超极巨化。**官方赛事页也统一用这个格式**：赛事队表的 `-Gmax` 别名在同步时折算成「基础形态 + `gigantamax` 标记」，导出的代码只有 `Gigantamax: Yes`，不再出现 `Charizard-Gmax` 物种名（旧库数据在读取时会按新规则重新渲染）。**注意**：Showdown 的队伍文本把超极巨化写成 `Gigantamax: Yes` 行，而不是把物种名改成 `-Gmax`；本地以「物种 + 标记」表达，避免图鉴编号重复 |
| 加入成员 | 建队页按**中文名 / 英文名 / 图鉴编号**搜索加入，走 `GET /pokemon?q=…&prefix=true`：`prefix=true` 只匹配名称开头（输入「喷火」命中喷火龙 / 喷火驼），图鉴页保留子串匹配（记得名字中段也能搜到）。用户输入的 `%` / `_` 按字面转义，不当成 LIKE 通配符 |
| 加入后回填 | 选中后默认走 `/team-options` 的推荐值（特性 / 道具 / 招式 / 配点 / 性格），并统一换成后端确认的 Showdown 规范名（`charizard` → `Charizard`，导出需要）；**新加入的默认闪光、100 级、雌性**（性别按图鉴 `gender_rate` 校正，尼多朗这类会改成雄性）；已填字段不覆盖，全部可在编辑器里逐项改 |
| 配点输入 | EV 可手动输入任意数字，**不自动取整、不偷偷夹到上限**；单项超过 252 或合计超过 508 时输入框标红并在下方说明原因，保存时由后端 `validate_points` 最终拦截。冠军格式的能力点上限为单项 32 / 合计 66 |
| 性格标注 | 下拉框与选中后的说明都标注增减（如「固执 · 攻击 ↑ / 特攻 ↓」），数据在 `apps/web/src/features/doubles/showdown.ts:NATURE_EFFECT`，25 种性格全覆盖，中性性格标「无增减」 |
| 编辑器候选 | 特性下拉框按使用率降序，默认选中使用率最高的那个（标注「★推荐」），值为 Showdown 英文名、展示中文名；道具下拉框合并两处来源 —— 该格式统计里这只宝可梦实际用过的道具（带使用率与图标）+ 道具百科全量 257 条（分页取完），找不到的仍可手输英文名；招式条按使用率排序、右侧箭头链到 `/moves/{slug}` 详情 |
| Showdown 导出 | `GET /teams/{id}/showdown`：整队文本，首行是交易前缀（BDSP `!tradeBDSP` / 剑盾 `!tradeSWSH` / 朱紫 `!tradeSV`，冠军无前缀）；IV 全 31 时省略 IV 行；每只输出 `Language:` 行（默认 CHS，**剑盾不输出**）；剑盾额外输出 `Dynamax Level`（**始终写出**，未设置按 10）与 `Gigantamax: Yes`（开启时）。渲染是纯函数（`domain/showdown_export.py`），与 LLM 提示词共用同一实现，不会出现「导出一种格式、给模型另一种」 |
| 单只复制 | 建队页每只成员摘要行有「复制 Showdown 代码」按钮：复用前端 `features/doubles/showdown.ts:renderShowdown`（与详情页导出同一规则），**首行带该队伍的交易命令**，可直接发给交换机器人。剪贴板 API 不可用（非 HTTPS / 用户拒绝）时降级为可全选的文本框，而不是静默失败 |
| 整队复制 | 建队页顶部「复制整队」按钮：`features/teams/showdownText.ts:renderTeamShowdown` 把当前草稿的全部成员拼成一份 Showdown 代码（**交易前缀只在首行出现一次**，成员之间空一行），可直接粘进 Showdown 的「Import/Export」框或发给交换机器人。规则与单只复制完全相同（含剑盾的极巨化参数、不含剑盾的 `Language:` 行），降级文本框更高以便选中整段 |
| Showdown 导入 | 建队页「导入代码」→ `POST /teams/import`：解析同样的格式回到成员配置，**不落库**，进编辑器让用户确认后才保存。解析是纯函数（`domain/showdown_parser.py`）：认不出的整只跳过并列入 `problems`（不猜配置），认不出的单行忽略（`Happiness` / `Pokeball` 等不影响对战配置）；剑盾的 `Dynamax Level` / `Gigantamax: Yes` 会被保留。头行兼容中文玩家习惯的 `Charizard (喷火龙) (M)` 写法（前面是英文物种名、括号里是中文名时自动对调，昵称仍保留）。物种名 → 图鉴编号复用双打统计的名称索引；`Charizard-Gmax` 与 `Gigantamax Charizard` 两种写法都会剥掉别名、解析到物种并标记超极巨化。**结果追加**进当前队伍（一只也能导，可反复导入拼队），对话框按剩余空位与已有编号先过滤一遍，被跳过的条目如实列出。导出 → 导入是往返一致的（有测试覆盖） |
| 队伍评价 | `POST /teams/analyze`（草稿，不落库）与 `POST /teams/{id}/analyze`（保存到队伍）：分两层。①**打击面 / 缺失面 / 共同弱点**由 `domain/team_analysis.py` 纯函数按**属性**推算（不逐招解析，这样导入的英文招式名也能覆盖；口径写在页面说明里），有独立单测、结果可复现；②**改进建议 / 玩法推荐**由 LLM 生成 —— 它只负责把结构化结论翻译成可执行建议，不参与计算 |
| 提示词内容 | 交给 LLM 的是**整支队伍的 Showdown 代码**（`domain/showdown_export.py`，与导出接口同一实现），含道具 / 特性 / 性格 / EV / IV / 等级 / 太晶 / 招式，再附中文名与属性、以及程序算出的打击面 / 缺失面 / 共同弱点。这样模型能引用真实配置（实测会点名 `Miracle Seed`、`Quick Guard`、`0 Def IV` 这类细节），而不是只按属性泛泛而谈。草稿评价的 `format_key` 决定是否输出太晶与默认等级 |
| 评价流式输出 | 页面走 SSE（`/teams/analyze/stream`、`/teams/{id}/analyze/stream`）：先推 `coverage`（计算结果），再逐段推 `delta`（AI 正文增量），最后 `done`。**原因**：配置的网关模型是推理模型，会先输出一大段 `reasoning_content` 再给正文，一次完整回答要 10–50 秒；一次性请求会撞上前端 10 秒超时（表现为「无法生成评价 · 请求超时」）。流式下只要字节在流动就不会超时，思考阶段页面显示「AI 正在思考…」。`enable_thinking: false` 被该网关忽略，关不掉推理 |
| 评价落库 | 已保存队伍的评价存在 `team.analysis_json`（完整快照）+ `analysis_at`（生成时间）+ `analysis_members_hash`（成员指纹）。指纹只取影响结论的字段（编号 / 招式 / 特性 / 道具 / 太晶），所以改昵称或导出语言不会误判过期；换招式、换道具则会。读取时重新算一遍指纹比对，不一致就在响应里标 `stale`，页面提示「队伍已改动，评价已过期」。存快照而不是每次重算：LLM 调用慢且结果不稳定，用户要能随时回看上次结论 |
| LLM 接入 | `app/clients/llm_client.py` 调 OpenAI 兼容的 `chat/completions`（用 httpx，不引 openai SDK）。配置读 `.env` 的 `TELECOM_BASE_URL` / `TELECOM_API_KEY` / `TELECOM_FLASH_MODEL`（备用 `TELECOM_MAX_MODEL`）—— 这几个变量不带 `POKEMON_LAB_` 前缀，配置类用 `validation_alias` 显式读取。**未配置或调用失败都不影响计算结果**：接口照常返回打击面等，`llm_error` 说明原因，页面提示「AI 建议暂不可用」并可重试（主模型失败会自动用备用模型再试一次） |
| 图片与链接 | 建队编辑器里的宝可梦图标与名字链到 `/dex/{dex}`；招式条目链到 `/moves/{slug}`（更早的改动） |
| 成员排序 | 拖动左侧手柄调整出场顺序（原生 HTML5 DnD，未引入拖拽库）；也可用行内的上移 / 下移按钮（键盘与触屏可用）。顺序即 `team_member.position`，保存时按列表顺序整体重写，后端读取也按 position 排序 |
| 队伍排序 | 左侧「我的队伍」列表同样支持拖动与上下按钮，顺序存 `team.sort_order`。**新建队伍插到最顶端**（取当前最小 `sort_order` − 1），建完立刻在左侧列表顶部看到、不用滚到底。`PUT /teams/order` 提交完整 id 列表，不存在的 id 忽略而不是报错。**按版本筛选时**拖动的是可见子集，前端用 `mergeSubsetOrder` 把子集新顺序填回完整列表再提交，未显示队伍的相对位置不变 |

## 2.6 建队形态选择（P9）

| 项目 | 内容 |
| --- | --- |
| 问题 | 洛托姆、厄诡椪、爱管侍、超级喷火龙等同一图鉴编号下有多个机制不同的形态；旧建队页只按编号取统计，遇到多条记录会 500（`scalar_one_or_none`），且无法选择形态 |
| 修复 | `GET /pokemon/{dex}/team-options` 支持 `form` 参数：不传时自动选**使用率最高的形态**（洛托姆 → 清洗洛托姆、喷火龙 → 超级进化 Y），`form=default` 明确选默认形态；返回 `forms` 列表（含默认形态，按使用率降序）与该形态的合法招式 / 特性 / 推荐配置 |
| 形态专属招式 | 选了形态就按形态的招式表取（清洗洛托姆有「热水」、加热洛托姆有「过热」）；形态表缺失时退回按编号合并的结果，不把「没数据」当「不会」 |
| 名称映射 | `data/forms/showdown.json`：本地形态名（PokéAPI 口径）→ Showdown 显示名（`rotom-wash` → `Rotom-Wash`、`ogerpon-wellspring-mask` → `Ogerpon-Wellspring`、`indeedee-female` → `Indeedee-F`）。由 `scripts/gen_form_showdown.py` 用 Showdown 官方 pokedex.json 生成，242 个形态全覆盖、0 未匹配；少数对不上的（一家三口 ↔ `Maushold`、米立龙 ↔ `Tatsugiri`）写在脚本的 `CURATED` 里并注明原因 |
| 保存与回显 | 形态不单独落库 —— 它已经体现在 `showdown_name` 里。队伍详情接口按 `showdown_name` 反查 `form`，重新打开队伍时选择器定位到当初的形态 |
| 切换形态 | 换了形态会重新取该形态的选项，并**替换**属于旧形态的招式 / 特性（避免「热洛托姆用热水」）；用户在新形态也合法的配置保留 |
| 界面 | 成员编辑器展开区新增「形态」分组：图标 + 中文名 + 使用率，点击切换；只有一种形态时不显示 |

## 2.7 图图犬的「写生」招式范围（P10）

| 项目 | 内容 |
| --- | --- |
| 问题 | 图图犬的 `moves_json` 只有「写生」一个招式（游戏机制如此），建队页的合法招式列表照搬数据 → 只剩 1 个选项，无法配招 |
| 规则 | 按 Pokémon Showdown 官方校验器（`sim/team-validator.ts`）描述：写生可复制**本版本任意宝可梦能学会**的招式，排除带 `nosketch` 标记的招式（暗黑洞、复活祈祷、晶光星群、XX 扭矩等） |
| 实现 | `domain/sketch.py`（纯函数 + 禁写生名单）；`build_validation_context` 对图图犬把「本版本全部可学招式 − 禁写生」并入合法招式。选项与保存校验走同一条路径 |
| 规模 | 朱紫 654 个、剑盾 623 个、BDSP 506 个、冠军 486 个可写生招式（本地按 `move_learner` 的版本分布统计） |
| 限制 | 本地没有「招式世代」字段，剑盾规则下会允许写生第八代之后的招式（官方规则只允许第八代以前）；图图犬不在剑盾/冠军图鉴里，不影响实战。一场对战仍只能写生 1 个招式（规则由游戏决定，界面有说明） |
| 界面 | 图图犬展开配置时在招式区上方显示说明：「只会写生，这里列出通过写生可获得的招式（N 个），暗黑洞等已排除」 |

## 2.8 建队「跳走再回来」的草稿与形态回显（P11）

| 项目 | 内容 |
| --- | --- |
| 现象 | 建队到一半切到别的页面再回来，页面显示「无法加载该宝可梦的建队选项」 |
| 根因 1 | 队伍详情接口把**默认形态**也反查成 `form=<slug>`（如 `Garchomp` → `garchomp`）。前端拿它请求 `?form=garchomp`，后端只认 `pokemon_form` 里的非默认形态 → 422。日志里成批的 `form=clefable` / `form=snorlax` / `form=smeargle` 422 就是它 |
| 修复 1 | 反查以 `pokemon_form`（数据库）为准，只返回真实形态；与默认形态同名的返回 `default`（明确选择默认形态），避免被「自动选使用率最高形态」替换 |
| 根因 2 | 未保存的新队伍草稿只存在组件 state，离开页面即丢失 |
| 修复 2 | 未保存草稿（`id=0`）暂存到 `sessionStorage`（键 `pokemon-lab:team-draft`，含形态选择），回到页面自动恢复；已保存队伍不暂存（以数据库为准）。数据损坏时静默丢弃，不阻断页面 |
| 保护 | 编辑器拿到 422 时只影响那一只的选项；页面本身仍可用。已保存队伍全量扫描（14 队 / 81 名成员）请求选项全部 200 |
| 新建要点两次（P12） | 打开某支已保存队伍后点「新建队伍」，第一次点击会被队伍详情的回填逻辑覆盖回去。根因：详情 → 草稿的同步写在**渲染期**，而 `setSearchParams` 是异步导航 —— 点击后先渲染一次（草稿已是新队伍、URL 里还是 `?team=3`），渲染期逻辑看到「`draft.id(0) ≠ 详情.id(3)`」又把草稿换回旧队伍。修复：同步移进 `useEffect`（只在 `selectedId` / 详情数据变化时执行），并加一个「本地草稿」闸门 ref —— 新建 / 导入 / 删除后立即挡住详情回填，等 URL 真正清空再放下。有回归测试覆盖「点一次就切到空白草稿」 |

## 3. 演示数据

- 用途：无网络首启演示与自动化测试。
- 约定：文件与记录带 `is_demo: true`，界面上可见「演示数据」标记；数量极小（约 12 只），不代表真实图鉴。

## 4. 属性克制页的计算来源

- 计算完全在浏览器本地完成，数据是仓库内的 `data/type-chart.json`（Gen 6+ 规范克制表，见第 1 节）。
- 页面不调用后端：断网也能用；后端 `/types/evaluate`、`/types/reverse` 只用于交叉校验与接口消费。
- 两端共用 `data/type-chart.cases.json` 测试向量，pytest 与 Vitest 读取同一份。

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

## 7. 出卷（看图识宝可梦）与错题集

| 项目 | 内容 |
| --- | --- |
| 数据来源 | 复用图鉴数据：题目图片取自 `pokemon.artwork_path`（本地立绘，缺失回落远程），答案取 `name_zh` / `name_en`。不引入新上游 |
| 出题范围 | 按世代（`generation_introduced`）或编号区间（可叠加，取交集）；数量可选随机 N 或全量（全量按编号升序，随机为洗牌顺序） |
| 判分 | `domain/quiz.py` 纯函数：接受中文名或英文名，忽略大小写、空格、连字符与标点（NFKC 归一）。**不做模糊匹配** —— 自动判「差不多对」比判错更伤，答错时直接展示正确答案 |
| 答案保密 | 作答前接口不返回名称（`name_zh` / `name_en` / `expected_*` 均为 null），前端无法提前看到答案 |
| 存储 | `quiz_session`（范围快照 + 进度）/ `quiz_question`（题号、图鉴编号、作答与判分）/ `quiz_mistake`（按编号累计错误次数与最近作答）。名称与图片**不落库**，始终读当前图鉴数据 |
| 错题集 | 答错自动 upsert（同一只累计次数）；答对不自动移除 —— 是否已掌握由用户判断，界面提供单条移除与清空 |
| 边界 | 同一题不可重复作答（409）；试卷完成后不再接受作答；范围内无数据时返回 422 而不是出空卷 |

## 8. Smogon 历史使用率（P7）

| 项目 | 内容 |
| --- | --- |
| 来源 | <https://www.smogon.com/stats/> 的月度文本统计（`/{YYYY-MM}/{format}-{cutoff}.txt`），与第 2.3 节同源，但这里的范围是**全历史 + 多规则** |
| 抓取范围 | 只抓**双打 / VGC 相关格式**（目录见 `app/domain/smogon_catalog.py`，66 个格式，含早期无 `gen` 前缀的 `vgc2015` / `doublesou`）；跳过单打与随机格式 |
| 等级线 | 1500 / 1630 / 1760 三档（0 = 全分段不抓） |
| 历史深度 | Smogon 提供的全部月份，2014-11 起（当前 144 个月） |
| 增量策略 | 以 `(格式, 月份, 等级线)` 为唯一键，已存在的直接跳过；「同步最近 3 个月」是按钮的默认行为，「回补全部历史」显式传空范围。首次全量约 66 格式 × 144 月 × 3 档 ≈ 2.8 万个候选，**大部分会 404**（格式在多数月份并不存在），跳过后实际入库量远小于此 |
| 任务收尾 | 所有候选处理完后统一把任务标 `done`（不再只在「成功写入快照」分支判断）—— 否则最后一个候选是 404 / 解析失败时，状态会永远停在 `running`，前端一直转圈。单条下载失败只记 `failed` 并推进进度，不中断整批；并发/残留导致的重复快照（唯一约束冲突）按 `skipped` 处理。服务启动时把上一个进程留下的 `running` 记录收尾（走完的标 `done`、没走完的标 `error` 并写明中断位置），否则新同步会一直被「已有任务在运行」挡住 |
| 并发保护 | 「检查是否已有任务 + 创建任务」放在服务进程内的互斥锁里：双击按钮或两个标签页同时请求时只有一个任务会被创建（另一个 409），不会两个后台任务并发写同一批快照 |
| 存储 | `usage_snapshot`（月份 × 格式 × 等级线，含对战总数）+ `usage_snapshot_entry`（名次、Showdown 名、图鉴编号、使用率、场次）。**不存仓库文件**，避免仓库随历史膨胀 |
| 与既有「使用率排行」的区别 | 那个页是四固定格式的单一快照（含招式 / 道具 / 配点的深度数据，`double_format` / `double_pokemon_stat`）；这里是任意时间 / 规则 / 等级线的排行（只有名次与使用率）。两者互不影响 |
| 同步接口 | `POST /usage/sync`（后台任务，202）、`GET /usage/sync/{id}`（进度）、`GET /usage/sync/latest`、`POST /usage/sync/{id}/cancel`；同时只允许一个任务（409）。**单条目同步**：只传 `format_ids`（一个规则）即只同步该规则的全部历史月份 × 三档等级线；再配合 `months` / `cutoffs` 可收窄到单个快照。参数会校验：未知格式 / 未知等级线 / 空列表 / 月份格式不对都返回 422 |
| 查询接口 | `GET /usage?format=&month=&cutoff=&q=&page=`；未指定时取最新月份与有数据的格式。响应带 `has_snapshot`：区分「该快照还没同步」与「同步了但榜单为空」 |
| 数据缺失 | 404 记为 `skipped` 而不是失败；解析失败记 `failed` 并保留提示，不中断整批 |
| 界面 | `/usage/history`：版本 → 规则 → 月份 → 等级线筛选，同步按钮带进度条与取消；榜单可搜索、分页，名称链到图鉴。**单条目同步**：规则旁有「同步本规则 / 补齐本规则」（只抓当前规则，显示已同步月份数），选到未同步的快照时提示并给出「只同步这个快照」；本页发起的同步结束后自动刷新榜单 |

## 9. 官方赛事（P8）：成绩、队表与赛事使用率

| 项目 | 内容 |
| --- | --- |
| 来源 | <https://limitlessvgc.com> —— 社区维护的 VGC **线下官方赛事**数据库（communities 认可的事实标准）。`robots.txt` 为 `Disallow:`（全站允许抓取），本项目保持克制：单任务并发 3、按需增量 |
| 抓取范围 | 赛事列表按类型翻页（地区赛 / 国际赛 / 世锦赛 / 特殊赛事 / 国家赛 / Players Cup），成绩页 `/tournaments/{id}`、队表页 `/tournaments/{id}/teams`。Limitless 收录 2010–2026 共 416 场赛事；**已同步 354 场**（2010–2023 的旧赛事多数没有公开队表，逐场如实记录「无队表」），其中 99 场有完整队表、合计 6,981 支队伍 / 41,886 条队员配置 |
| 单场数据 | 名次 / 选手 / 国家 / 队伍预览；**完整队表**：6 只的物种 / 道具 / 特性 / 性格 / 太晶 / 招式 |
| **没有的数据** | 赛事队表**不公开 EV / IV**。本项目如实留空（导出与建队草稿里的配点为 0），不编造默认配点 |
| 赛事使用率 | 由该赛事的**全部队表重算**：分母是队数、每队同一物种只计一次 —— 与 Smogon「使用率」同口径（上限 100%），不是 Top Cut 统计。站点自带的 Statistics 页只覆盖 Top Cut，本项目不使用它 |
| 名称映射 | Limitless 的物种 slug → Showdown 官方名称 / 全国图鉴编号。首次同步下载 Showdown 官方 `pokedex.json` / `items.js`（进化石 → 超级进化形态）/ `learnsets.json` / `moves.json`，缓存在 `api_cache`（30 天）。名称走 Showdown 口径而非 PokéAPI：本地缺 `Indeedee`（只有 `indeedee-male`）这类默认形态条目，而赛事队表恰好大量使用 |
| 进化石处理 | `Charizardite Y` 等进化石会转换成对应形态（`Charizard-Mega-Y`）再落库 —— 与 Showdown 导出 / 交换机器人一致 |
| 特性对齐 | 站点写法 `As One (Glastrier)` 对齐到本地 `as-one-glastrier`；无法对齐的（源站笔误，如把 Glimmora 写成 Rough Skin）**保留原值**，由建队校验如实报出，不在同步时悄悄改写 |
| 可建队性 | 规则 → 本地建队格式：冠军（`m-*`）→ `champions`、朱紫（`sv*`）→ `sv`、剑盾（`swsh*` / `vgc22`）→ `swsh`。2019 及更早的规则本地没有建队数据，**只读**（仍可查看队表与使用率） |
| Showdown 代码格式 | 赛事页复制 / 一键建队的代码统一：**默认等级 100、默认闪光（`Shiny: Yes`）**；超极巨化写 `Gigantamax: Yes`（物种名保持基础形态；Limitless 的 `Gigantamax Charizard` 前缀与 `-Gmax` 后缀都会折算掉）；剑盾额外写 `Dynamax Level: 10`。这样同一段代码既能在 Showdown 里导入，也能被建队页解析（并回填 `gigantamax` / `dynamax_level`） |
| 一键建队 | 赛事页队伍卡片 →「一键建队」→ `/teams?fromTournament=&eventTeam=`：建队页拉取草稿并填进编辑器（**不落库**），队名自动带赛事与名次，备注写明「赛事未公开 EV / IV」。草稿默认满级 / 闪光，并带回超极巨化与极巨化等级；源站笔误导致的校验问题在返回里列出，用户可自行修正 |
| 增量策略 | 已抓过且有队表的赛事直接跳过（官方赛事的历史不会变）；无队表的赛事 30 天内不重试；`refresh=true` 强制重抓 |
| 存储 | `tournament` / `tournament_standing` / `tournament_team` / `tournament_team_member` / `tournament_usage` / `tournament_sync_run`（SQLite，不落仓库文件） |
| 接口 | `GET /tournaments`（规则 / 类型 / 年份 / 搜索）、`GET /tournaments/{id}`、`GET /tournaments/{id}/teams/{team_id}`（建队草稿）、`POST /tournaments/sync`、同步进度 / 取消 |
| 界面 | `/tournaments`：赛事列表 + 详情（队伍 / 使用率 / 名次三个视图），队表可展开、可复制 Showdown 代码、可一键建队；同步条带进度与取消 |
| 与 Smogon 的区别 | Smogon 是**天梯**统计（按月 / 等级线），这里是**线下赛事**的实际参赛队伍；两者口径不同，页面分开呈现 |

### 9.1 形态专属招式与特性的校验修复（随 P8 补齐）

官方赛事队表里大量出现形态专属配置（连击流武道熊师的「水流连打」、蕾冠王骑乘形态的「雪矛」、厄诡椪面具形态的「棘藤棒」、超级喷火龙的「日照」）。此前建队校验只看默认形态的 `pokemon.moves_json` / `abilities_json`，会把**合法配置判成非法**，进而导致一键建队无法保存。

| 项目 | 内容 |
| --- | --- |
| 修复 | 新增派生表 `pokemon_form_move`（形态 × 版本组 × 招式明细，来自 PokéAPI `/pokemon/{form}`）；校验时按图鉴编号合并全部形态的招式与特性 |
| 回填 | `scripts/sync_form_moves.py`（全量 / 区间 / 指定编号），幂等；`scripts/sync_forms.py --all-forms` 可同时补齐图鉴形态表 |
| 特性写法 | `As One (Glastrier)` 这类 Showdown 写法在校验里按「去掉括号」与「括号转连字符」两种归一化匹配，仍不匹配才报错 |
| 实测 | 2026 世锦赛 57 支邀请队、2026-10 五场地区赛 359 支队伍全部通过本地校验。全量 6,981 支队伍里 977 支（14%）仍有招式 / 特性与本地数据不一致，集中在 2024 年以前的朱紫规则（`svg` / `svi` 为主）：本地 PokéAPI 数据是**当前版本**口径，旧规则里合法而现已被移除的招式（如历代入的 `High Horsepower`、`Aurora Veil`、`Follow Me`）会被判为不可学。这类问题在同步时逐队记录到 `tournament_team.validation_json`，页面标「待核对」，**不阻断**查看与复制 |
| 已知限制 | ① 赛事未公开 EV / IV（一键建队的配点为 0，需自行调整）；② 本地招式数据是当前版本口径，旧规则的历史队表可能报「该版本无法学会」；③ 部分源站笔误（如把 Glimmora 写成 Rough Skin）保留原值并如实标注 |
