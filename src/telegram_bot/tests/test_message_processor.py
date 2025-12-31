"""Tests for the message processor service."""

import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_bot.services.input_classifier import InputType
from telegram_bot.services.message_processor import (
    MessageProcessor,
    ProcessingResult,
    ProcessingStatus,
)


@pytest.fixture
def mock_nlp_response() -> dict[str, Any]:
    """Mock NLP service response."""
    return {
        "response": "Hello! I'm doing well, thank you for asking.",
        "model": "gemini-2.0-flash",
        "input_length": 20,
        "output_length": 45,
    }


@pytest.fixture
def mock_asr_response() -> dict[str, Any]:
    """Mock ASR service response."""
    return {
        "text": "Hello, how are you?",
        "confidence": 0.95,
        "language": "en",
    }


@pytest.fixture
def mock_ocr_response() -> dict[str, Any]:
    """Mock OCR service response."""
    return {
        "text": "Invoice #12345\nTotal: $100.00",
        "confidence": 0.98,
    }


@pytest.fixture
def mock_bot() -> MagicMock:
    """Create a mock Bot instance."""
    bot = MagicMock()

    # Mock file download
    mock_file = MagicMock()
    mock_file.file_path = "voice/file_123.ogg"
    bot.get_file = AsyncMock(return_value=mock_file)

    # Mock download_file to return bytes
    mock_bytes = io.BytesIO(b"fake audio content")
    bot.download_file = AsyncMock(return_value=mock_bytes)

    return bot


@pytest.fixture
def mock_text_message() -> MagicMock:
    """Create a mock text message."""
    message = MagicMock()
    message.chat.id = 123456789
    message.text = "Hello, how are you?"
    message.from_user.id = 987654321
    message.from_user.language_code = "en"
    return message


@pytest.fixture
def mock_voice_message() -> MagicMock:
    """Create a mock voice message."""
    message = MagicMock()
    message.chat.id = 123456789
    message.text = None
    message.voice = MagicMock()
    message.voice.file_id = "voice_file_123"
    message.audio = None
    message.photo = None
    message.from_user.id = 987654321
    message.from_user.language_code = "es"
    return message


@pytest.fixture
def mock_photo_message() -> MagicMock:
    """Create a mock photo message."""
    message = MagicMock()
    message.chat.id = 123456789
    message.text = None
    message.voice = None
    message.audio = None
    message.photo = [
        MagicMock(file_id="photo_small", width=100, height=100),
        MagicMock(file_id="photo_large", width=800, height=600),
    ]
    message.from_user.id = 987654321
    message.from_user.language_code = "en"
    return message


class TestProcessingResult:
    """Tests for ProcessingResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a success result."""
        result = ProcessingResult(
            status=ProcessingStatus.SUCCESS,
            response="Test response",
            input_type=InputType.TEXT,
            raw_response={"key": "value"},
        )
        assert result.status == ProcessingStatus.SUCCESS
        assert result.response == "Test response"
        assert result.input_type == InputType.TEXT
        assert result.raw_response == {"key": "value"}
        assert result.error is None

    def test_error_result(self) -> None:
        """Test creating an error result."""
        result = ProcessingResult(
            status=ProcessingStatus.ERROR,
            response="Error message",
            input_type=InputType.TEXT,
            error="Connection failed",
        )
        assert result.status == ProcessingStatus.ERROR
        assert result.error == "Connection failed"


