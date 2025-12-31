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
from aiogram.types import Message

from telegram_bot.logging_config import get_logger
from telegram_bot.services.input_classifier import InputClassifier
from telegram_bot.services.message_processor import ProcessingStatus, get_processor

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

        result = await processor.process_message(message, input_type, bot)

        if result.response:
            await _safe_answer(message, result.response)

    # Register voice handler
    @router.message(F.voice)
    async def handle_voice(message: Message, bot: Bot) -> None:
        """Handle voice messages via ASR + NLP service."""
        input_type = classifier.classify(message)
        processor = get_processor()

        # Send typing indicator while processing
        await message.answer_chat_action("typing")

        result = await processor.process_message(message, input_type, bot)

        if result.response:
            await _safe_answer(message, result.response)

    # Register audio handler
    @router.message(F.audio)
    async def handle_audio(message: Message, bot: Bot) -> None:
        """Handle audio messages via ASR + NLP service."""
        input_type = classifier.classify(message)
        processor = get_processor()

        await message.answer_chat_action("typing")

        result = await processor.process_message(message, input_type, bot)

        if result.response:
            await _safe_answer(message, result.response)

    # Register photo handler
    @router.message(F.photo)
    async def handle_photo(message: Message, bot: Bot) -> None:
        """Handle photo messages via OCR + NLP service."""
        input_type = classifier.classify(message)
        processor = get_processor()

        await message.answer_chat_action("typing")

        result = await processor.process_message(message, input_type, bot)

        if result.response:
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
