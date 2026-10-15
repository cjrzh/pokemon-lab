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

    #: PokéAPI：公开 REST 接口，无需密钥
    pokeapi_base_url: str = "https://pokeapi.co/api/v2"
    pokeapi_connect_timeout_seconds: float = 5.0
    pokeapi_read_timeout_seconds: float = 10.0
    pokeapi_max_retries: int = 2
    pokeapi_cache_ttl_seconds: int = 7 * 24 * 60 * 60

    @field_validator("var_dir", "data_dir", mode="after")
    @classmethod
    def _expand_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def database_path(self) -> Path:
        return self.var_dir / "pokemon_lab.db"

    @property
    def database_url(self) -> str:
        """SQLite 绝对路径的 SQLAlchemy 连接串（Windows 盘符同样适用）。"""
        return f"sqlite+aiosqlite:///{self.database_path.as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例。测试中通过 `get_settings.cache_clear()` 切换到临时配置。"""
    return Settings()
