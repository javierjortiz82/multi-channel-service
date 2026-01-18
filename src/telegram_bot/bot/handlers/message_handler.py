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

Attributes:
    START_MESSAGE: Welcome message displayed for /start command.
    HELP_MESSAGE: Help text displayed for /help command.
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
from telegram_bot.utils.typing_indicator import continuous_typing

logger = get_logger("handlers.message")


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram's HTML parse mode.

    Escapes <, >, and & characters to prevent HTML injection and parsing errors
    when displaying dynamic content like product names or descriptions.

    Args:
        text: The text to escape.

    Returns:
        Text with HTML special characters escaped.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def _format_products_as_text(result: ProcessingResult) -> str:
    """Format products as text list when carousel fails.

    Args:
        result: Processing result with product_carousel data.

    Returns:
        Formatted text with product details.
    """
    if not result.product_carousel:
        return result.response or ""

    # Check if any product has exact match
    has_exact = any(p.match_type == "exact" for p in result.product_carousel)

    if has_exact:
        header = "✅ <b>¡Encontré productos que coinciden con tu imagen!</b>\n\n"
    else:
        header = "🔍 <b>No tenemos exactamente ese producto, pero encontré opciones similares:</b>\n\n"

    lines = [header]

    for i, product in enumerate(result.product_carousel[:5], 1):
        price_str = f"${product.price:.2f}" if product.price else "Consultar"
        similarity_pct = f"{product.similarity:.0%}"

        line = f"<b>{i}. {escape_html(product.name)}</b>\n"
        if product.brand:
            line += f"   🏢 {escape_html(product.brand)}\n"
        if product.description:
            desc = product.description[:100]
            if len(product.description) > 100:
                desc += "..."
            line += f"   📝 {escape_html(desc)}\n"
        line += f"   💰 {price_str} | Similitud: {similarity_pct}\n"
        line += f"   📦 SKU: {product.sku}\n"

        lines.append(line)

    lines.append("\n¿Te interesa alguno de estos productos?")

    return "\n".join(lines)


async def _send_product_carousel(
    bot: Bot,
    chat_id: int,
    result: ProcessingResult,
) -> bool:
    """Send product carousel as media group with elegant cards.

    Args:
        bot: The Telegram bot instance.
        chat_id: The chat ID to send to.
        result: Processing result with product_carousel data.

    Returns:
        True if carousel was sent successfully, False otherwise.
    """
    if not result.product_carousel:
        return False

    try:
        # Build media group (max 10 items per Telegram API)
        media_items: list[InputMediaPhoto] = []

        for product in result.product_carousel[:10]:
            # Format product card caption
            # Use elegant formatting with emojis for visual hierarchy
            price_str = f"${product.price:.2f}" if product.price else "Consultar"
            similarity_pct = f"{product.similarity:.0%}"

            # All cards get full details
            match_indicator = (
                "✅ Coincidencia" if product.match_type == "exact" else "🔍 Similar"
            )
            caption = (
                f"{match_indicator} ({similarity_pct})\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>{escape_html(product.name)}</b>\n"
            )
            if product.brand:
                caption += f"🏢 {escape_html(product.brand)}\n"
            if product.description:
                # Truncate description to fit caption limit
                desc = product.description[:150]
                if len(product.description) > 150:
                    desc += "..."
                caption += f"📝 {escape_html(desc)}\n"
            caption += f"💰 <b>{price_str}</b>\n"
            caption += f"📦 SKU: {escape_html(product.sku)}"

            media_items.append(
                InputMediaPhoto(
                    media=product.image_url,
                    caption=caption,
                    parse_mode="HTML",
                )
            )

        if len(media_items) >= 2:
            # Send as media group (carousel)
            await bot.send_media_group(chat_id=chat_id, media=media_items)
            logger.info(
                "Sent product carousel with %d items to chat %d",
                len(media_items),
                chat_id,
            )
            return True
        elif len(media_items) == 1:
            # Single product - send as regular photo
            product = result.product_carousel[0]
            await bot.send_photo(
                chat_id=chat_id,
                photo=product.image_url,
                caption=media_items[0].caption,
                parse_mode="HTML",
            )
            logger.info("Sent single product photo to chat %d", chat_id)
            return True
        else:
            return False

    except TelegramAPIError as e:
        logger.warning(
            "Failed to send product carousel to chat %d: %s",
            chat_id,
            e,
        )
        return False


# Welcome message for /start command
START_MESSAGE = """
<b>¡Bienvenido!</b> 👋

Soy un bot de Telegram con soporte para webhook.

Puedo procesar diferentes tipos de mensajes:
• Texto
• Fotos
• Documentos
• Videos
• Audio
• Ubicaciones
• Y más...

Usa /help para ver los comandos disponibles.
"""

# Help message
HELP_MESSAGE = """
<b>Comandos disponibles:</b>

/start - Iniciar el bot
/help - Mostrar esta ayuda

<b>Tipos de contenido soportados:</b>
• Mensajes de texto
• Fotos e imágenes
• Documentos y archivos
• Videos y animaciones
• Mensajes de voz y audio
• Ubicaciones y lugares
• Contactos
• Encuestas
• Stickers
"""


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
        await _safe_answer(message, START_MESSAGE)

    @router.message(Command("help"))
    async def handle_help(message: Message) -> None:
        """Handle the /help command."""
        classifier.classify(message)
        logger.info("User %s requested help", message.from_user)
        await _safe_answer(message, HELP_MESSAGE)

    # Register media handlers dynamically
    for filter_obj, type_name in media_filters:
        handler = create_media_handler(type_name)
        router.message(filter_obj)(handler)

    # Register text handler
    @router.message(F.text)
    async def handle_text(message: Message, bot: Bot) -> None:
        """Handle plain text messages via NLP service."""
        input_type = classifier.classify(message)
        processor = get_processor()

        # Continuous typing indicator - refreshes every 4s while LLM processes
        async with continuous_typing(bot, message.chat.id):
            result = await processor.process_message(message, input_type, bot)

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

        For product image searches, displays results as a visual carousel
        using Telegram's media group feature for a modern UX experience.
        """
        input_type = classifier.classify(message)
        processor = get_processor()

        # Continuous typing - OCR + NLP can take several seconds
        async with continuous_typing(bot, message.chat.id):
            result = await processor.process_message(message, input_type, bot)

        # Check if we have a product carousel to display
        if result.product_carousel:
            # Send carousel first (visual products)
            carousel_sent = await _send_product_carousel(bot, message.chat.id, result)

            # Then send text response as follow-up
            if result.response and carousel_sent:
                await _safe_answer(message, result.response)
            elif result.response:
                # Carousel failed, send text-only fallback with product list
                fallback_text = _format_products_as_text(result)
                await _safe_answer(message, fallback_text, parse_mode="HTML")
                logger.info(
                    "Sent text fallback for %d products", len(result.product_carousel)
                )
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
