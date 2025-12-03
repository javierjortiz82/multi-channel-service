"""Message handlers for the Telegram bot."""

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
    """Create and configure the message router.

    Returns:
        Configured Router instance with all message handlers.
    """
    router = Router(name="message_router")

    @router.message(Command("start"))  # type: ignore[misc]
    async def handle_start(message: Message) -> None:
        """Handle the /start command."""
        classifier.classify(message)
        logger.info("User %s started the bot", message.from_user)
        await message.answer(START_MESSAGE)

    @router.message(Command("help"))  # type: ignore[misc]
    async def handle_help(message: Message) -> None:
        """Handle the /help command."""
        classifier.classify(message)
        logger.info("User %s requested help", message.from_user)
        await message.answer(HELP_MESSAGE)

    @router.message(F.photo)  # type: ignore[misc]
    async def handle_photo(message: Message) -> None:
        """Handle photo messages."""
        classifier.classify(message)

    @router.message(F.document)  # type: ignore[misc]
    async def handle_document(message: Message) -> None:
        """Handle document messages."""
        classifier.classify(message)

    @router.message(F.video)  # type: ignore[misc]
    async def handle_video(message: Message) -> None:
        """Handle video messages."""
        classifier.classify(message)

    @router.message(F.audio)  # type: ignore[misc]
    async def handle_audio(message: Message) -> None:
        """Handle audio messages."""
        classifier.classify(message)

    @router.message(F.voice)  # type: ignore[misc]
    async def handle_voice(message: Message) -> None:
        """Handle voice messages."""
        classifier.classify(message)

    @router.message(F.video_note)  # type: ignore[misc]
    async def handle_video_note(message: Message) -> None:
        """Handle video note messages."""
        classifier.classify(message)

    @router.message(F.sticker)  # type: ignore[misc]
    async def handle_sticker(message: Message) -> None:
        """Handle sticker messages."""
        classifier.classify(message)

    @router.message(F.animation)  # type: ignore[misc]
    async def handle_animation(message: Message) -> None:
        """Handle animation messages."""
        classifier.classify(message)

    @router.message(F.location)  # type: ignore[misc]
    async def handle_location(message: Message) -> None:
        """Handle location messages."""
        classifier.classify(message)

    @router.message(F.venue)  # type: ignore[misc]
    async def handle_venue(message: Message) -> None:
        """Handle venue messages."""
        classifier.classify(message)

    @router.message(F.contact)  # type: ignore[misc]
    async def handle_contact(message: Message) -> None:
        """Handle contact messages."""
        classifier.classify(message)

    @router.message(F.poll)  # type: ignore[misc]
    async def handle_poll(message: Message) -> None:
        """Handle poll messages."""
        classifier.classify(message)

    @router.message(F.dice)  # type: ignore[misc]
    async def handle_dice(message: Message) -> None:
        """Handle dice messages."""
        classifier.classify(message)

    @router.message(F.text)  # type: ignore[misc]
    async def handle_text(message: Message) -> None:
        """Handle plain text messages."""
        classifier.classify(message)

    @router.message()  # type: ignore[misc]
    async def handle_unknown(message: Message) -> None:
        """Handle any other message type."""
        classifier.classify(message)
        logger.warning("Received unknown message type from %s", message.from_user)

    return router
