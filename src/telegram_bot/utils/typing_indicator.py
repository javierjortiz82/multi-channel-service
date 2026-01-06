"""Continuous typing indicator for Telegram.

Telegram's typing indicator only lasts ~5 seconds. For longer operations
like LLM processing (500-2000ms+), we need to refresh it periodically.

This module provides a context manager that keeps the "typing..." indicator
active until the async operation completes.

Example:
    async with continuous_typing(bot, chat_id):
        # Do slow operation - typing will stay active
        result = await llm.generate(prompt)
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from telegram_bot.logging_config import get_logger

logger = get_logger("typing_indicator")

# Telegram typing indicator lasts ~5 seconds, refresh every 4 seconds
TYPING_REFRESH_INTERVAL = 4.0


@asynccontextmanager
async def continuous_typing(
    bot: Bot,
    chat_id: int,
    *,
    interval: float = TYPING_REFRESH_INTERVAL,
) -> AsyncGenerator[None, None]:
    """Context manager that maintains typing indicator during async operations.

    Sends typing action immediately, then refreshes every `interval` seconds
    until the context exits. Handles errors gracefully - if Telegram API fails,
    it logs and continues without crashing.

    Args:
        bot: The Telegram Bot instance
        chat_id: The chat ID to show typing in
        interval: Seconds between typing refreshes (default: 4)

    Yields:
        None

    Example:
        async with continuous_typing(bot, message.chat.id):
            result = await slow_llm_call(text)
    """
    task: asyncio.Task[None] | None = None
    stop_event = asyncio.Event()

    async def _keep_typing() -> None:
        """Background task that sends typing action periodically."""
        while not stop_event.is_set():
            try:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
            except TelegramAPIError as e:
                logger.debug("Typing indicator failed for chat %d: %s", chat_id, e)
                # Don't break - user might have blocked bot or chat was deleted
            except Exception as e:
                logger.warning("Unexpected error in typing indicator: %s", e)
                break

            try:
                # Wait for interval or until stopped
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break  # Event was set, exit loop
            except asyncio.TimeoutError:
                continue  # Timeout expired, send another typing action

    try:
        # Send first typing action immediately
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except TelegramAPIError as e:
            logger.debug("Initial typing failed for chat %d: %s", chat_id, e)

        # Start background refresh task
        task = asyncio.create_task(_keep_typing())

        yield

    finally:
        # Stop the background task
        stop_event.set()
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
