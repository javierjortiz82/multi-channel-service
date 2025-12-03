"""Main entry point for the Telegram bot application."""

import uvicorn

from telegram_bot.config.settings import get_settings
from telegram_bot.logging_config import get_logger, setup_logging

logger = get_logger("main")


def main() -> None:
    """Run the Telegram bot webhook server.

    Supports multiple workers for handling concurrent users.
    In production (workers > 1), uses factory pattern for proper process isolation.
    In development (workers = 1), can use direct app instance.
    """
    settings = get_settings()
    setup_logging(settings.log_level, settings=settings)

    logger.info(
        "Starting Telegram Bot Webhook Server | env=%s | host=%s | port=%d | workers=%d",
        settings.environment,
        settings.server_host,
        settings.server_port,
        settings.workers,
    )
    logger.info(
        "Concurrency | limit=%d | max_requests=%d | backlog=%d",
        settings.limit_concurrency,
        settings.limit_max_requests,
        settings.backlog,
    )
    logger.info(
        "Timeouts | keep_alive=%ds | graceful_shutdown=%s",
        settings.timeout_keep_alive,
        (
            f"{settings.timeout_graceful_shutdown}s"
            if settings.timeout_graceful_shutdown
            else "None"
        ),
    )
    logger.info(
        "Performance | http=%s | loop=%s",
        settings.http_implementation,
        settings.loop_implementation,
    )

    # Use factory pattern for multi-worker support
    # Each worker process creates its own app instance
    uvicorn.run(
        "telegram_bot.app:create_app",
        factory=True,
        host=settings.server_host,
        port=settings.server_port,
        workers=settings.workers,
        # Concurrency limits
        limit_concurrency=settings.limit_concurrency,
        limit_max_requests=(
            settings.limit_max_requests if settings.limit_max_requests > 0 else None
        ),
        backlog=settings.backlog,
        # Timeouts
        timeout_keep_alive=settings.timeout_keep_alive,
        timeout_graceful_shutdown=settings.timeout_graceful_shutdown,
        # Performance
        http=settings.http_implementation,
        loop=settings.loop_implementation,
        # Logging
        log_level=settings.log_level.lower(),
        access_log=settings.environment != "production",
    )


if __name__ == "__main__":
    main()