class TestMessageProcessor:
    """Tests for MessageProcessor class."""

    @pytest.mark.asyncio
    async def test_process_text_success(
        self,
        mock_text_message: MagicMock,
        mock_bot: MagicMock,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test successful text processing."""
        processor = MessageProcessor()

        with patch.object(
            processor._client,
            "call_nlp_service",
            new_callable=AsyncMock,
            return_value=mock_nlp_response,
        ):
            result = await processor.process_message(
                mock_text_message, InputType.TEXT, mock_bot
            )

        assert result.status == ProcessingStatus.SUCCESS
        assert result.response == mock_nlp_response["response"]
        assert result.input_type == InputType.TEXT

    @pytest.mark.asyncio
    async def test_process_text_empty(
        self,
        mock_bot: MagicMock,
    ) -> None:
        """Test processing empty text message."""
        message = MagicMock()
        message.chat.id = 123456789
        message.text = None

        processor = MessageProcessor()
        result = await processor.process_message(message, InputType.TEXT, mock_bot)

        assert result.status == ProcessingStatus.NO_CONTENT
        assert "texto" in result.response.lower()

    @pytest.mark.asyncio
    async def test_process_text_nlp_error(
        self,
        mock_text_message: MagicMock,
        mock_bot: MagicMock,
    ) -> None:
        """Test text processing with NLP service error."""
        processor = MessageProcessor()

        with patch.object(
            processor._client,
            "call_nlp_service",
            new_callable=AsyncMock,
            side_effect=Exception("NLP service unavailable"),
        ):
            result = await processor.process_message(
                mock_text_message, InputType.TEXT, mock_bot
            )

        assert result.status == ProcessingStatus.ERROR
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_process_voice_success(
        self,
        mock_voice_message: MagicMock,
        mock_bot: MagicMock,
        mock_asr_response: dict[str, Any],
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test successful voice message processing."""
        processor = MessageProcessor()

        with (
            patch.object(
                processor._client,
                "call_asr_service",
                new_callable=AsyncMock,
                return_value=mock_asr_response,
            ),
            patch.object(
                processor._client,
                "call_nlp_service",
                new_callable=AsyncMock,
                return_value=mock_nlp_response,
            ),
        ):
            result = await processor.process_message(
                mock_voice_message, InputType.VOICE, mock_bot
            )

        assert result.status == ProcessingStatus.SUCCESS
        assert result.response == mock_nlp_response["response"]
        assert result.raw_response is not None
        assert "transcribed_text" in result.raw_response

    @pytest.mark.asyncio
    async def test_process_voice_asr_error(
        self,
        mock_voice_message: MagicMock,
        mock_bot: MagicMock,
    ) -> None:
        """Test voice processing with ASR service error."""
        processor = MessageProcessor()

        with patch.object(
            processor._client,
            "call_asr_service",
            new_callable=AsyncMock,
            side_effect=Exception("ASR service unavailable"),
        ):
            result = await processor.process_message(
                mock_voice_message, InputType.VOICE, mock_bot
            )

        assert result.status == ProcessingStatus.ERROR
        assert "audio" in result.response.lower()

    @pytest.mark.asyncio
    async def test_process_photo_success(
        self,
        mock_photo_message: MagicMock,
        mock_bot: MagicMock,
        mock_ocr_response: dict[str, Any],
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test successful photo message processing."""
        processor = MessageProcessor()

        # Mock file download for photo
        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        with (
            patch.object(
                processor._client,
                "call_ocr_service",
                new_callable=AsyncMock,
                return_value=mock_ocr_response,
            ),
            patch.object(
                processor._client,
                "call_nlp_service",
                new_callable=AsyncMock,
                return_value=mock_nlp_response,
            ),
        ):
            result = await processor.process_message(
                mock_photo_message, InputType.PHOTO, mock_bot
            )

        assert result.status == ProcessingStatus.SUCCESS
        assert result.response == mock_nlp_response["response"]

    @pytest.mark.asyncio
    async def test_process_photo_no_text(
        self,
        mock_photo_message: MagicMock,
        mock_bot: MagicMock,
    ) -> None:
        """Test photo processing when OCR finds no text."""
        processor = MessageProcessor()

        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        with patch.object(
            processor._client,
            "call_ocr_service",
            new_callable=AsyncMock,
            return_value={"text": ""},
        ):
            result = await processor.process_message(
                mock_photo_message, InputType.PHOTO, mock_bot
            )

        assert result.status == ProcessingStatus.SUCCESS
        assert "imagen" in result.response.lower()

    @pytest.mark.asyncio
    async def test_process_unsupported_type(
        self,
        mock_bot: MagicMock,
    ) -> None:
        """Test processing unsupported message type."""
        message = MagicMock()
        message.chat.id = 123456789

        processor = MessageProcessor()
        result = await processor.process_message(message, InputType.STICKER, mock_bot)

        assert result.status == ProcessingStatus.UNSUPPORTED
        assert "no está soportado" in result.response.lower()

    @pytest.mark.asyncio
    async def test_process_command_returns_empty(
        self,
        mock_bot: MagicMock,
    ) -> None:
        """Test that commands return empty response (handled by command handlers)."""
        message = MagicMock()
        message.chat.id = 123456789
        message.text = "/start"

        processor = MessageProcessor()
        result = await processor.process_message(message, InputType.COMMAND, mock_bot)

        assert result.status == ProcessingStatus.SUCCESS
        assert result.response == ""

    @pytest.mark.asyncio
    async def test_process_text_directly(
        self,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test processing text directly without message wrapper."""
        processor = MessageProcessor()

        with patch.object(
            processor._client,
            "call_nlp_service",
            new_callable=AsyncMock,
            return_value=mock_nlp_response,
        ):
            result = await processor.process_text("Hello world")

        assert result.status == ProcessingStatus.SUCCESS
        assert result.response == mock_nlp_response["response"]


class TestProcessingStatus:
    """Tests for ProcessingStatus enum."""

    def test_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert ProcessingStatus.SUCCESS.value == "success"
        assert ProcessingStatus.ERROR.value == "error"
        assert ProcessingStatus.UNSUPPORTED.value == "unsupported"
        assert ProcessingStatus.NO_CONTENT.value == "no_content"
