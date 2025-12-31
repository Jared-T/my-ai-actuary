"""
Configuration management using pydantic-settings.

Environment variables are loaded from .env file and validated at startup.
All configuration is centralized here for consistency and type safety.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILES = [BASE_DIR / ".env", BASE_DIR / "backend" / ".env"]


class Settings(BaseSettings):
    """Application settings with validation and environment variable loading."""

    model_config = SettingsConfigDict(
        env_file=[str(path) for path in ENV_FILES],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    app_name: str = Field(default="My AI Actuary", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # Server Settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    workers: int = Field(default=1, ge=1, description="Number of worker processes")

    # CORS Settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")

    # Supabase Settings
    supabase_url: str = Field(
        default="",
        description="Supabase project URL",
    )
    supabase_anon_key: SecretStr = Field(
        default=SecretStr(""),
        description="Supabase anonymous/public key",
    )
    supabase_service_role_key: SecretStr = Field(
        default=SecretStr(""),
        description="Supabase service role key for admin operations",
    )

    # OpenAI Settings
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API key for Agents SDK",
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="Default OpenAI model for agents",
    )

    # Logging Settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "console"] = Field(
        default="console",
        description="Logging output format",
    )

    # Rate Limiting
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Maximum requests per rate limit window",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Rate limit window in seconds",
    )

    # Backup Settings
    backup_dir: str = Field(
        default="/tmp/claude/backups",
        description="Directory for storing backup files",
    )
    backup_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Default number of days to retain backups",
    )
    backup_max_file_size_mb: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum backup file size in megabytes",
    )
    backup_auto_cleanup: bool = Field(
        default=True,
        description="Automatically cleanup expired backups",
    )
    backup_compression_enabled: bool = Field(
        default=False,
        description="Enable compression for backup files",
    )

    # CLI Task Settings (Codex CLI Integration)
    cli_task_output_dir: str = Field(
        default="/tmp/claude/cli_outputs",
        description="Directory for storing CLI task output files",
    )
    cli_task_default_timeout: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default timeout for CLI tasks in seconds (1 hour default, max 24 hours)",
    )
    cli_task_max_concurrent: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of concurrent CLI tasks",
    )
    cli_task_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Default maximum retry attempts for failed tasks",
    )
    cli_task_cleanup_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Number of days to retain completed task records",
    )
    codex_cli_path: str = Field(
        default="",
        description="Path to Codex CLI executable (empty for system PATH)",
    )
    codex_cli_config_path: str = Field(
        default="",
        description="Path to Codex CLI configuration file",
    )

    # Database Settings
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/my_ai_actuary",
        description="PostgreSQL database URL for async connections",
    )
    database_url_sync: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/my_ai_actuary",
        description="PostgreSQL database URL for sync connections (migrations)",
    )
    database_echo: bool = Field(
        default=False,
        description="Echo SQL statements for debugging",
    )
    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Database connection pool size",
    )
    database_pool_overflow: int = Field(
        default=10,
        ge=0,
        le=20,
        description="Maximum overflow connections beyond pool_size",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are loaded once and reused.
    """
    return Settings()


# Global settings instance for convenient import
settings = get_settings()
