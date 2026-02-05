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

import ipaddress
import re
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
    timeout_graceful_shutdown: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Seconds to wait for graceful shutdown",
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

    # Internal Service URLs (Cloud Run)
    nlp_service_url: str = Field(
        default="https://nlp-service-4k3haexkga-uc.a.run.app",
        description="URL of NLP service for Gemini processing",
    )
    asr_service_url: str = Field(
        default="https://asr-service-4k3haexkga-uc.a.run.app",
        description="URL of ASR service for audio transcription",
    )
    ocr_service_url: str = Field(
        default="https://ocr-service-4k3haexkga-uc.a.run.app",
        description="URL of OCR service for image analysis",
    )

    @field_validator("webhook_path")
    @classmethod
    def validate_webhook_path(cls, v: str) -> str:
        """Validate and normalize the webhook path.

        Ensures the webhook path starts with '/' and contains only valid characters.

        Args:
            v: The webhook path value to validate.

        Returns:
            The normalized webhook path.

        Raises:
            ValueError: If the webhook path is invalid.
        """
        if not v:
            raise ValueError("webhook_path cannot be empty")
        if not v.startswith("/"):
            raise ValueError("webhook_path must start with '/'")
        # Check for valid URL path characters
        if not re.match(r"^/[a-zA-Z0-9_\-/]*$", v):
            raise ValueError(
                "webhook_path must contain only alphanumeric characters, "
                "underscores, hyphens, and forward slashes"
            )
        # Remove double slashes
        while "//" in v:
            v = v.replace("//", "/")
        return v

    @field_validator("webhook_host")
    @classmethod
    def validate_webhook_host(cls, v: str) -> str:
        """Validate and normalize the webhook host URL.

        Ensures the webhook host starts with http:// or https://,
        contains a valid hostname, and removes any trailing slashes.

        Args:
            v: The webhook host value to validate.

        Returns:
            The normalized webhook host without trailing slash.

        Raises:
            ValueError: If the webhook host is invalid.

        Example:
            Valid inputs::

                "https://example.com" -> "https://example.com"
                "https://example.com/" -> "https://example.com"
        """
        if not v.startswith(("http://", "https://")):
            raise ValueError("webhook_host must start with http:// or https://")

        # Extract hostname part and validate it exists
        v = v.rstrip("/")
        protocol_end = v.find("://") + 3
        host_part = v[protocol_end:]

        if not host_part:
            raise ValueError("webhook_host must include a hostname after the protocol")

        # Basic hostname validation (must have at least one character)
        hostname = host_part.split(":")[0].split("/")[0]
        if not hostname or hostname == "":
            raise ValueError("webhook_host must include a valid hostname")

        return v

    @field_validator("server_host")
    @classmethod
    def validate_server_host(cls, v: str) -> str:
        """Validate the server host.

        Ensures the server host is a valid IP address or hostname.

        Args:
            v: The server host value to validate.

        Returns:
            The validated server host.

        Raises:
            ValueError: If the server host is invalid.
        """
        if not v:
            raise ValueError("server_host cannot be empty")

        # Check if it's a valid IP address
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            pass

        # Check if it's a valid hostname
        hostname_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
        if not re.match(hostname_pattern, v):
            raise ValueError(f"server_host '{v}' is not a valid IP address or hostname")

        return v

    @field_validator("log_dir")
    @classmethod
    def validate_log_dir(cls, v: str) -> str:
        """Validate the log directory path.

        Ensures the log directory path is valid and doesn't contain
        null characters or other invalid path components.

        Args:
            v: The log directory path to validate.

        Returns:
            The validated log directory path.

        Raises:
            ValueError: If the log directory path is invalid.
        """
        if not v:
            raise ValueError("log_dir cannot be empty")

        # Check for null characters (security issue)
        if "\x00" in v:
            raise ValueError("log_dir cannot contain null characters")

        # Check for overly long paths
        if len(v) > 4096:
            raise ValueError("log_dir path is too long (max 4096 characters)")

        return v

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
