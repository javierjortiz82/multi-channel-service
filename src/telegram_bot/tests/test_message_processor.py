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
    Product,
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
        "success": True,
        "data": {
            "transcription": "Hello, how are you?",
            "confidence": 0.95,
            "language": "en",
        },
    }


@pytest.fixture
def mock_analyze_response() -> dict[str, Any]:
    """Mock analyze service response."""
    return {
        "result": "Invoice #12345\nTotal: $100.00",
        "classification": {
            "predicted_type": "document",
            "confidence": 0.98,
        },
        "ocr_result": {
            "text": "Invoice #12345\nTotal: $100.00",
            "confidence": 0.98,
        },
    }


@pytest.fixture
def mock_analyze_object_response() -> dict[str, Any]:
    """Mock analyze service response for object detection with embedding."""
    return {
        "result": "keyboard",
        "classification": {
            "predicted_type": "object",
            "confidence": 0.92,
        },
        "detection_result": {
            "objects": [{"name": "keyboard", "confidence": 0.92}],
        },
        "image_embedding": [0.1] * 1536,  # 1536-dim vector
        "image_description": "Black mechanical keyboard with RGB lighting",
    }


@pytest.fixture
def mock_image_search_response() -> dict[str, Any]:
    """Mock image similarity search response."""
    return {
        "found": True,
        "count": 2,
        "has_exact_match": False,
        "products": [
            {
                "sku": "TECH-001",
                "name": "Mechanical Keyboard RGB",
                "description": "Gaming keyboard with blue switches",
                "category": "Electronics",
                "brand": "Logitech",
                "price": 149.99,
                "image_url": "https://example.com/keyboard.jpg",
                "similarity": 0.85,
                "match_type": "similar",
            },
            {
                "sku": "TECH-002",
                "name": "Wireless Keyboard",
                "description": "Bluetooth keyboard",
                "category": "Electronics",
                "brand": "Microsoft",
                "price": 79.99,
                "image_url": "https://example.com/wireless.jpg",
                "similarity": 0.72,
                "match_type": "similar",
            },
        ],
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


class TestProduct:
    """Tests for Product dataclass."""

    def test_product_creation(self) -> None:
        """Test creating a product."""
        product = Product(
            sku="TECH-001",
            name="Mechanical Keyboard",
            brand="Logitech",
            description="RGB gaming keyboard",
            price=149.99,
            image_url="https://example.com/keyboard.jpg",
            similarity=0.85,
            match_type="exact",
        )
        assert product.sku == "TECH-001"
        assert product.name == "Mechanical Keyboard"
        assert product.brand == "Logitech"
        assert product.price == 149.99
        assert product.similarity == 0.85
        assert product.match_type == "exact"

    def test_product_optional_fields(self) -> None:
        """Test product with optional fields as None."""
        product = Product(
            sku="TECH-002",
            name="Basic Keyboard",
            brand=None,
            description=None,
            price=None,
            image_url=None,
            similarity=0.60,
            match_type="similar",
        )
        assert product.brand is None
        assert product.price is None
        assert product.image_url is None


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
        assert result.products is None

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

    def test_result_with_products(self) -> None:
        """Test creating a result with products."""
        cards = [
            Product(
                sku="TECH-001",
                name="Keyboard",
                brand="Logitech",
                description="Gaming keyboard",
                price=149.99,
                image_url="https://example.com/kb.jpg",
                similarity=0.85,
                match_type="exact",
            )
        ]
        result = ProcessingResult(
            status=ProcessingStatus.SUCCESS,
            response="Found products!",
            input_type=InputType.PHOTO,
            products=cards,
        )
        assert result.products is not None
        assert len(result.products) == 1
        assert result.products[0].name == "Keyboard"


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
    async def test_process_text_passes_telegram_language_code(
        self,
        mock_text_message: MagicMock,
        mock_bot: MagicMock,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test that text processing passes Telegram language_code as detected_language.

        After removing langdetect, the system relies on:
        1. Telegram's user.language_code as a fallback for error messages
        2. Gemini automatically detecting input language and responding accordingly

        The detected_language parameter is passed as a hint, but Gemini makes the
        final decision on which language to use based on the actual input text.
        """
        processor = MessageProcessor()

        # Set a specific language_code in the mock message
        mock_text_message.from_user.language_code = "es"

        with patch.object(
            processor._client,
            "call_nlp_service",
            new_callable=AsyncMock,
            return_value=mock_nlp_response,
        ) as mock_nlp_call:
            result = await processor.process_message(
                mock_text_message, InputType.TEXT, mock_bot
            )

            # Verify Telegram's language_code was passed as detected_language
            call_kwargs = mock_nlp_call.call_args.kwargs
            assert call_kwargs.get("detected_language") == "es"
            assert call_kwargs.get("conversation_id") == str(mock_text_message.chat.id)

        assert result.status == ProcessingStatus.SUCCESS

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
        assert "text" in result.response.lower()

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
    async def test_process_voice_passes_detected_language(
        self,
        mock_voice_message: MagicMock,
        mock_bot: MagicMock,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test that voice processing passes ASR detected language to NLP."""
        processor = MessageProcessor()

        # ASR response with detected language "en"
        asr_response_with_lang = {
            "success": True,
            "data": {
                "transcription": "Hello, how are you?",
                "confidence": 0.95,
                "language": "en",
            },
        }

        with (
            patch.object(
                processor._client,
                "call_asr_service",
                new_callable=AsyncMock,
                return_value=asr_response_with_lang,
            ),
            patch.object(
                processor._client,
                "call_nlp_service",
                new_callable=AsyncMock,
                return_value=mock_nlp_response,
            ) as mock_nlp_call,
        ):
            result = await processor.process_message(
                mock_voice_message, InputType.VOICE, mock_bot
            )

            # Verify detected_language was passed to NLP service
            call_kwargs = mock_nlp_call.call_args.kwargs
            assert call_kwargs.get("detected_language") == "en"

        assert result.status == ProcessingStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_process_voice_unknown_language_not_passed(
        self,
        mock_voice_message: MagicMock,
        mock_bot: MagicMock,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test that 'unknown' language from ASR is not passed to NLP."""
        processor = MessageProcessor()

        # ASR response with "unknown" language
        asr_response_unknown = {
            "success": True,
            "data": {
                "transcription": "Some text",
                "confidence": 0.80,
                "language": "unknown",
            },
        }

        with (
            patch.object(
                processor._client,
                "call_asr_service",
                new_callable=AsyncMock,
                return_value=asr_response_unknown,
            ),
            patch.object(
                processor._client,
                "call_nlp_service",
                new_callable=AsyncMock,
                return_value=mock_nlp_response,
            ) as mock_nlp_call,
        ):
            result = await processor.process_message(
                mock_voice_message, InputType.VOICE, mock_bot
            )

            # Verify detected_language is None (not "unknown")
            call_kwargs = mock_nlp_call.call_args.kwargs
            assert call_kwargs.get("detected_language") is None

        assert result.status == ProcessingStatus.SUCCESS

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
        mock_analyze_response: dict[str, Any],
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
                "call_analyze_service",
                new_callable=AsyncMock,
                return_value=mock_analyze_response,
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
        """Test photo processing when analyze finds no content."""
        processor = MessageProcessor()

        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        with patch.object(
            processor._client,
            "call_analyze_service",
            new_callable=AsyncMock,
            return_value={
                "result": "",
                "classification": {"predicted_type": "unknown", "confidence": 0.0},
            },
        ):
            result = await processor.process_message(
                mock_photo_message, InputType.PHOTO, mock_bot
            )

        assert result.status == ProcessingStatus.SUCCESS
        # Check for "image" (en) as mock user has language_code="en"
        assert "image" in result.response.lower()

    @pytest.mark.asyncio
    async def test_process_photo_with_image_similarity_search(
        self,
        mock_photo_message: MagicMock,
        mock_bot: MagicMock,
        mock_analyze_object_response: dict[str, Any],
        mock_image_search_response: dict[str, Any],
    ) -> None:
        """Test photo processing with exact product match (≥80% similarity)."""
        processor = MessageProcessor()

        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        with (
            patch.object(
                processor._client,
                "call_analyze_service",
                new_callable=AsyncMock,
                return_value=mock_analyze_object_response,
            ),
            patch.object(
                processor._client,
                "search_products_by_embedding",
                new_callable=AsyncMock,
                return_value=mock_image_search_response,
            ),
        ):
            result = await processor.process_message(
                mock_photo_message, InputType.PHOTO, mock_bot
            )

        assert result.status == ProcessingStatus.SUCCESS
        assert result.raw_response is not None
        assert result.raw_response.get("priority") == "exact_match"
        assert "image_search" in result.raw_response

        # Verify products includes ALL found products (exact + similar)
        assert result.products is not None
        assert len(result.products) == 2  # Both products included
        # First product is exact match
        assert result.products[0].sku == "TECH-001"
        assert result.products[0].name == "Mechanical Keyboard RGB"
        assert result.products[0].similarity == 0.85
        assert result.products[0].match_type == "exact"
        # Second product is similar
        assert result.products[1].sku == "TECH-002"
        assert result.products[1].match_type == "similar"

    @pytest.mark.asyncio
    async def test_process_photo_image_search_no_results(
        self,
        mock_photo_message: MagicMock,
        mock_bot: MagicMock,
        mock_analyze_object_response: dict[str, Any],
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test photo processing falls back to process_text when no exact match."""
        processor = MessageProcessor()

        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        with (
            patch.object(
                processor._client,
                "call_analyze_service",
                new_callable=AsyncMock,
                return_value=mock_analyze_object_response,
            ),
            patch.object(
                processor._client,
                "search_products_by_embedding",
                new_callable=AsyncMock,
                return_value={"found": False, "count": 0, "products": []},
            ),
            patch.object(
                processor._client,
                "call_nlp_service",
                new_callable=AsyncMock,
                return_value=mock_nlp_response,
            ) as mock_nlp,
        ):
            result = await processor.process_message(
                mock_photo_message, InputType.PHOTO, mock_bot
            )

        # Should fall back to priority 3: process object name as text
        assert result.status == ProcessingStatus.SUCCESS
        # NLP was called with the object name ("keyboard" from mock)
        mock_nlp.assert_called_once()
        call_args = mock_nlp.call_args
        assert call_args[0][0] == "keyboard"  # First positional arg is the text

    @pytest.mark.asyncio
    async def test_process_photo_image_search_error_fallback(
        self,
        mock_photo_message: MagicMock,
        mock_bot: MagicMock,
        mock_analyze_object_response: dict[str, Any],
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test photo processing falls back to process_text when search fails."""
        processor = MessageProcessor()

        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        with (
            patch.object(
                processor._client,
                "call_analyze_service",
                new_callable=AsyncMock,
                return_value=mock_analyze_object_response,
            ),
            patch.object(
                processor._client,
                "search_products_by_embedding",
                new_callable=AsyncMock,
                side_effect=Exception("MCP service unavailable"),
            ),
            patch.object(
                processor._client,
                "call_nlp_service",
                new_callable=AsyncMock,
                return_value=mock_nlp_response,
            ) as mock_nlp,
        ):
            result = await processor.process_message(
                mock_photo_message, InputType.PHOTO, mock_bot
            )

        # Should fall back to priority 3: process object name as text
        assert result.status == ProcessingStatus.SUCCESS
        # NLP was called with the object name ("keyboard" from mock)
        mock_nlp.assert_called_once()
        call_args = mock_nlp.call_args
        assert call_args[0][0] == "keyboard"  # First positional arg is the text

    @pytest.mark.asyncio
    async def test_process_photo_below_threshold_includes_products(
        self,
        mock_photo_message: MagicMock,
        mock_bot: MagicMock,
        mock_analyze_object_response: dict[str, Any],
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test that products below 80% are included with NLP response."""
        processor = MessageProcessor()

        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        # Mock response with similarity below 0.80 threshold
        below_threshold_response = {
            "found": True,
            "count": 1,
            "has_exact_match": False,
            "products": [
                {
                    "sku": "TECH-003",
                    "name": "Similar Keyboard",
                    "similarity": 0.70,  # Below 0.80 threshold
                    "match_type": "similar",
                    "image_url": "https://example.com/similar.jpg",
                }
            ],
        }

        with (
            patch.object(
                processor._client,
                "call_analyze_service",
                new_callable=AsyncMock,
                return_value=mock_analyze_object_response,
            ),
            patch.object(
                processor._client,
                "search_products_by_embedding",
                new_callable=AsyncMock,
                return_value=below_threshold_response,
            ),
            patch.object(
                processor._client,
                "call_nlp_service",
                new_callable=AsyncMock,
                return_value=mock_nlp_response,
            ) as mock_nlp,
        ):
            result = await processor.process_message(
                mock_photo_message, InputType.PHOTO, mock_bot
            )

        # Should include similar products
        assert result.products is not None
        assert len(result.products) == 1
        assert result.products[0].sku == "TECH-003"
        assert result.products[0].match_type == "similar"
        # NLP was called with the object name
        mock_nlp.assert_called_once()
        call_args = mock_nlp.call_args
        assert call_args[0][0] == "keyboard"
        # Priority should indicate text with similar products
        assert result.raw_response.get("priority") == "text_with_similar_products"

    @pytest.mark.asyncio
    async def test_process_photo_document_priority(
        self,
        mock_photo_message: MagicMock,
        mock_bot: MagicMock,
        mock_analyze_response: dict[str, Any],
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test that document photos use OCR priority over image search."""
        processor = MessageProcessor()

        mock_file = MagicMock()
        mock_file.file_path = "photos/file_123.jpg"
        mock_bot.get_file = AsyncMock(return_value=mock_file)
        mock_bot.download_file = AsyncMock(
            return_value=io.BytesIO(b"fake image content")
        )

        with (
            patch.object(
                processor._client,
                "call_analyze_service",
                new_callable=AsyncMock,
                return_value=mock_analyze_response,
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
        assert result.raw_response is not None
        assert result.raw_response.get("priority") == "document_ocr"

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
        assert "not supported" in result.response.lower()

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

    @pytest.mark.asyncio
    async def test_process_text_with_detected_language(
        self,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test processing text with detected_language parameter."""
        processor = MessageProcessor()

        with patch.object(
            processor._client,
            "call_nlp_service",
            new_callable=AsyncMock,
            return_value=mock_nlp_response,
        ) as mock_nlp_call:
            result = await processor.process_text(
                "Hello world",
                conversation_id="12345",
                user_info={"language_code": "es"},
                detected_language="en",
            )

            # Verify detected_language was passed to NLP service
            call_kwargs = mock_nlp_call.call_args.kwargs
            assert call_kwargs.get("detected_language") == "en"
            assert call_kwargs.get("conversation_id") == "12345"

        assert result.status == ProcessingStatus.SUCCESS


class TestProcessingStatus:
    """Tests for ProcessingStatus enum."""

    def test_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert ProcessingStatus.SUCCESS.value == "success"
        assert ProcessingStatus.ERROR.value == "error"
        assert ProcessingStatus.UNSUPPORTED.value == "unsupported"
        assert ProcessingStatus.NO_CONTENT.value == "no_content"
