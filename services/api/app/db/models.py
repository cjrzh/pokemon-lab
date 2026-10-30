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
SCHEMA_VERSION = "0011_p2_items"


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
    cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 本地图标（相对 media_dir，如 items/sitrus-berry.png）；指纹文件时为空
    icon_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: 上游图标地址（PokéAPI sprites 仓库）；前端兜底用
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


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
