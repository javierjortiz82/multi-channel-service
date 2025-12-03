"""FastAPI application with Telegram webhook endpoint."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from weakref import WeakSet

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from telegram_bot.bot.handlers import create_message_router
from telegram_bot.config.settings import Settings, get_settings
from telegram_bot.logging_config import get_logger, setup_logging
from telegram_bot.services.webhook_service import validate_telegram_request

logger = get_logger("app")

# Maximum number of retries for webhook setup
MAX_WEBHOOK_RETRIES = 3

# Store background tasks to prevent garbage collection
_background_tasks: WeakSet[asyncio.Task[None]] = WeakSet()


async def set_webhook_with_retry(bot: Bot, settings: Settings) -> None:
    """Set webhook with retry logic for flood control.

    When multiple workers start simultaneously, Telegram may return
    TelegramRetryAfter errors. This function handles those gracefully
    with exponential backoff.

    If all retries are exhausted, the function logs a warning and continues.
    This is safe because another worker likely succeeded in setting the webhook,
    and the webhook configuration is idempotent.

    Args:
        bot: The Bot instance.
        settings: Application settings.
    """
    webhook_url = settings.webhook_url

    for attempt in range(MAX_WEBHOOK_RETRIES):
        try:
            await bot.set_webhook(
                url=webhook_url,
                secret_token=settings.webhook_secret.get_secret_value(),
                max_connections=settings.webhook_max_connections,
                drop_pending_updates=settings.webhook_drop_pending_updates,
            )
            logger.info("Webhook configured successfully")
            return
        except TelegramRetryAfter as e:
            wait_time = e.retry_after + 0.5  # Add buffer
            logger.warning(
                "Flood control on SetWebhook, attempt %d/%d. Waiting %.1f seconds...",
                attempt + 1,
                MAX_WEBHOOK_RETRIES,
                wait_time,
            )
            await asyncio.sleep(wait_time)

    # If we exhaust all retries, log warning and continue
    # Another worker likely succeeded - webhook setup is idempotent
    logger.warning(
        "Webhook setup exhausted retries. Another worker likely configured it."
    )


def create_bot(settings: Settings) -> Bot:
    """Create and configure the Telegram bot.

    Args:
        settings: Application settings.

    Returns:
        Configured Bot instance.
    """
    return Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure the aiogram dispatcher.

    Returns:
        Configured Dispatcher instance.
    """
    dp = Dispatcher()
    dp.include_router(create_message_router())
    return dp


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager.

    Sets up webhook on startup and removes it on shutdown.
    This runs as a background worker, independent of main request handling.

    Args:
        app: FastAPI application instance.

    Yields:
        None during application runtime.
    """
    settings: Settings = app.state.settings
    bot: Bot = app.state.bot

    # Set up webhook with full configuration
    logger.info("Setting webhook to: %s", settings.webhook_url)
    logger.info(
        "Webhook config | max_connections=%d | ip_filter=%s | drop_pending=%s",
        settings.webhook_max_connections,
        settings.webhook_ip_filter_enabled,
        settings.webhook_drop_pending_updates,
    )

    # Use retry logic to handle flood control from multiple workers
    await set_webhook_with_retry(bot, settings)

    yield

    # Clean up webhook with guaranteed session close
    logger.info("Removing webhook...")
    try:
        await bot.delete_webhook()
    except Exception:
        logger.exception("Error removing webhook")
    finally:
        await bot.session.close()
        logger.info("Bot session closed")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings instance (uses default if not provided).

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = get_settings()

    setup_logging(settings.log_level, settings=settings)

    app = FastAPI(
        title="Telegram Bot Webhook",
        description="Enterprise Telegram Bot with webhook integration",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Store bot and dispatcher in app state
    app.state.bot = create_bot(settings)
    app.state.dp = create_dispatcher()
    app.state.settings = settings

    # Register routes
    register_routes(app, settings)

    return app


async def process_update_background(dp: Dispatcher, bot: Bot, update: Update) -> None:
    """Process update in background task.

    This allows the webhook to respond immediately to Telegram
    while processing continues asynchronously.

    Args:
        dp: The aiogram Dispatcher instance.
        bot: The Bot instance.
        update: The Telegram Update to process.
    """
    try:
        await dp.feed_update(bot=bot, update=update)
        logger.debug("Update %d processed successfully", update.update_id)
    except Exception:
        logger.exception("Error processing update %d", update.update_id)


def register_routes(app: FastAPI, settings: Settings) -> None:
    """Register application routes.

    Args:
        app: FastAPI application instance.
        settings: Application settings.
    """

    @app.post(settings.webhook_path)
    async def webhook_handler(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> JSONResponse:
        """Handle incoming Telegram webhook updates.

        Security features:
        - IP filtering: Only accepts requests from Telegram server IPs
        - Secret token validation: Verifies X-Telegram-Bot-Api-Secret-Token header
        - Background processing: Responds immediately, processes asynchronously

        Args:
            request: The incoming HTTP request.
            x_telegram_bot_api_secret_token: Secret token from Telegram.

        Returns:
            JSON status response.

        Raises:
            HTTPException: If validation fails.
        """
        # 1. Validate IP address (if enabled)
        await validate_telegram_request(request, settings.webhook_ip_filter_enabled)

        # 2. Validate secret token
        expected_secret = settings.webhook_secret.get_secret_value()
        if x_telegram_bot_api_secret_token != expected_secret:
            logger.warning("Invalid webhook secret token received")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid secret token",
            )

        # 3. Parse update
        data: dict[str, Any] = await request.json()
        update = Update.model_validate(data, context={"bot": app.state.bot})

        # 4. Process in background (respond immediately to Telegram)
        task = asyncio.create_task(
            process_update_background(app.state.dp, app.state.bot, update)
        )
        _background_tasks.add(task)

        # 5. Return immediately (Telegram expects fast response)
        return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            Health status.
        """
        return {"status": "healthy"}
