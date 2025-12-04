"""Input classifier service for Telegram messages.

This module provides classification of Telegram message types using a
Chain-of-Thought approach that systematically checks message attributes
in order of specificity.

Example:
    Basic usage::

        from telegram_bot.services.input_classifier import InputClassifier

        classifier = InputClassifier()
        input_type = classifier.classify(message)
        print(f"Message type: {input_type.value}")

Attributes:
    InputType: Enumeration of all supported input types.
    InputClassifier: Main classifier class for message type detection.
"""

from enum import Enum
from typing import Any

from aiogram.types import Message

from telegram_bot.logging_config import get_logger

logger = get_logger("input_classifier")


class InputType(str, Enum):
    """Enumeration of supported Telegram message input types.

    This enum inherits from both str and Enum, allowing direct string
    comparison and serialization while maintaining type safety.

    Attributes:
        TEXT: Plain text messages.
        COMMAND: Bot commands starting with '/'.
        PHOTO: Photo/image messages.
        DOCUMENT: Document/file attachments.
        VIDEO: Video messages.
        AUDIO: Audio file messages.
        VOICE: Voice recording messages.
        VIDEO_NOTE: Round video messages.
        STICKER: Sticker messages.
        ANIMATION: GIF/animation messages.
        LOCATION: Location sharing messages.
        VENUE: Venue/place sharing messages.
        CONTACT: Contact sharing messages.
        POLL: Poll messages.
        DICE: Dice/random number messages.
        UNKNOWN: Unrecognized message types.

    Example:
        Check message type::

            if input_type == InputType.TEXT:
                print("This is a text message")
    """

    TEXT = "text"
    COMMAND = "command"
    PHOTO = "photo"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    STICKER = "sticker"
    ANIMATION = "animation"
    LOCATION = "location"
    VENUE = "venue"
    CONTACT = "contact"
    POLL = "poll"
    DICE = "dice"
    UNKNOWN = "unknown"


class InputClassifier:
    """Classifier for Telegram message input types.

    Uses a Chain-of-Thought approach by checking message attributes
    in a systematic order based on specificity. Media types are checked
    first, followed by special content types, then text-based content.

    The classification priority order:
        1. Media attachments (photo, document, video, audio, etc.)
        2. Special content (location, venue, contact, poll, dice)
        3. Text content (commands vs plain text)
        4. Unknown (fallback)

    Attributes:
        _ATTRIBUTE_TYPE_MAP: Ordered mapping of message attributes to InputType.
        _MAX_LOG_CONTENT_LENGTH: Maximum characters to log from message content.

    Example:
        Classify a message::

            classifier = InputClassifier()
            message = await bot.get_updates()[0].message
            input_type = classifier.classify(message)

            if input_type == InputType.PHOTO:
                print("User sent a photo")
            elif input_type == InputType.COMMAND:
                print(f"User sent command: {message.text}")
    """

    # Maximum characters to log from message content (to avoid PII exposure)
    _MAX_LOG_CONTENT_LENGTH: int = 30

    # Mapping of message attributes to input types (order matters for priority)
    _ATTRIBUTE_TYPE_MAP: list[tuple[str, InputType]] = [
        ("photo", InputType.PHOTO),
        ("document", InputType.DOCUMENT),
        ("video", InputType.VIDEO),
        ("audio", InputType.AUDIO),
        ("voice", InputType.VOICE),
        ("video_note", InputType.VIDEO_NOTE),
        ("sticker", InputType.STICKER),
        ("animation", InputType.ANIMATION),
        ("location", InputType.LOCATION),
        ("venue", InputType.VENUE),
        ("contact", InputType.CONTACT),
        ("poll", InputType.POLL),
        ("dice", InputType.DICE),
    ]

    def classify(self, message: Message) -> InputType:
        """Classify the input type of a Telegram message.

        Chain-of-Thought classification:
        1. Check for media attachments (most specific)
        2. Check for special content (location, contact, poll, etc.)
        3. Check for text-based content (command vs plain text)
        4. Fall back to unknown

        Args:
            message: The Telegram message to classify.

        Returns:
            The classified input type.
        """
        input_type = self._classify_internal(message)
        self._log_classification(message, input_type)
        return input_type

    def _classify_internal(self, message: Message) -> InputType:
        """Execute internal classification logic without logging.

        Args:
            message: The Telegram message to classify.

        Returns:
            The determined InputType for the message.
        """
        # Check for media and special content types
        for attr, input_type in self._ATTRIBUTE_TYPE_MAP:
            if getattr(message, attr, None) is not None:
                return input_type

        # Check for text content
        if message.text:
            return self._classify_text(message.text)

        # Check for caption (media with caption but no direct media attribute)
        if message.caption:
            return InputType.TEXT

        return InputType.UNKNOWN

    def _classify_text(self, text: str) -> InputType:
        """Classify text content as command or plain text.

        Args:
            text: The text content to classify.

        Returns:
            Either COMMAND or TEXT input type.
        """
        if text.startswith("/"):
            return InputType.COMMAND
        return InputType.TEXT

    def _truncate_content(self, content: str) -> str:
        """Truncate content to prevent PII exposure in logs.

        Args:
            content: The content to truncate.

        Returns:
            Truncated content with ellipsis if needed.
        """
        if len(content) <= self._MAX_LOG_CONTENT_LENGTH:
            return content
        return content[: self._MAX_LOG_CONTENT_LENGTH] + "..."

    def _log_classification(self, message: Message, input_type: InputType) -> None:
        """Log the classification result.

        Args:
            message: The classified message.
            input_type: The determined input type.
        """
        user_info = self._get_user_info(message)
        logger.info(
            "Classified input | type=%s | user=%s | chat_id=%d",
            input_type.value,
            user_info,
            message.chat.id,
        )
        # Log to console with truncated content for text messages (PII protection)
        if input_type == InputType.TEXT and message.text:
            truncated = self._truncate_content(message.text)
            logger.info("[INPUT TYPE] %s | content: %s", input_type.value, truncated)
        else:
            logger.info("[INPUT TYPE] %s", input_type.value)

    def _get_user_info(self, message: Message) -> str:
        """Extract user information for logging.

        Args:
            message: The message containing user info.

        Returns:
            Formatted user string.
        """
        if message.from_user:
            username = message.from_user.username or "no_username"
            return f"{message.from_user.id}:{username}"
        return "unknown_user"

    def classify_raw(self, data: dict[str, Any]) -> InputType:
        """Classify from raw update data (for testing/debugging).

        Self-Consistency check: validates against known message structure.

        Args:
            data: Raw message data dictionary.

        Returns:
            The classified input type.
        """
        # Check for media types in raw data
        for attr, input_type in self._ATTRIBUTE_TYPE_MAP:
            if attr in data and data[attr] is not None:
                return input_type

        # Check for text
        text = data.get("text")
        if text:
            return self._classify_text(text)

        if data.get("caption"):
            return InputType.TEXT

        return InputType.UNKNOWN
