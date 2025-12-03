"""Main entry point for the Telegram bot application.

This module provides the main entry point for running the Telegram Bot
webhook server using uvicorn with configurable multi-worker support.

Example:
    Run from command line::

        telegram-bot

    Or run directly::

        python -m telegram_bot.main

Attributes:
    main: Main function to start the webhook server.
"""

import uvicorn

from telegram_bot.config.settings import get_settings
from telegram_bot.logging_config import get_logger, setup_logging

logger = get_logger("main")


def main() -> None:
    """Run the Telegram bot webhook server.

    Starts the uvicorn ASGI server with the FastAPI application configured
    for Telegram webhook handling. Supports multiple workers for handling
    concurrent users with proper process isolation.

    The server configuration includes:
        - Multi-worker support via factory pattern
        - Configurable concurrency limits
        - Graceful shutdown handling
        - Performance optimizations (httptools, uvloop)

    Configuration is loaded from environment variables or .env file.
    See Settings class for all available options.

    Example:
        Start server programmatically::

            from telegram_bot.main import main
            main()

    Note:
        In production (workers > 1), each worker creates its own app instance
        using the factory pattern for proper process isolation.
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
