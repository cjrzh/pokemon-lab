"""应用配置。

所有可调参数集中在这里，可通过 `POKEMON_LAB_*` 环境变量覆盖，
也可写在 `services/api/.env`（该文件不入库）。

不把配置散落到各模块，是为了让「数据目录在哪」「数据库在哪」「外部接口超时多少」
这类问题只有一个答案。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: services/api/
API_DIR = Path(__file__).resolve().parents[2]
#: 仓库根目录 pokemon-lab/
REPO_ROOT = API_DIR.parents[1]
#: 跨前后端共享的规范数据目录
DEFAULT_DATA_DIR = REPO_ROOT / "data"
#: 运行期产物目录（SQLite 文件、PokéAPI 缓存），已被 .gitignore 忽略
DEFAULT_VAR_DIR = API_DIR / "var"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POKEMON_LAB_",
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "pokemon-lab-api"
    version: str = "0.1.0"
    environment: str = "development"

    #: 产品 API 前缀，健康检查等接口都挂在其下
    api_prefix: str = "/api/v1"

    #: 允许的前端来源。开发态前端走 Vite 同源代理，这里是给「直连后端」与「预览构建」兜底。
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    #: 运行期产物目录（不入库）
    var_dir: Path = DEFAULT_VAR_DIR
    #: 规范数据目录（仓库内共享，入库）
    data_dir: Path = DEFAULT_DATA_DIR
    #: 本地图片缓存目录。默认跟随 var_dir（测试切到临时目录时自动隔离）；
    #: 需要单独指定时设 POKEMON_LAB_MEDIA_DIR。
    media_dir: Path | None = None

    #: PokéAPI：公开 REST 接口，无需密钥
    pokeapi_base_url: str = "https://pokeapi.co/api/v2"
    pokeapi_connect_timeout_seconds: float = 5.0
    pokeapi_read_timeout_seconds: float = 10.0
    pokeapi_max_retries: int = 2
    pokeapi_cache_ttl_seconds: int = 7 * 24 * 60 * 60

    #: 官方图鉴立绘（pokemon.com 公开图鉴资源）同步到本地，离线可用
    artwork_base_url: str = "https://assets.pokemon.com/assets/cms2/img/pokedex/full"
    artwork_fetch_timeout_seconds: float = 20.0
    #: 是否在同步时下载立绘。测试默认关闭，避免打真实网络。
    artwork_sync_enabled: bool = True

    #: ---------- LLM（队伍评价，OpenAI 兼容接口） ----------
    #: 这几个变量沿用 `TELECOM_` 前缀（与 .env 里的既有写法一致），
    #: 因此用 validation_alias 显式读取，而不是套 POKEMON_LAB_ 前缀。
    llm_base_url: str | None = Field(
        default=None, validation_alias="TELECOM_BASE_URL"
    )
    llm_api_key: str | None = Field(
        default=None, validation_alias="TELECOM_API_KEY", repr=False
    )
    llm_model: str = Field(
        default="deepseek-v4.1-flash-new", validation_alias="TELECOM_FLASH_MODEL"
    )
    #: 备用模型：主模型失败（超时 / 5xx）时重试一次，仍失败则降级为「无 AI 建议」。
    llm_fallback_model: str | None = Field(
        default=None, validation_alias="TELECOM_MAX_MODEL"
    )
    llm_enable_thinking: bool = Field(
        default=False, validation_alias="TELECOM_ENABLE_THINKING"
    )
    llm_temperature: float = Field(default=0.5, validation_alias="TELECOM_TEMPERATURE")
    llm_top_p: float = Field(default=0.8, validation_alias="TELECOM_TOP_P")
    llm_max_tokens: int = Field(default=800, validation_alias="TELECOM_MAX_TOKENS")
    llm_timeout_seconds: float = 45.0

    @property
    def llm_configured(self) -> bool:
        """有 base_url 与 key 才认为配置可用；否则接口降级为「只给计算结果」。"""
        return bool(self.llm_base_url and self.llm_api_key)

    @field_validator("var_dir", "data_dir", mode="after")
    @classmethod
    def _expand_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def database_path(self) -> Path:
        return self.var_dir / "pokemon_lab.db"

    @property
    def resolved_media_dir(self) -> Path:
        """实际生效的图片目录。未显式配置时跟随 var_dir，避免漏配后写到仓库根。"""
        path = self.media_dir or (self.var_dir / "media")
        return path.expanduser().resolve()

    @property
    def artwork_dir(self) -> Path:
        """立绘缓存目录：media/artwork/{dex}.png。"""
        return self.resolved_media_dir / "artwork"

    @property
    def sprite_dir(self) -> Path:
        """小图标缓存目录：media/sprites/{dex}.png。"""
        return self.resolved_media_dir / "sprites"

    @property
    def item_icon_dir(self) -> Path:
        """道具图标缓存目录：media/items/{slug}.png（30×30）。"""
        return self.resolved_media_dir / "items"

    @property
    def database_url(self) -> str:
        """SQLite 绝对路径的 SQLAlchemy 连接串（Windows 盘符同样适用）。"""
        return f"sqlite+aiosqlite:///{self.database_path.as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例。测试中通过 `get_settings.cache_clear()` 切换到临时配置。"""
    return Settings()
