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
    Command responses (start, help) and product display templates are
    rendered via Jinja2 templates in telegram_bot.templates module.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import InputMediaPhoto, Message

from telegram_bot.logging_config import get_logger
from telegram_bot.services.input_classifier import InputClassifier
from telegram_bot.services.message_processor import (
    ProcessingResult,
    ProcessingStatus,
    get_processor,
)
from telegram_bot.templates import templates
from telegram_bot.utils.typing_indicator import continuous_typing

logger = get_logger("handlers.message")


def _create_classifier() -> InputClassifier:
    """Create a new InputClassifier instance.

    Returns:
        A new InputClassifier instance.
    """
    return InputClassifier()


async def _safe_answer(
    message: Message, text: str, parse_mode: str | None = None
) -> None:
    """Safely send a reply message with error handling.

    Args:
        message: The message to reply to.
        text: The text to send.
        parse_mode: Optional parse mode (HTML, Markdown, etc.)
    """
    try:
        await message.answer(text, parse_mode=parse_mode)
    except TelegramAPIError as e:
        logger.warning("Failed to send message to chat %d: %s", message.chat.id, e)


async def _send_product_media_group(
    message: Message,
    result: ProcessingResult,
    language_code: str | None = None,
) -> bool:
    """Send products as media group (photo carousel) if they have images.

    Args:
        message: The message to reply to.
        result: Processing result with products and response.
        language_code: User's language code for localization.

    Returns:
        True if media group was sent, False if no images available.
    """
    if not result.products:
        return False

    # Filter products with valid image URLs (max 10 for Telegram media group)
    products_with_images = [
        p for p in result.products if p.image_url and p.image_url.startswith("http")
    ][:10]

    if not products_with_images:
        return False

    # Build media group
    media_group: list[InputMediaPhoto] = []
    intro_text = result.response  # Gemini's response as intro on first photo

    for idx, product in enumerate(products_with_images):
        is_first = idx == 0
        caption = templates.format_product_caption(
            product={
                "name": product.name,
                "brand": product.brand,
                "description": product.description,
                "price": product.price,
                "sku": product.sku,
            },
            language_code=language_code,
            is_first=is_first,
            intro_text=intro_text if is_first else None,
        )

        media_group.append(
            InputMediaPhoto(
                media=product.image_url,
                caption=caption,
                parse_mode="HTML",
            )
        )

    try:
        await message.answer_media_group(media_group)
        logger.info(
            "Sent media group with %d product images to chat %d",
            len(media_group),
            message.chat.id,
        )
        return True
    except TelegramAPIError as e:
        logger.warning(
            "Failed to send media group to chat %d: %s. Falling back to text.",
            message.chat.id,
            e,
        )
        return False


def _format_products_as_text(
    result: ProcessingResult, language_code: str | None = None
) -> str:
    """Format products as text list.

    Args:
        result: Processing result with products data.
        language_code: User's language code for localization.

    Returns:
        Formatted text with product details.
    """
    if not result.products:
        return result.response or ""

    # Check if any product has exact match
    has_exact = any(p.match_type == "exact" for p in result.products)

    return templates.render_product_list(result.products, has_exact, language_code)


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
        await _safe_answer(message, templates.render_command("start", user_lang))

    @router.message(Command("help"))
    async def handle_help(message: Message) -> None:
        """Handle the /help command."""
        classifier.classify(message)
        logger.info("User %s requested help", message.from_user)
        user_lang = message.from_user.language_code if message.from_user else None
        await _safe_answer(message, templates.render_command("help", user_lang))

    # Register media handlers dynamically
    for filter_obj, type_name in media_filters:
        handler = create_media_handler(type_name)
        router.message(filter_obj)(handler)

    # Register text handler
    @router.message(F.text)
    async def handle_text(message: Message, bot: Bot) -> None:
        """Handle plain text messages via NLP service.

        If products with images are returned, sends as media group carousel.
        Otherwise sends text response.
        """
        input_type = classifier.classify(message)
        processor = get_processor()

        # Continuous typing indicator - refreshes every 4s while LLM processes
        async with continuous_typing(bot, message.chat.id):
            result = await processor.process_message(message, input_type, bot)

        # Try to send products as media group if available
        if result.products:
            user_lang = message.from_user.language_code if message.from_user else None
            media_sent = await _send_product_media_group(message, result, user_lang)
            if media_sent:
                return  # Media group sent successfully

        # Fallback to text response
        if result.response:
            await _safe_answer(message, result.response)

    # Register voice handler
    @router.message(F.voice)
    async def handle_voice(message: Message, bot: Bot) -> None:
        """Handle voice messages via ASR + NLP service."""
        input_type = classifier.classify(message)
        processor = get_processor()

        # Continuous typing - ASR + NLP can take several seconds
        async with continuous_typing(bot, message.chat.id):
            result = await processor.process_message(message, input_type, bot)

        if result.response:
            await _safe_answer(message, result.response)

    # Register audio handler
    @router.message(F.audio)
    async def handle_audio(message: Message, bot: Bot) -> None:
        """Handle audio messages via ASR + NLP service."""
        input_type = classifier.classify(message)
        processor = get_processor()

        # Continuous typing - ASR + NLP can take several seconds
        async with continuous_typing(bot, message.chat.id):
            result = await processor.process_message(message, input_type, bot)

        if result.response:
            await _safe_answer(message, result.response)

    # Register photo handler
    @router.message(F.photo)
    async def handle_photo(message: Message, bot: Bot) -> None:
        """Handle photo messages via OCR + NLP service.

        For product image searches, displays results as media group carousel.
        Falls back to text list if images unavailable.
        """
        input_type = classifier.classify(message)
        processor = get_processor()

        # Continuous typing - OCR + NLP can take several seconds
        async with continuous_typing(bot, message.chat.id):
            result = await processor.process_message(message, input_type, bot)

        # Check if we have products to display
        if result.products:
            user_lang = message.from_user.language_code if message.from_user else None

            # Try media group first
            media_sent = await _send_product_media_group(message, result, user_lang)
            if media_sent:
                logger.info("Sent media group for %d products", len(result.products))
                return

            # Fallback to text list
            product_text = _format_products_as_text(result, user_lang)
            await _safe_answer(message, product_text, parse_mode="HTML")
            logger.info("Sent text list for %d products", len(result.products))
        elif result.response:
            await _safe_answer(message, result.response)

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
