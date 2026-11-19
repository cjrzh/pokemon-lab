"""ORM 模型。

P0 只有元数据表；P1 加入 PokéAPI 落盘缓存与世代/规则版本参考数据；
P2 加入图鉴表与后台操作日志；收藏、笔记、考试等表在 P4–P5 逐步加入。
每张涉及竞技规则的表都必须带 `generation_id` / `ruleset_id` 维度 —— 见 docs/ARCHITECTURE.md。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: 当前数据库结构代次。正式引入迁移工具前，用它判断本地库是否落后于代码。
SCHEMA_VERSION = "0024_tournament_gmax"


class SchemaMeta(Base):
    """键值型元数据表：记录结构版本、初始化时间等运行期信息。"""

    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"SchemaMeta(key={self.key!r}, value={self.value!r})"


class ApiCache(Base):
    """PokéAPI 落盘缓存（ARCHITECTURE.md §8：TTL 默认 7 天，命中标 X-Cache: hit）。

    `payload` 存原始 JSON 文本；`fetched_at` 与 `expires_at`（Unix 时间戳，秒）
    支撑「上游失败但本地有旧缓存 → 返回旧数据并标 stale」的降级路径。
    """

    __tablename__ = "api_cache"

    cache_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"ApiCache(cache_key={self.cache_key!r}, expires_at={self.expires_at!r})"


class Generation(Base):
    """世代（参考数据，由种子脚本写入，P1 交付）。"""

    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)
    released_at: Mapped[str | None] = mapped_column(String(16), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Generation(id={self.id!r}, label={self.label!r})"


class Ruleset(Base):
    """规则版本（参考数据，如 gen9-standard）。所有个人数据都可按它区分。"""

    __tablename__ = "rulesets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Ruleset(id={self.id!r}, label={self.label!r})"


class Pokemon(Base):
    """图鉴条目（P2）。数据主体来自 PokéAPI 同步；支持后台手动编辑与新增。

    结构原则：
      - `types_json` / `stats_json` / `abilities_json` / `evolution_json` / `moves_json`
        存 JSON 文本，图鉴展示结构相对稳定，比拆成多张表更符合 MVP 复杂度。
      - `source` 记录数据来源（pokeapi / manual），`synced_at` 记录最近同步时间；
        手动编辑过的记录 `source=manual`，再同步时不会被覆盖（同步脚本按该标记跳过）。
      - `is_demo` 为 True 的记录是演示数据，接口与前端都会显式标记。
      - P2 打磨：补充官方立绘（本地缓存）、图鉴描述、分类、捕获/孵化等基础档案，
        以及招式学习表。`artwork_path` 是相对 `media_dir` 的路径（离线可用），
        `artwork_url` 是上游兜底地址。
    """

    __tablename__ = "pokemon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dex_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name_ja: Mapped[str | None] = mapped_column(String(64), nullable=True)
    types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    abilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evolution_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    moves_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    generation_introduced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_dm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_hg: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ---------- 图鉴档案（P2 打磨） ----------
    #: 分类，如「种子宝可梦」
    genus_zh: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: 中文分类来源：pokeapi / project（自译）
    genus_zh_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    genus_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: 图鉴描述（已清理换行与换页符）
    flavor_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    flavor_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 中文图鉴描述的来源：pokeapi（上游官方文本）/ project（上游缺失时的项目自译）
    #: / None（没有中文文本）。界面据此标注「项目自译」，不把译文冒充官方文本。
    flavor_zh_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: 本地立绘（相对 media_dir，如 artwork/1.png）；为空表示未缓存
    artwork_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: 上游立绘兜底地址（pokemon.com 官方图鉴立绘）
    artwork_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sprite_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    #: 本地小图标（相对 media_dir，如 sprites/25.png）；列表 / 特性拥有者用，缺失时回落远程地址
    sprite_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cry_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_legendary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_mythical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_baby: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: 雌性比例（0–8）；-1 表示无性别
    gender_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capture_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_happiness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hatch_counter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    growth_rate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    habitat: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shape: Mapped[str | None] = mapped_column(String(32), nullable=True)
    egg_groups_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    #: 数据来源：pokeapi（同步）/ manual（后台手动编辑或新增）
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="pokeapi")
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Pokemon(id={self.id!r}, dex_number={self.dex_number!r}, name_en={self.name_en!r})"


class MoveReference(Base):
    """招式参考数据（P2+）：中文名、属性、分类、威力等。

    招式数值在所有宝可梦之间共享，因此单独建表而不是重复写进每只宝可梦的
    `moves_json` —— 592 个招式若按 151 只重复存储会多出十倍冗余。
    `pokemon.moves_json` 只存「谁在什么版本组、用什么方式学会哪一招」。
    """

    __tablename__ = "move_ref"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    zh: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    damage_class: Mapped[str | None] = mapped_column(String(16), nullable=True)
    power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accuracy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---------- 招式百科（P2+） ----------
    #: Showdown 英文名（如 `U-turn`、`Will-O-Wisp`），用于展示与导出代码
    name_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: 能否批量为多只宝可梦学会（TM/TR/招式机），供列表筛选用
    is_machine: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: 有任意一只宝可梦能学会；同步时维护，避免 join 全表扫描
    learner_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"MoveReference(name={self.name!r}, zh={self.zh!r})"


class MoveLearner(Base):
    """招式学习者索引（P2+）：一只宝可梦在哪些版本组、用什么方式学会这招。

    这是从 `pokemon.moves_json` 展开出来的**派生表**：
      - 详情页「谁会这招」需要按招式反查，直接扫 1025 条 JSON（约 21 MB）不现实；
      - 每个 (招式, 宝可梦) 一行，`version_groups_json` 存
        `{"scarlet-violet": [{"method": "machine", "level": 0}, ...]}`，
        反查只需一次索引扫描；写入时整表重建，逻辑简单且不会漂移。
    不在这里存招式数值 —— 数值统一在 `move_ref`。
    """

    __tablename__ = "move_learner"
    __table_args__ = (
        UniqueConstraint("move_name", "dex_number", name="uq_move_learner"),
        Index("ix_move_learner_move", "move_name"),
        Index("ix_move_learner_dex", "dex_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    move_name: Mapped[str] = mapped_column(String(64), nullable=False)
    dex_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 版本组 → [{method, level}, ...]（已按版本从新到旧排序）
    version_groups_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    #: 展开出的 (版本组, 学习方式) 集合，形如 `scarlet-violet:machine,...`。
    #: 用 LIKE '%vg:method%' 就能按「哪一代的什么方式」筛选，避免解析 JSON 全表扫描。
    methods_key: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"MoveLearner(move={self.move_name!r}, dex={self.dex_number!r})"


class Ability(Base):
    """特性参考数据（P2+）：中文名与说明、S 级评级与评分理由。

    - 特性名与说明在同步时从各宝可梦的 `abilities_json` 汇总写入（同一特性跨宝可梦共享）；
    - `tier` 只有两个合法值：`s`（S 级）/ `normal`；
    - 评级由 LLM 预评（`rating_source=llm`），人工修改后置 `rating_source=manual`
      并记录修改时间，之后的自动评级不会覆盖人工结论；
    - `rating_note` 记录评级理由，便于回看「为什么给 S」。
    """

    __tablename__ = "ability"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    zh: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    effect_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    effect_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: 's' 表示 S 级特性；'normal' 为普通特性
    tier: Mapped[str] = mapped_column(String(8), nullable=False, default="normal", index=True)
    #: 评级理由（LLM 或人工填写）
    rating_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 评级来源：llm（自动预评）/ manual（人工修改）
    rating_source: Mapped[str] = mapped_column(String(8), nullable=False, default="llm")
    rated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Ability(name={self.name!r}, tier={self.tier!r})"


class ItemReference(Base):
    """道具参考数据（P2+）：中文名、分类、说明与本地图标。

    数据来自 PokéAPI `/item/{name}`（公开接口）：`names` 取 zh-hans / zh-hant，
    `effect_entries` 的英文短说明作为补充，`sprites.default` 指向 30×30 图标。
    图标经 wsrv 代理下载到 `media/items/{slug}.png`，离线可用。

    道具与双打统计是弱关联：统计里只存 slug，页面展示时按 slug 关联本表；
    查不到时回落到 `data/doubles/labels.json` 的中文名，界面显示占位而非假图标。
    """

    __tablename__ = "item_ref"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    zh: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: PokéAPI 分类 slug，如 held-items / berries / mega-stones
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    effect_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 道具说明的中文（项目自译，非官方文本）；上游没有中文说明
    effect_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 中文说明来源：project（项目自译）/ None（没有中文）
    effect_zh_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 本地图标（相对 media_dir，如 items/sitrus-berry.png）；指纹文件时为空
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: 上游图标地址（PokéAPI sprites 仓库）；前端兜底用
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PokemonForm(Base):
    """宝可梦的其它形态（P2+）：同一图鉴编号下机制上不同的样子。

    背景：PokéAPI 的 `pokemon-species/{dex}` 用 `varieties` 描述形态。默认形态的
    数据在 `pokemon` 表；这里只存**除默认形态外、且机制上有差异**的形态
    （属性 / 种族值 / 特性 / 身高体重任一不同）—— 纯外观差异（性别、颜色变体、
    剑盾的极巨化只改外形）不收录，避免把图鉴变成形态大全。

    `name_en` 是 PokéAPI 的完整形态 slug（如 `urshifu-rapid-strike`），
    同时也是主键：同物种的形态之间、以及跨物种之间都不会重复。
    中文形态名来自 `data/forms/zh-hans.json`（PokéAPI 的 form names 没有中文）。
    """

    __tablename__ = "pokemon_form"
    __table_args__ = (
        Index("ix_pokemon_form_dex", "dex_number"),
        UniqueConstraint("dex_number", "name", name="uq_pokemon_form"),
    )

    #: 完整形态 slug（PokéAPI `/pokemon/{name}` 的 name，如 `rotom-wash`）
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: 归属的全国图鉴编号（与 `pokemon.dex_number` 对应）
    dex_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 形态前缀（PokéAPI form_name，如 `wash` / `mega-x` / `alola`），缺少时用名称去掉物种名后的部分
    suffix: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    #: 中文形态名（如「连击流」）；缺失时界面回落到英文
    zh: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: PokéAPI 的本地化英文形态名（如 `Wash Rotom`）
    name_en_label: Mapped[str | None] = mapped_column(String(96), nullable=True)

    types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    abilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    height_dm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_hg: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: 立绘 / 小图标（本地缓存优先，相对 media_dir）
    artwork_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artwork_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sprite_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sprite_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    #: 展示顺序（默认形态为 0，其余按上游 varieties 顺序）
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"PokemonForm(name={self.name!r}, dex={self.dex_number!r})"


class DoubleFormat(Base):
    """双打数据源（P2+ 双打辅助）：一个格式一行。

    数据来自 Smogon 公开的月度使用率统计（文本），经
    `scripts/fetch_doubles_stats.py` 抓取到 `data/doubles/{key}.json`，
    再由 `services/doubles_service.py` 导入本表。

    统计是**历史快照**：`month` / `cutoff` 必须随数据一起展示，
    否则旧月份的数据会被误读成当前环境。
    """

    __tablename__ = "doubles_format"

    key: Mapped[str] = mapped_column(String(16), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    short_label: Mapped[str] = mapped_column(String(16), nullable=False)
    game: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset: Mapped[str] = mapped_column(String(64), nullable=False)
    smogon_format: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 统计月份（YYYY-MM）
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    #: Smogon 等级线（表示「该分段及以上」的对战）
    cutoff: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 配点类型：ev（旧世代 0–252）/ stat_points（Champions 能力点 0–32）
    points_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="ev")
    #: 该格式的对战总数
    battles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 导出 Showdown 代码时的交易命令前缀（如 !tradeSV）；为空表示不添加
    trade_prefix: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: 导出代码的默认等级
    default_level: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"DoubleFormat(key={self.key!r}, month={self.month!r})"


class DoublePokemonStat(Base):
    """双打统计：一个格式里一只宝可梦的使用率与主流配置。

    名称是 Smogon / Showdown 的显示名（如 `Incineroar`、`Urshifu-Rapid-Strike`），
    与全国图鉴不是一一对应：形态、超级进化会归并到同一图鉴编号（见 `dex_number`）。
    JSON 列保存完整明细，页面只消费需要的那部分：

      - `abilities_json` / `items_json` / `moves_json` / `teammates_json`
        → `[[slug, pct], ...]`，已按百分比降序；
      - `spreads_json` → `[{"nature": "adamant", "points": [..6], "pct": 4.4}, ...]`；
      - `tera_types_json` → 仅朱紫有值。
    """

    __tablename__ = "doubles_pokemon_stat"
    __table_args__ = (
        UniqueConstraint("format_key", "showdown_name", name="uq_doubles_format_name"),
        Index("ix_doubles_dex_format", "dex_number", "format_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    format_key: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    showdown_name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 映射到的全国图鉴编号；无法映射时为 None（页面按名称直接展示）
    dex_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 使用率排名（来自 usage 表；没有配装明细的宝可梦也有排名）
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 使用率（百分比，0–100）
    usage: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: 该条目的样本数（Raw count）
    raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    abilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    moves_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    spreads_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    teammates_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tera_types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"DoublePokemonStat(format={self.format_key!r}, name={self.showdown_name!r})"


class AdminOpLog(Base):
    """后台操作日志（P2）：谁在什么时候对图鉴做了什么。

    MVP 不做账号体系，`operator` 目前固定为 "admin"（本地单人使用）。
    引入认证后该字段记录真实用户。
    """

    __tablename__ = "admin_op_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(64), nullable=False, default="admin")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"AdminOpLog(id={self.id!r}, action={self.action!r})"


class Team(Base):
    """双打队伍（P3+）：一个格式下最多 6 只宝可梦。

    队伍与成员的关系用 `team_member` 表 + `position`（0–5）表达槽位顺序：
      - 同一队伍内 `dex_number` 不重复（编号唯一）；
      - 同一队伍内非空 `item` 不重复（道具唯一）；
      - 合法性（招式 / 特性是否能在该版本学会）在 `team_service.validate_team` 里校验，
        不写死在数据库约束里 —— 规则随版本变化，约束住在服务层更容易演进。

    `owner_key` 是历史遗留列（早期按匿名身份隔离个人数据）。项目为个人自用，
    已取消浏览器隔离：查询不再按它过滤，新建队伍统一写占位值 `"local"`。
    列保留是为了兼容旧数据（旧队伍各自带着原来的 UUID，仍能正常列出）。
    将来接入登录时，这一列可直接改造成账号 id。
    """

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: 历史遗留的归属字段（不再参与过滤；见类文档）
    owner_key: Mapped[str] = mapped_column(String(64), nullable=False, default="local")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 双打格式 key（bdsp / swsh / sv / champions）
    format_key: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 用户在队伍列表里拖动的顺序（升序）。新队伍排到**最前面**（取当前最小值 − 1），
    #: 方便建完立刻在列表顶部看到；旧数据默认 0，按 id 兜底，列表不会乱。
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 最近一次队伍评价的完整快照（`schemas/teams.py:TeamAnalysis` 的 JSON）。
    #: 存快照而不是每次重新算：LLM 调用慢且结果不稳定，用户要能随时回看上次结论。
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 评价生成时间（用于「多久以前」的提示）。
    analysis_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: 生成评价时的成员指纹（`team_analysis_service.members_fingerprint`）。
    #: 与当前成员比对即可判断评价是否还对新配置有效 —— 比用 updated_at 准，
    #: 因为「只保存评价」也会改 updated_at。
    analysis_members_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Team(id={self.id!r}, name={self.name!r}, format={self.format_key!r})"


class TeamMember(Base):
    """队伍中的一个槽位（0–5）。

    每只宝可梦的完整配置存成 JSON：招式 / 特性 / 道具 / 性格 / EV / IV / 太晶属性。
    这样「加一只」是一次 insert，不必再为一堆字段建表；配置的字段集合由
    `schemas/teams.py` 的 `TeamMemberInput` 约束，避免脏数据。
    """

    __tablename__ = "team_member"
    __table_args__ = (
        UniqueConstraint("team_id", "position", name="uq_team_member_position"),
        Index("ix_team_member_team", "team_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 槽位序号 0–5（0 表示第一只）
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    dex_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Showdown 显示名（含形态，如 `Charizard-Mega-Y`）
    showdown_name: Mapped[str] = mapped_column(String(64), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(32), nullable=True)
    item: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nature: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: 六项 EV（HP/攻/防/特攻/特防/速）；Champions 用能力点，同样是 6 个数
    evs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[0,0,0,0,0,0]")
    ivs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    moves_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tera_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(2), nullable=True)
    shiny: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 极巨化等级 0–10（仅剑盾；10 为 Showdown 默认值，NULL 视为 10）。
    #: 极巨化后 HP 倍率随等级提高，因而作为一只宝可梦的配置保存。
    dynamax_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 超极巨化（仅剑盾）：True 时导出 `Gigantamax: Yes`。
    #: 只有带 G 形态的物种合法（清单见 `data/forms/showdown.json:gigantamax`）。
    gigantamax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Showdown 导出用的语言标记（CHS / CHT / ENG / JPN / KOR / FRA / GER / ITA / ESP）
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="CHS")

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"TeamMember(id={self.id!r}, dex={self.dex_number!r})"


# ---------------------------------------------------------------------------
# 出卷（P6）：一轮答题 + 每道题 + 错题集
# ---------------------------------------------------------------------------


class QuizSession(Base):
    """一轮出卷。

    `scope_json` 记录出卷时的筛选条件（世代 / 编号区间 / 数量 / 是否全量），
    便于结果页回显与「再考一次」；题库本身不存快照 —— 题目在 `quiz_question`
    里按图鉴编号引用，名称与图片始终取当前图鉴数据。
    """

    __tablename__ = "quiz_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: 卷面配置（JSON）：generation / dex_from / dex_to / count / mode
    scope_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    #: 题目总数
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 已作答数量（含答错）；等于 total 时视为完成
    answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"QuizSession(id={self.id!r}, total={self.total!r})"


class QuizQuestion(Base):
    """一道题：图鉴编号 + 顺序 + 作答结果。

    名称 / 图片不落库：它们属于图鉴数据，重复存会产生两份真相。
    """

    __tablename__ = "quiz_question"
    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_quiz_question_position"),
        Index("ix_quiz_question_session", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 卷内序号（0 起），决定答题顺序
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    dex_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 依次作答：NULL 表示还没答
    answer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"QuizQuestion(session={self.session_id!r}, dex={self.dex_number!r})"


class QuizMistake(Base):
    """错题集：按图鉴编号累计。

    答错自动 upsert（次数 +1、更新时间）；同一只反复答错只保留一行，
    这样错题集是「还需要复习的宝可梦」而不是一堆重复条目。
    答对不会自动移除 —— 是否已掌握应由用户自己判断，界面提供手动移除。
    """

    __tablename__ = "quiz_mistake"
    __table_args__ = (UniqueConstraint("dex_number", name="uq_quiz_mistake_dex"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dex_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    #: 累计答错次数
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: 最近一次答错的作答内容（原样保存，便于回看当时写成了什么）
    last_answer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_wrong_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_wrong_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"QuizMistake(dex={self.dex_number!r}, wrong={self.wrong_count!r})"


# ---------------------------------------------------------------------------
# Smogon 历史使用率（P7）：任意月份 × 格式 × 等级线的快照
# ---------------------------------------------------------------------------


class UsageSnapshot(Base):
    """一次「月份 × 格式 × 等级线」的统计快照。

    与 `DoubleFormat` 的区别：后者是「每格式一个固定快照」（详情页双打辅助用），
    这里是**全历史多快照**（使用率查询页用），两者数据源相同但不互相依赖 ——
    改动一边不会影响另一边的既有行为。

    `format_id` 是 Smogon 的格式 id（如 `gen9vgc2026regf`），`month` 是 YYYY-MM，
    `cutoff` 是等级线。三者共同唯一。
    """

    __tablename__ = "usage_snapshot"
    __table_args__ = (
        UniqueConstraint("format_id", "month", "cutoff", name="uq_usage_snapshot_key"),
        Index("ix_usage_snapshot_month", "month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Smogon 格式 id（URL 中的名字）
    format_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: 统计月份（YYYY-MM）
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    #: 等级线（0 表示全分段）
    cutoff: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 该快照的对战总数（usage 表头）
    battles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 数据源地址，便于核对
    source_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return (
            f"UsageSnapshot(format={self.format_id!r}, month={self.month!r}, "
            f"cutoff={self.cutoff!r})"
        )


class UsageSnapshotEntry(Base):
    """一个快照里的一只宝可梦：排名 + 使用率。

    只存使用率表（usage）里的字段；配装明细（招式 / 道具 / 配点）属于
    「当前环境」的深度分析，仍由 `DoubleFormat` / `DoublePokemonStat` 承载，
    这里不重复存 —— 全历史 × 全格式 × 三档等级线的明细体量过大。
    """

    __tablename__ = "usage_snapshot_entry"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "showdown_name", name="uq_usage_entry_name"),
        Index("ix_usage_entry_snapshot_rank", "snapshot_id", "rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Smogon / Showdown 显示名（如 `Urshifu-Rapid-Strike`）
    showdown_name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 映射到的全国图鉴编号；无法映射时为 None
    dex_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 使用率（百分比 0–100）
    usage: Mapped[float] = mapped_column(Float, nullable=False)
    #: 原始场次
    raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"UsageSnapshotEntry(snapshot={self.snapshot_id!r}, name={self.showdown_name!r})"


class UsageSyncRun(Base):
    """同步任务记录：谁在什么时候同步了哪些月份，结果如何。

    用于「同步按钮」展示进度与最近结果；也便于排查「某个月为什么没数据」。
    """

    __tablename__ = "usage_sync_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: running / done / error / cancelled
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    #: 同步范围（JSON）：{"months": [...], "formats": [...], "cutoffs": [...]}
    scope_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    #: 已处理的快照数 / 总快照数
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 新增 / 跳过（已存在）/ 失败
    created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 当前正在处理的项，如 `gen9vgc2026regf 2026-04 1630`
    current: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"UsageSyncRun(id={self.id!r}, status={self.status!r})"


# ---------------------------------------------------------------------------
# 官方赛事（P8）：赛事 → 名次 → 队伍 → 队员；以及赛事使用率
# ---------------------------------------------------------------------------


class Tournament(Base):
    """一场官方赛事（地区赛 / 国际赛 / 世锦赛 / 特殊赛事 / 国家赛 / Players Cup）。

    数据源是 Limitless VGC 的赛事页。与 Smogon 快照的区别：
      - Smogon 是**天梯**统计（按月、按等级线）；
      - 这里是**线下官方赛事**的实际参赛队伍（按赛事），使用率由队表重算。
    两者分开存，页面上分区展示，不互相覆盖。

    `source_id` 是 Limitless 的赛事 id（URL 里的数字），全局唯一；增量同步靠它判断
    哪些赛事已经抓过 —— 已抓过且已有队表的直接跳过。
    """

    __tablename__ = "tournament"
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_tournament_source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Limitless 的赛事 id（如 448）
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    #: 赛事日期（YYYY-MM-DD，来自列表页；详情页只有英文长日期）
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    #: Limitless 规则标识（m-c / svf / vgc17 …），展示名见 domain/tournament_catalog
    ruleset: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    #: 赛事类型：regional / international / worlds / special / national / players_cup
    event_type: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    #: 举办国家（两位代码）
    country: Mapped[str | None] = mapped_column(String(4), nullable=True)
    #: 参赛人数（列表页）
    players: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 冠军（名字与国家分开存）
    winner: Mapped[str | None] = mapped_column(String(96), nullable=True)
    winner_country: Mapped[str | None] = mapped_column(String(4), nullable=True)
    #: 可建队的格式 key（bdsp / swsh / sv / champions）；None 表示本地无法建队
    format_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: 成绩页的名次条目数（Top Cut 人数，来自成绩页）
    standings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 已抓取队表的队伍数
    team_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 是否有队表（没有队表的赛事只能看名次与使用率，不能一键建队）
    has_teamlists: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"Tournament(source={self.source_id!r}, name={self.name!r})"


class TournamentStanding(Base):
    """一场赛事的一个名次（成绩页的一行）。

    队伍预览（`species_json`）来自成绩页；完整配置在 `tournament_team`。
    早期赛事没有队表，只有这个预览，仍然可以展示「谁用了哪 6 只」。
    """

    __tablename__ = "tournament_standing"
    __table_args__ = (
        # 早期赛事存在并列名次（如两个第 4 名），因此名次 + 选手共同唯一
        UniqueConstraint("tournament_id", "rank", "player", name="uq_tournament_standing_rank"),
        Index("ix_tournament_standing_tournament", "tournament_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    player: Mapped[str] = mapped_column(String(96), nullable=False)
    country: Mapped[str | None] = mapped_column(String(4), nullable=True)
    #: 队伍预览：Showdown 显示名列表（`["Garchomp", …]`），可能为空
    species_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    #: Limitless 的队伍页 id（`/teams/{id}`）；None 表示该选手没有公开队表
    source_team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"TournamentStanding(rank={self.rank!r}, player={self.player!r})"


class TournamentTeam(Base):
    """一位选手在一场赛事里的完整队表（6 只）。

    `source_team_id` 对应 Limitless 的 `/teams/{id}`，用于去重与增量更新。
    `showdown_text` 是**已补齐默认值**的 Showdown 文本（含等级 / 语言标记），
    前端「复制」与「一键建队」都直接用它，保证同一份数据两个入口一致。
    """

    __tablename__ = "tournament_team"
    __table_args__ = (
        UniqueConstraint("tournament_id", "rank", "player", name="uq_tournament_team_rank"),
        Index("ix_tournament_team_tournament", "tournament_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 名次（与成绩页一致；没有名次时为 0）
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    player: Mapped[str] = mapped_column(String(96), nullable=False)
    country: Mapped[str | None] = mapped_column(String(4), nullable=True)
    #: Limitless 队伍页 id（`/teams/{id}`）
    source_team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 完整 Showdown 文本（可直接复制 / 导入建队页）
    showdown_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: 配置里无法映射到图鉴的条目（JSON 列表，展示用）
    problems_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    #: 本地规则校验结果（JSON）：`{"ok": bool, "issues": [...]}`。
    #: 源站笔误（如把 Glimmora 写成 Rough Skin）如实记录，页面提示但**不阻断**建队。
    validation_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"TournamentTeam(rank={self.rank!r}, player={self.player!r})"


class TournamentTeamMember(Base):
    """队表里的一只宝可梦：结构化字段 + Showdown 显示名。

    与 `team_member` 的区别：这里是**只读的赛事记录**，EV / IV 未公开（NULL），
    等级按赛事规则推断；建队时复制成 `team` 的成员，两者互不影响。
    """

    __tablename__ = "tournament_team_member"
    __table_args__ = (
        UniqueConstraint("team_id", "position", name="uq_tournament_team_member_position"),
        Index("ix_tournament_team_member_team", "team_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 槽位 0–5（按队表顺序）
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 图鉴编号；无法映射时为 NULL（仍保留原始名字，展示时如实标注）
    dex_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Limitless 的物种 slug（如 `urshifu-rapid-strike`）
    species_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Showdown 显示名（如 `Urshifu-Rapid-Strike`）
    #: 超极巨化不写进名字：G 形态统一折算成基础形态 + `gigantamax` 标记。
    showdown_name: Mapped[str] = mapped_column(String(64), nullable=False)
    item: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nature: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tera_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: 超极巨化（剑盾）：赛事队表里的 `-Gmax` 别名在同步时折算成这个标记，
    #: 导出代码写 `Gigantamax: Yes`（与建队页 / Showdown 同一套写法）。
    gigantamax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: 极巨化等级 0–10（赛事未公开，按 Showdown 默认值 10 记录）
    dynamax_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moves_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"TournamentTeamMember(team={self.team_id!r}, slug={self.species_slug!r})"


class TournamentUsage(Base):
    """赛事使用率（由该赛事全部队表重算，不是 Top Cut 统计）。

    分母是「有队表的队伍数」；`share` 是百分比（一只 / 队 计一次）。
    与 Smogon 的口径一致（每队 6 只），所以最高不超过 100%。
    """

    __tablename__ = "tournament_usage"
    __table_args__ = (
        UniqueConstraint("tournament_id", "species_slug", name="uq_tournament_usage_species"),
        Index("ix_tournament_usage_tournament", "tournament_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Limitless 物种 slug（与队表一致）
    species_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 映射到的图鉴编号（用于显示中文名与图标）；无法映射时为 NULL
    dex_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    showdown_name: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 出现队伍数
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 使用率（百分比）
    share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"TournamentUsage(slug={self.species_slug!r}, share={self.share!r})"


class TournamentSyncRun(Base):
    """赛事同步任务：与 `usage_sync_run` 同样的进度记录方式。"""

    __tablename__ = "tournament_sync_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    #: 同步范围（JSON）：{"types": [...], "year_min": 2024, "with_teams": true}
    scope_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 当前正在处理的项（如 `Regional Gdańsk（445）`）
    current: Mapped[str | None] = mapped_column(String(160), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"TournamentSyncRun(id={self.id!r}, status={self.status!r})"


class PokemonFormMove(Base):
    """形态的招式学习表（从 PokéAPI `/pokemon/{form}` 同步，**派生表**）。

    为什么需要单独一张表：`pokemon.moves_json` 是默认形态的招式表，形态专属招式
    （如水熊连击流的「水流连打」、厄诡椪面具形态的「棘藤棒」）只出现在形态的
    `/pokemon/{name}` 响应里。队伍合法性校验按图鉴编号合并两者，否则官方赛事里的
    合法配置会被误判成非法。

    `methods_json` 的结构与主表相同：`{学习方式: [{name, level}, …]}`，但只保留
    与当前存档相关的版本组（`version_groups_json` 记录是哪些）。
    """

    __tablename__ = "pokemon_form_move"
    __table_args__ = (
        UniqueConstraint("form_name", "version_group", name="uq_form_move_version"),
        Index("ix_form_move_dex", "dex_number"),
        Index("ix_form_move_version", "version_group"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: 形态主键（`pokemon_form.name`）
    form_name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 归属的全国图鉴编号（与默认形态合并校验用）
    dex_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 版本组（如 `scarlet-violet` / `sword-shield`）
    version_group: Mapped[str] = mapped_column(String(48), nullable=False)
    #: 该版本组的招式明细：`{method: [{name, level}, …]}`
    methods_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"PokemonFormMove(form={self.form_name!r}, vg={self.version_group!r})"
