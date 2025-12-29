"""FastAPI application with Telegram webhook endpoint."""

import asyncio
import hmac
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from telegram_bot.bot.handlers import create_message_router
from telegram_bot.config.settings import Settings, get_settings
from telegram_bot.logging_config import get_logger, setup_logging
from telegram_bot.services.webhook_service import validate_telegram_request

logger = get_logger("app")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add comprehensive security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Add security headers to response.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler.

        Returns:
            Response with security headers added.
        """
        response = await call_next(request)
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        # Additional security headers
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        return response


class RateLimiter:
    """Thread-safe in-memory rate limiter for webhook endpoint.

    Implements a sliding window rate limiting algorithm with async lock
    to prevent race conditions in concurrent environments.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed per window.
            window_seconds: Time window in seconds.
        """
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_counter = 0
        self._cleanup_interval = 100  # Cleanup every 100 requests

    async def is_allowed(self, client_ip: str) -> bool:
        """Check if request from client IP is allowed (async, thread-safe).

        Args:
            client_ip: The client's IP address.

        Returns:
            True if request is allowed, False if rate limited.
        """
        now = time.time()
        window_start = now - self._window_seconds

        async with self._lock:
            # Periodic cleanup of old IPs to prevent memory leak
            self._cleanup_counter += 1
            if self._cleanup_counter >= self._cleanup_interval:
                self._cleanup_old_entries(window_start)
                self._cleanup_counter = 0

            # Clean old entries for this IP
            if client_ip in self._requests:
                self._requests[client_ip] = [
                    t for t in self._requests[client_ip] if t > window_start
                ]
            else:
                self._requests[client_ip] = []

            # Check if under limit
            if len(self._requests[client_ip]) >= self._max_requests:
                return False

            # Record this request
            self._requests[client_ip].append(now)
            return True

    def _cleanup_old_entries(self, window_start: float) -> None:
        """Remove IPs with no recent requests to prevent memory leak.

        Args:
            window_start: Timestamp marking the start of the current window.
        """
        empty_ips = [
            ip
            for ip, timestamps in self._requests.items()
            if not timestamps or all(t <= window_start for t in timestamps)
        ]
        for ip in empty_ips:
            del self._requests[ip]


# Store background tasks with strong references to prevent garbage collection
_background_tasks: set[asyncio.Task[None]] = set()

# Rate limiter instance (initialized lazily with settings)
_rate_limiter: RateLimiter | None = None
_rate_limiter_lock = asyncio.Lock()


async def _get_rate_limiter(settings: Settings) -> RateLimiter:
    """Get or create the rate limiter instance (async, thread-safe).

    Uses double-checked locking pattern to ensure thread-safe initialization
    while minimizing lock contention after initialization.

    Args:
        settings: Application settings.

    Returns:
        The rate limiter instance.
    """
    global _rate_limiter
    if _rate_limiter is None:
        async with _rate_limiter_lock:
            # Double-check after acquiring lock
            if _rate_limiter is None:
                _rate_limiter = RateLimiter(
                    max_requests=settings.rate_limit_requests,
                    window_seconds=settings.rate_limit_window_seconds,
                )
    return _rate_limiter


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
    max_retries = settings.webhook_max_retries
    retry_buffer = settings.webhook_retry_buffer_seconds

    for attempt in range(max_retries):
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
            wait_time = e.retry_after + retry_buffer
            logger.warning(
                "Flood control on SetWebhook, attempt %d/%d. Waiting %.1f seconds...",
                attempt + 1,
                max_retries,
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
    except TelegramAPIError as e:
        logger.exception("Telegram API error removing webhook: %s", e)
    except OSError as e:
        logger.exception("Network error removing webhook: %s", e)
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

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

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
    except TelegramAPIError as e:
        logger.exception(
            "Telegram API error processing update %d: %s", update.update_id, e
        )
    except OSError as e:
        logger.exception("Network error processing update %d: %s", update.update_id, e)


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

        Security features (in order of execution):
        1. IP filtering: Only accepts requests from Telegram server IPs
        2. Secret token validation: Timing-safe verification of secret token
        3. Rate limiting: Prevents abuse with per-IP request limits (after auth)
        4. Background processing: Responds immediately, processes asynchronously

        Args:
            request: The incoming HTTP request.
            x_telegram_bot_api_secret_token: Secret token from Telegram.

        Returns:
            JSON status response.

        Raises:
            HTTPException: If validation fails.
        """
        client_ip = request.client.host if request.client else "unknown"

        # 1. Validate IP address first (if enabled) - reject non-Telegram IPs early
        await validate_telegram_request(request, settings.webhook_ip_filter_enabled)

        # 2. Validate secret token (timing-safe comparison)
        expected_secret = settings.webhook_secret.get_secret_value()
        token_to_check = x_telegram_bot_api_secret_token or ""
        if not hmac.compare_digest(token_to_check, expected_secret):
            logger.warning("Invalid webhook secret token received")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid secret token",
            )

        # 3. Rate limiting check (only after authentication to prevent DoS)
        rate_limiter = await _get_rate_limiter(settings)
        if not await rate_limiter.is_allowed(client_ip):
            logger.warning("Rate limit exceeded for IP: %s", client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
            )

        # 4. Parse update with error handling
        try:
            data: dict[str, Any] = await request.json()
        except JSONDecodeError as err:
            logger.warning("Invalid JSON payload received")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON",
            ) from err

        try:
            update = Update.model_validate(data, context={"bot": app.state.bot})
        except ValidationError as err:
            logger.warning("Invalid Telegram update format: %s", err.error_count())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid update format",
            ) from err

        # 5. Process in background (respond immediately to Telegram)
        task = asyncio.create_task(
            process_update_background(app.state.dp, app.state.bot, update)
        )
        _background_tasks.add(task)
        # Add callback to remove task from set when done (prevents memory leak)
        task.add_done_callback(_background_tasks.discard)

        # 6. Return immediately (Telegram expects fast response)
        return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint.

        Returns:
            Health status.
        """
        return {"status": "healthy"}
