"""Configuration loader for PrivateSearch."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field
except ImportError:  # pragma: no cover - fallback when pydantic-settings is missing
    from pydantic import BaseModel, Field

    class BaseSettings(BaseModel):  # type: ignore[no-redef]
        """Minimal fallback that reads from environment variables."""

        model_config: Any = None

        def __init__(self, **data: Any) -> None:
            for key in self.__class__.model_fields:  # type: ignore[attr-defined]
                env_name = key.upper()
                if env_name in os.environ:
                    data[key] = os.environ[env_name]
            super().__init__(**data)

    class SettingsConfigDict(dict):  # type: ignore[no-redef]
        """Placeholder type alias."""

    def _default_settings_config(**kwargs: Any) -> Any:
        return None

    SettingsConfigDict = _default_settings_config  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for PrivateSearch services.

    All values can be overridden via environment variables. The defaults are
    chosen so that the application boots in a local development environment
    without requiring any setup.
    """

    model_config = SettingsConfigDict(  # type: ignore[call-arg]
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "PrivateSearch"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    secret_key: str = Field(default="dev-secret-change-in-production")

    database_url: str = Field(
        default=f"sqlite:///{(PROJECT_ROOT / 'data' / 'privatesearch.sqlite').as_posix()}"
    )

    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    index_storage_path: Path = Field(default=PROJECT_ROOT / "data" / "index")
    snapshot_dir: Path = Field(default=PROJECT_ROOT / "data" / "snapshots")

    bm25_k1: float = Field(default=1.2)
    bm25_b: float = Field(default=0.75)

    crawler_user_agent: str = Field(
        default="PrivateSearch/0.1 (+https://github.com/privatesearch/privatesearch)"
    )
    crawler_allowed_domains: list[str] = Field(default_factory=list)
    crawler_max_depth: int = Field(default=2)
    crawler_max_pages: int = Field(default=100)
    crawler_delay_seconds: float = Field(default=1.0)
    crawler_timeout_seconds: float = Field(default=20.0)
    crawler_max_response_bytes: int = Field(default=5 * 1024 * 1024)
    crawler_concurrency: int = Field(default=4)

    api_max_query_length: int = Field(default=256)
    api_max_page_size: int = Field(default=50)
    api_default_page_size: int = Field(default=10)
    api_rate_limit_per_minute: int = Field(default=120)

    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_dim: int = Field(default=384)
    enable_semantic_search: bool = Field(default=False)

    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""

    return Settings()