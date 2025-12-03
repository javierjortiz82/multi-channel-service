"""Message handlers for the Telegram bot.

This module provides message handlers for all supported Telegram message types
using aiogram's Router pattern. Each handler classifies the incoming message
and logs the input type.

The module handles:
    - Bot commands (/start, /help)
    - Media messages (photo, video, audio, document, etc.)
    - Special content (location, contact, poll, dice, etc.)
    - Plain text messages
    - Unknown message types (fallback)

Example:
    Register handlers in the dispatcher::

        from telegram_bot.bot.handlers import create_message_router

        dp = Dispatcher()
        dp.include_router(create_message_router())

Attributes:
    START_MESSAGE: Welcome message displayed for /start command.
    HELP_MESSAGE: Help text displayed for /help command.
    classifier: InputClassifier instance for message type detection.
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from telegram_bot.logging_config import get_logger
from telegram_bot.services.input_classifier import InputClassifier

logger = get_logger("handlers.message")

# Initialize the classifier
classifier = InputClassifier()

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

    @router.message(Command("start"))  # type: ignore[misc]
    async def handle_start(message: Message) -> None:
        """Handle the /start command.

        Sends a welcome message to the user and classifies the input.

        Args:
            message: The incoming Telegram message.
        """
        classifier.classify(message)
        logger.info("User %s started the bot", message.from_user)
        await message.answer(START_MESSAGE)

    @router.message(Command("help"))  # type: ignore[misc]
    async def handle_help(message: Message) -> None:
        """Handle the /help command.

        Sends help information to the user with available commands
        and supported content types.

        Args:
            message: The incoming Telegram message.
        """
        classifier.classify(message)
        logger.info("User %s requested help", message.from_user)
        await message.answer(HELP_MESSAGE)

    @router.message(F.photo)  # type: ignore[misc]
    async def handle_photo(message: Message) -> None:
        """Handle photo messages.

        Args:
            message: The incoming Telegram message containing a photo.
        """
        classifier.classify(message)

    @router.message(F.document)  # type: ignore[misc]
    async def handle_document(message: Message) -> None:
        """Handle document messages.

        Args:
            message: The incoming Telegram message containing a document.
        """
        classifier.classify(message)

    @router.message(F.video)  # type: ignore[misc]
    async def handle_video(message: Message) -> None:
        """Handle video messages.

        Args:
            message: The incoming Telegram message containing a video.
        """
        classifier.classify(message)

    @router.message(F.audio)  # type: ignore[misc]
    async def handle_audio(message: Message) -> None:
        """Handle audio messages.

        Args:
            message: The incoming Telegram message containing audio.
        """
        classifier.classify(message)

    @router.message(F.voice)  # type: ignore[misc]
    async def handle_voice(message: Message) -> None:
        """Handle voice messages.

        Args:
            message: The incoming Telegram message containing a voice recording.
        """
        classifier.classify(message)

    @router.message(F.video_note)  # type: ignore[misc]
    async def handle_video_note(message: Message) -> None:
        """Handle video note (round video) messages.

        Args:
            message: The incoming Telegram message containing a video note.
        """
        classifier.classify(message)

    @router.message(F.sticker)  # type: ignore[misc]
    async def handle_sticker(message: Message) -> None:
        """Handle sticker messages.

        Args:
            message: The incoming Telegram message containing a sticker.
        """
        classifier.classify(message)

    @router.message(F.animation)  # type: ignore[misc]
    async def handle_animation(message: Message) -> None:
        """Handle animation (GIF) messages.

        Args:
            message: The incoming Telegram message containing an animation.
        """
        classifier.classify(message)

    @router.message(F.location)  # type: ignore[misc]
    async def handle_location(message: Message) -> None:
        """Handle location messages.

        Args:
            message: The incoming Telegram message containing location data.
        """
        classifier.classify(message)

    @router.message(F.venue)  # type: ignore[misc]
    async def handle_venue(message: Message) -> None:
        """Handle venue messages.

        Args:
            message: The incoming Telegram message containing venue data.
        """
        classifier.classify(message)

    @router.message(F.contact)  # type: ignore[misc]
    async def handle_contact(message: Message) -> None:
        """Handle contact messages.

        Args:
            message: The incoming Telegram message containing contact data.
        """
        classifier.classify(message)

    @router.message(F.poll)  # type: ignore[misc]
    async def handle_poll(message: Message) -> None:
        """Handle poll messages.

        Args:
            message: The incoming Telegram message containing a poll.
        """
        classifier.classify(message)

    @router.message(F.dice)  # type: ignore[misc]
    async def handle_dice(message: Message) -> None:
        """Handle dice messages.

        Args:
            message: The incoming Telegram message containing a dice roll.
        """
        classifier.classify(message)

    @router.message(F.text)  # type: ignore[misc]
    async def handle_text(message: Message) -> None:
        """Handle plain text messages.

        Args:
            message: The incoming Telegram message containing text.
        """
        classifier.classify(message)

    @router.message()  # type: ignore[misc]
    async def handle_unknown(message: Message) -> None:
        """Handle any other message type (fallback handler).

        This handler catches all messages that don't match any other handler.
        Logs a warning for debugging purposes.

        Args:
            message: The incoming Telegram message of unknown type.
        """
        classifier.classify(message)
        logger.warning("Received unknown message type from %s", message.from_user)

    return router
