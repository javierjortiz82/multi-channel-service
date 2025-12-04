"""Application settings using Pydantic v2.

This module provides centralized configuration management for the Telegram Bot
webhook service using Pydantic v2 settings with environment variable support.

Example:
    Basic usage::

        from telegram_bot.config.settings import get_settings

        settings = get_settings()
        print(settings.webhook_url)

Attributes:
    Settings: Main settings class with all configuration options.
    get_settings: Factory function to get cached settings instance.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation.

    This class manages all configuration for the Telegram Bot webhook service,
    including Telegram API credentials, webhook configuration, server settings,
    concurrency limits, timeouts, and logging options.

    All settings can be configured via environment variables or a .env file.

    Attributes:
        telegram_bot_token: Bot API token from @BotFather.
        webhook_host: Public hostname for webhook (must be HTTPS in production).
        webhook_path: Path for the webhook endpoint.
        webhook_secret: Secret token for webhook verification.
        webhook_max_connections: Max simultaneous HTTPS connections (1-100).
        webhook_ip_filter_enabled: Enable IP filtering for Telegram servers only.
        webhook_drop_pending_updates: Drop pending updates on webhook setup.
        server_host: Host to bind the server.
        server_port: Port to bind the server.
        environment: Application environment (development/staging/production).
        log_level: Logging level.
        debug: Enable debug mode.
        workers: Number of uvicorn workers.
        limit_concurrency: Max concurrent connections per worker.
        limit_max_requests: Max requests per worker before restart.
        backlog: Max connections in backlog queue.
        timeout_keep_alive: Seconds to keep idle connections open.
        timeout_graceful_shutdown: Seconds to wait for graceful shutdown.
        http_implementation: HTTP protocol implementation.
        loop_implementation: Event loop implementation.
        log_to_file: Whether to write logs to file.
        log_dir: Directory for log files.
        log_max_size_mb: Max log file size before rotation.
        log_backup_count: Number of backup log files to keep.

    Example:
        Create settings from environment::

            settings = Settings()
            print(f"Server running on {settings.server_host}:{settings.server_port}")
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot Configuration
    telegram_bot_token: SecretStr = Field(
        ...,
        description="Telegram Bot API token from @BotFather",
    )

    # Webhook Configuration
    webhook_host: str = Field(
        ...,
        description="Public hostname for webhook (e.g., https://example.com)",
    )
    webhook_path: str = Field(
        default="/webhook",
        description="Path for the webhook endpoint",
    )
    webhook_secret: SecretStr = Field(
        ...,
        description="Secret token for webhook verification",
    )
    webhook_max_connections: int = Field(
        default=100,
        ge=1,
        le=100,
        description="Max simultaneous HTTPS connections for update delivery (1-100)",
    )
    webhook_ip_filter_enabled: bool = Field(
        default=True,
        description="Enable IP filtering to allow only Telegram servers",
    )
    webhook_drop_pending_updates: bool = Field(
        default=True,
        description="Drop pending updates on webhook setup",
    )

    # Server Configuration
    server_host: str = Field(
        default="0.0.0.0",
        description="Host to bind the server",
    )
    server_port: int = Field(
        default=8002,
        ge=1,
        le=65535,
        description="Port to bind the server",
    )

    # Application Configuration
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    # Concurrency Configuration
    workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of uvicorn workers for concurrency",
    )
    limit_concurrency: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum concurrent connections per worker",
    )
    limit_max_requests: int = Field(
        default=10000,
        ge=0,
        description="Maximum requests per worker before restart (0=unlimited)",
    )
    backlog: int = Field(
        default=2048,
        ge=1,
        le=65535,
        description="Maximum connections in backlog queue",
    )

    # Timeout Configuration
    timeout_keep_alive: int = Field(
        default=5,
        ge=1,
        le=300,
        description="Seconds to keep idle connections open (keep-alive timeout)",
    )
    timeout_graceful_shutdown: int | None = Field(
        default=30,
        ge=1,
        le=300,
        description="Seconds to wait for graceful shutdown (None=wait forever)",
    )

    # Performance Configuration
    http_implementation: Literal["auto", "h11", "httptools"] = Field(
        default="auto",
        description="HTTP protocol implementation (httptools is faster)",
    )
    loop_implementation: Literal["auto", "asyncio", "uvloop"] = Field(
        default="auto",
        description="Event loop implementation (uvloop is faster on Linux)",
    )

    # Logging Configuration
    log_to_file: bool = Field(
        default=True,
        description="Whether to write logs to file",
    )
    log_dir: str = Field(
        default="./logs",
        description="Directory for log files",
    )
    log_max_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum log file size in megabytes before rotation",
    )
    log_backup_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of backup log files to keep",
    )

    # Webhook Retry Configuration
    webhook_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retries for webhook setup on flood control",
    )
    webhook_retry_buffer_seconds: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Buffer time in seconds added to Telegram's retry_after",
    )

    # Rate Limiting Configuration
    rate_limit_requests: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Maximum requests per IP per rate limit window",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Rate limit window in seconds",
    )

    @field_validator("webhook_host")
    @classmethod
    def validate_webhook_host(cls, v: str) -> str:
        """Validate and normalize the webhook host URL.

        Ensures the webhook host starts with http:// or https:// and
        removes any trailing slashes for consistent URL construction.

        Args:
            v: The webhook host value to validate.

        Returns:
            The normalized webhook host without trailing slash.

        Raises:
            ValueError: If the webhook host doesn't start with http:// or https://.

        Example:
            Valid inputs::

                "https://example.com" -> "https://example.com"
                "https://example.com/" -> "https://example.com"
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError("webhook_host must start with http:// or https://")
        return v.rstrip("/")

    @property
    def webhook_url(self) -> str:
        """Get the full webhook URL.

        Combines webhook_host and webhook_path into a complete URL.

        Returns:
            The complete webhook URL (e.g., "https://example.com/webhook").

        Example:
            Get webhook URL::

                settings = Settings(
                    webhook_host="https://example.com",
                    webhook_path="/webhook"
                )
                print(settings.webhook_url)  # https://example.com/webhook
        """
        return f"{self.webhook_host}{self.webhook_path}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses LRU cache to ensure a single settings instance is created
    and reused throughout the application lifecycle.

    Returns:
        Cached Settings instance loaded from environment.

    Example:
        Get settings in application code::

            from telegram_bot.config.settings import get_settings

            settings = get_settings()
            print(settings.server_port)
    """
    return Settings()
