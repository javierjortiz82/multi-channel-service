"""Message handlers for the Telegram bot.

This module provides message handlers for all supported Telegram message types
using aiogram's Router pattern. Each handler classifies the incoming message,
routes it to appropriate backend services, and sends the response.

The module handles:
    - Bot commands (/start, /help)
    - Text messages (processed via NLP service)
    - Voice/Audio messages (transcribed via ASR, then NLP)
    - Photo messages (OCR extraction, then NLP)
    - Other media types (acknowledged but not processed)

Architecture:
    Message -> InputClassifier -> MessageProcessor -> InternalServiceClient -> Response

Example:
    Register handlers in the dispatcher::

        from telegram_bot.bot.handlers import create_message_router

        dp = Dispatcher()
        dp.include_router(create_message_router())

Note:
    Start and help messages are loaded from locales/messages.json.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message

from telegram_bot.components import send_product_card
from telegram_bot.logging_config import get_logger
from telegram_bot.services.input_classifier import InputClassifier
from telegram_bot.services.message_processor import (
    ProcessingResult,
    ProcessingStatus,
    get_processor,
)
from telegram_bot.services.product_cache import get_product_cache
from telegram_bot.utils.i18n import get_localized_message
from telegram_bot.utils.typing_indicator import continuous_typing

logger = get_logger("handlers.message")


def _create_classifier() -> InputClassifier:
    """Create a new InputClassifier instance.

    Returns:
        A new InputClassifier instance.
    """
    return InputClassifier()


async def _safe_answer(message: Message, text: str) -> None:
    """Safely send a reply message with error handling.

    Args:
        message: The message to reply to.
        text: The text to send.
    """
    try:
        await message.answer(text)
    except TelegramAPIError as e:
        logger.warning("Failed to send message to chat %d: %s", message.chat.id, e)


def _extract_products_from_response(result: ProcessingResult) -> list[dict[str, Any]]:
    """Extract product data from processing result if available.

    Checks raw_response for product data from NLP service function calls.

    Args:
        result: The processing result from message processor.

    Returns:
        List of product dictionaries, or empty list if none found.
    """
    if not result.raw_response:
        return []

    # Check for products in NLP response (from MCP tool calls)
    nlp_response = result.raw_response.get("nlp", result.raw_response)

    # Look for products in various possible locations
    products = nlp_response.get("products", [])
    if products and isinstance(products, list):
        return list(products)

    # Check for items from search results
    items = nlp_response.get("items", [])
    if items and isinstance(items, list):
        return list(items)

    return []


def _extract_detected_language(result: ProcessingResult) -> str | None:
    """Extract detected language from NLP response.

    Args:
        result: The processing result from message processor.

    Returns:
        ISO 639-1 language code (e.g., 'en', 'es') or None.
    """
    if not result.raw_response:
        return None

    nlp_response = result.raw_response.get("nlp", result.raw_response)
    return nlp_response.get("detected_language")


async def _process_and_respond(
    message: Message,
    bot: Bot,
    classifier: InputClassifier,
) -> None:
    """Process a message and send the response.

    Shared handler logic for text, voice, audio, and photo messages.

    Args:
        message: The Telegram message to process.
        bot: The Bot instance.
        classifier: The input classifier instance.
    """
    input_type = classifier.classify(message)
    processor = get_processor()

    # Continuous typing indicator - refreshes every 4s while LLM processes
    async with continuous_typing(bot, message.chat.id):
        result = await processor.process_message(message, input_type, bot)

    # Send response with product cards if available
    user_lang = message.from_user.language_code if message.from_user else None
    await _send_response_with_products(
        message, bot, result, fallback_language_code=user_lang
    )


async def _send_response_with_products(
    message: Message,
    bot: Bot,
    result: ProcessingResult,
    fallback_language_code: str | None = None,
) -> None:
    """Send response, using product cards if products are available.

    Args:
        message: The original message to reply to.
        bot: The Bot instance.
        result: The processing result with response and optional products.
        fallback_language_code: Fallback language code if NLP doesn't detect one.
    """
    # Extract products from response
    products = _extract_products_from_response(result)

    # Use detected language from NLP, fallback to Telegram language
    detected_lang = _extract_detected_language(result)
    language_code = detected_lang or fallback_language_code

    if products and len(products) > 0:
        # Store products in cache for pagination navigation (with language)
        cache = get_product_cache()
        cache.store(message.chat.id, products, language_code=language_code)

        # Send first product as card with pagination
        first_product = products[0]
        total = len(products)

        logger.info(
            "Sending product card: %s (%d total, cached, detected_lang=%s, fallback=%s)",
            first_product.get("name", "Unknown"),
            total,
            detected_lang,
            fallback_language_code,
        )

        # Send product card (no additional text - card is self-explanatory)
        await send_product_card(
            bot=bot,
            chat_id=message.chat.id,
            product=first_product,
            page=0,
            total=total,
            language_code=language_code,
        )
        # Product cards are self-contained, no need to send duplicate text
    elif result.response:
        # No products, send regular text response
        await _safe_answer(message, result.response)


def create_message_router() -> Router:
    """Create and configure the message router with all handlers.

    Creates a Router instance and registers handlers for all supported
    message types. Handlers are registered in priority order to ensure
    proper message classification.

    The handler registration order:
        1. Commands (/start, /help) - highest priority
        2. Media types (photo, document, video, etc.)
        3. Special content (location, contact, poll, dice)
        4. Plain text
        5. Unknown (catch-all fallback)

    Returns:
        Router: Configured Router instance with all message handlers registered.

    Example:
        Include router in dispatcher::

            from telegram_bot.bot.handlers import create_message_router

            dp = Dispatcher()
            router = create_message_router()
            dp.include_router(router)
    """
    router = Router(name="message_router")
    classifier = _create_classifier()

    # Define media type filters in priority order (for types without dedicated handlers)
    # Note: photo, voice, and audio have dedicated handlers that call the processor
    # Each tuple: (filter, type_name for logging)
    media_filters: list[tuple[Any, str]] = [
        (F.document, "document"),
        (F.video, "video"),
        (F.video_note, "video_note"),
        (F.sticker, "sticker"),
        (F.animation, "animation"),
        (F.location, "location"),
        (F.venue, "venue"),
        (F.contact, "contact"),
        (F.poll, "poll"),
        (F.dice, "dice"),
    ]

    def create_media_handler(
        type_name: str,
    ) -> Callable[[Message], Awaitable[None]]:
        """Create a handler function for a specific media type.

        Args:
            type_name: The name of the media type for logging.

        Returns:
            An async handler function.
        """

        async def handler(message: Message) -> None:
            classifier.classify(message)
            logger.debug(
                "Processed %s message from user %s", type_name, message.from_user
            )

        handler.__name__ = f"handle_{type_name}"
        handler.__doc__ = f"Handle {type_name} messages."
        return handler

    # Register command handlers
    @router.message(Command("start"))
    async def handle_start(message: Message) -> None:
        """Handle the /start command."""
        classifier.classify(message)
        logger.info("User %s started the bot", message.from_user)
        user_lang = message.from_user.language_code if message.from_user else None
        await _safe_answer(message, get_localized_message("start_message", user_lang))

    @router.message(Command("help"))
    async def handle_help(message: Message) -> None:
        """Handle the /help command."""
        classifier.classify(message)
        logger.info("User %s requested help", message.from_user)
        user_lang = message.from_user.language_code if message.from_user else None
        await _safe_answer(message, get_localized_message("help_message", user_lang))

    # Register media handlers dynamically
    for filter_obj, type_name in media_filters:
        handler = create_media_handler(type_name)
        router.message(filter_obj)(handler)

    # Register text handler
    @router.message(F.text)
    async def handle_text(message: Message, bot: Bot) -> None:
        """Handle plain text messages via NLP service."""
        await _process_and_respond(message, bot, classifier)

    # Register voice handler
    @router.message(F.voice)
    async def handle_voice(message: Message, bot: Bot) -> None:
        """Handle voice messages via ASR + NLP service."""
        await _process_and_respond(message, bot, classifier)

    # Register audio handler
    @router.message(F.audio)
    async def handle_audio(message: Message, bot: Bot) -> None:
        """Handle audio messages via ASR + NLP service."""
        await _process_and_respond(message, bot, classifier)

    # Register photo handler
    @router.message(F.photo)
    async def handle_photo(message: Message, bot: Bot) -> None:
        """Handle photo messages via OCR + NLP service."""
        await _process_and_respond(message, bot, classifier)

    # Register fallback handler
    @router.message()
    async def handle_unknown(message: Message, bot: Bot) -> None:
        """Handle any other message type (fallback handler)."""
        input_type = classifier.classify(message)
        logger.warning("Received unknown message type from %s", message.from_user)

        processor = get_processor()
        result = await processor.process_message(message, input_type, bot)

        if result.status == ProcessingStatus.UNSUPPORTED and result.response:
            await _safe_answer(message, result.response)

    return router
