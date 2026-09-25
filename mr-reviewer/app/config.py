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
        populate_by_name=True,
    )

    gitlab_token: str = Field(default="", description="GitLab API token")
    admin_token: str = Field(default="", description="Admin API token for /courses")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL", alias="REDIS_URL")
    manytask_base_url: str = Field(
        default="http://localhost:8080",
        description="Base URL of the manytask service",
        alias="MANYTASK_BASE_URL",
    )
    manytask_request_timeout_sec: float = Field(
        default=5.0,
        description="Per-request timeout for manytask HTTP calls",
        alias="MANYTASK_REQUEST_TIMEOUT_SEC",
    )
    ping_cache_ttl_sec: int = Field(
        default=30,
        description="TTL for cached successful ping validations",
        alias="PING_CACHE_TTL_SEC",
    )
    poll_interval_sec: float = Field(
        default=900.0,
        description="Worker poll interval in seconds",
        alias="POLL_INTERVAL_SEC",
    )
    per_mr_timeout_sec: float = Field(
        default=120.0,
        description="Hard per-MR processing timeout inside the poll cycle",
        alias="PER_MR_TIMEOUT_SEC",
    )
    gitlab_base_url: str = Field(
        default="https://gitlab.com",
        description="GitLab API base URL (no trailing slash)",
        alias="GITLAB_BASE_URL",
    )
    hosting_executor_workers: int = Field(
        default=32,
        description="Thread pool size for sync hosting client calls",
        alias="HOSTING_EXECUTOR_WORKERS",
    )
    bot_username: str = Field(
        default="manytask-mr-reviewer-bot",
        description="GitLab username under which the bot posts comments",
        alias="BOT_USERNAME",
    )
    bot_label_processed: str = Field(
        default="checklist",
        description="Label set when the bot has processed the MR (always)",
        alias="BOT_LABEL_PROCESSED",
    )
    bot_label_fail: str = Field(
        default="fix it",
        description="Label set when at least one checklist step failed",
        alias="BOT_LABEL_FAIL",
    )
    run_step_timeout_sec: float = Field(
        default=60.0,
        description="Hard timeout for the run: checklist step",
        alias="RUN_STEP_TIMEOUT_SEC",
    )
    log_level: str = Field(
        default="INFO",
        description="Default loguru level for all modules",
        alias="LOG_LEVEL",
    )
    log_json: bool = Field(
        default=True,
        description="Emit logs as JSON on stdout (disable for human-readable local dev)",
        alias="LOG_JSON",
    )
    log_module_levels: str = Field(
        default="",
        description="Per-module level overrides, e.g. 'app.worker=DEBUG,app.manytask=WARNING'",
        alias="LOG_MODULE_LEVELS",
    )
    healthz_poll_stale_sec: float = Field(
        default=1800.0,
        description="Age of the last completed poll cycle above which /healthz returns 503",
        alias="HEALTHZ_POLL_STALE_SEC",
    )
    manytask_retry_attempts: int = Field(
        default=3,
        description="Total attempts (1 = no retry) for transient manytask failures",
        alias="MANYTASK_RETRY_ATTEMPTS",
    )
    manytask_retry_backoff_sec: float = Field(
        default=0.5,
        description="Exponential backoff multiplier for manytask retries",
        alias="MANYTASK_RETRY_BACKOFF_SEC",
    )
    manytask_retry_max_backoff_sec: float = Field(
        default=5.0,
        description="Cap on a single manytask retry wait",
        alias="MANYTASK_RETRY_MAX_BACKOFF_SEC",
    )
    gitlab_retry_attempts: int = Field(
        default=3,
        description="Total attempts (1 = no retry) for transient GitLab failures",
        alias="GITLAB_RETRY_ATTEMPTS",
    )
    gitlab_retry_backoff_sec: float = Field(
        default=0.5,
        description="Exponential backoff multiplier for GitLab retries",
        alias="GITLAB_RETRY_BACKOFF_SEC",
    )
    gitlab_retry_max_backoff_sec: float = Field(
        default=10.0,
        description="Cap on a single GitLab retry wait",
        alias="GITLAB_RETRY_MAX_BACKOFF_SEC",
    )
    gitlab_rate_limit_threshold: float = Field(
        default=0.1,
        description="Sleep when RateLimit-Remaining / RateLimit-Limit falls below this fraction",
        alias="GITLAB_RATE_LIMIT_THRESHOLD",
    )
    gitlab_rate_limit_max_sleep_sec: float = Field(
        default=60.0,
        description="Cap on a single rate-limit sleep",
        alias="GITLAB_RATE_LIMIT_MAX_SLEEP_SEC",
    )
    gitlab_rate_limit_fallback_sleep_sec: float = Field(
        default=5.0,
        description="Sleep used when RateLimit-Reset header is missing",
        alias="GITLAB_RATE_LIMIT_FALLBACK_SLEEP_SEC",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
