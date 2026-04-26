"""Runtime configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BOT_",
        extra="ignore",
    )

    gitlab_token: str = Field(default="", description="GitLab API token")
    admin_token: str = Field(default="", description="Admin API token for /courses")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL", alias="REDIS_URL")
    manytask_base_url: str = Field(
        default="http://localhost:8080",
        description="Base URL of the manytask service",
        alias="MANYTASK_BASE_URL",
    )
    poll_interval_sec: float = Field(
        default=10.0,
        description="Worker poll interval in seconds",
        alias="POLL_INTERVAL_SEC",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
