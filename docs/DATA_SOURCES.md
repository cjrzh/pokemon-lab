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
- **用途**：宝可梦名称（中/英）、属性、种族值、特性、进化链等基础图鉴数据。
- **落地方式**：后端 `clients/pokeapi.py`（P1）代理请求并缓存到本地 SQLite；`sync_pokeapi.py` 手动预拉取，站点离线可用。
- **许可注意**：PokéAPI 提供的是整理后的游戏数据，宝可梦**形象与商标版权仍归 任天堂 / GAME FREAK / Creatures Inc.**，本项目为非商业个人学习用途，不使用官方美术素材。

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
