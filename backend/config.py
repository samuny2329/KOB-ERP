"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level config. All env vars use the KOB_ prefix."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="KOB_",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "kob"
    db_password: str = "kob_dev_password_change_me"
    db_name: str = "kob_erp"

    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    redis_url: str = "redis://localhost:6379/0"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Sync SQLAlchemy DSN (psycopg3 driver)."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                path=self.db_name,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_async(self) -> str:
        """Async SQLAlchemy DSN (asyncpg driver) for async sessions."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                path=self.db_name,
            )
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — call this everywhere instead of instantiating."""
    return Settings()  # type: ignore[call-arg]
