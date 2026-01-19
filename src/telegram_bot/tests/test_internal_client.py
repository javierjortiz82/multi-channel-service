"""Tests for the internal service client."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from telegram_bot.services.internal_client import InternalServiceClient, get_client


@pytest.fixture
def mock_nlp_response() -> dict[str, Any]:
    """Mock NLP service response."""
    return {
        "response": "This is the NLP response.",
        "model": "gemini-2.0-flash",
        "input_length": 20,
        "output_length": 28,
    }


@pytest.fixture
def mock_asr_response() -> dict[str, Any]:
    """Mock ASR service response."""
    return {
        "text": "Transcribed audio text",
        "confidence": 0.95,
        "language": "en",
        "duration": 5.5,
    }


@pytest.fixture
def mock_analyze_response() -> dict[str, Any]:
    """Mock analyze service response."""
    return {
        "result": "Extracted text from image",
        "classification": {
            "predicted_type": "document",
            "confidence": 0.98,
        },
        "ocr_result": {
            "text": "Extracted text from image",
            "confidence": 0.98,
        },
    }


@pytest.fixture
def mock_image_search_response() -> dict[str, Any]:
    """Mock image similarity search response."""
    return {
        "found": True,
        "count": 2,
        "products": [
            {
                "sku": "TECH-001",
                "name": "Mechanical Keyboard",
                "description": "RGB gaming keyboard with blue switches",
                "category": "Electronics",
                "brand": "Logitech",
                "price": 149.99,
                "image_url": "https://example.com/keyboard.jpg",
                "similarity": 0.85,
            },
            {
                "sku": "TECH-002",
                "name": "Wireless Keyboard",
                "description": "Bluetooth keyboard with quiet keys",
                "category": "Electronics",
                "brand": "Microsoft",
                "price": 79.99,
                "image_url": None,
                "similarity": 0.72,
            },
        ],
    }


@pytest.fixture
def mock_embedding() -> list[float]:
    """Mock 1536-dimensional embedding vector."""
    return [0.1] * 1536


class TestInternalServiceClient:
    """Tests for InternalServiceClient class."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default URLs."""
        client = InternalServiceClient()

        assert "nlp-service" in client.nlp_url
        assert "asr-service" in client.asr_url
        assert "ocr-service" in client.ocr_url
        assert "mcp-server" in client.mcp_url

    def test_init_with_custom_urls(self) -> None:
        """Test client initialization with custom URLs."""
        client = InternalServiceClient(
            nlp_service_url="https://custom-nlp.example.com",
            asr_service_url="https://custom-asr.example.com",
            ocr_service_url="https://custom-ocr.example.com",
            mcp_service_url="https://custom-mcp.example.com",
        )

        assert client.nlp_url == "https://custom-nlp.example.com"
        assert client.asr_url == "https://custom-asr.example.com"
        assert client.ocr_url == "https://custom-ocr.example.com"
        assert client.mcp_url == "https://custom-mcp.example.com"

    @pytest.mark.asyncio
    async def test_call_nlp_service_success(
        self,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test successful NLP service call."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_nlp_response
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = mock_response
            result = await client.call_nlp_service("Hello world")

        assert result == mock_nlp_response

    @pytest.mark.asyncio
    async def test_call_nlp_service_with_detected_language(
        self,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test NLP service call with detected_language from ASR."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_nlp_response
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = mock_response
            result = await client.call_nlp_service(
                "Hello world",
                conversation_id="12345",
                user_info={"channel": "telegram", "external_id": "987"},
                detected_language="en",
            )

            # Verify detected_language was included in payload
            call_args = mock_request.call_args
            payload = call_args.kwargs.get("json", {})
            assert payload.get("detected_language") == "en"
            assert payload.get("text") == "Hello world"
            assert payload.get("conversation_id") == "12345"

        assert result == mock_nlp_response

    @pytest.mark.asyncio
    async def test_call_nlp_service_error(self) -> None:
        """Test NLP service call with HTTP error."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                await client.call_nlp_service("Hello world")

    @pytest.mark.asyncio
    async def test_call_asr_service_success(
        self,
        mock_asr_response: dict[str, Any],
    ) -> None:
        """Test successful ASR service call."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_asr_response
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = mock_response
            result = await client.call_asr_service(
                audio_content=b"fake audio",
                filename="test.ogg",
            )

        assert result == mock_asr_response

    @pytest.mark.asyncio
    async def test_call_analyze_service_success(
        self,
        mock_analyze_response: dict[str, Any],
    ) -> None:
        """Test successful analyze service call."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_analyze_response
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = mock_response
            result = await client.call_analyze_service(
                file_content=b"fake image",
                filename="test.jpg",
                mime_type="image/jpeg",
            )

        assert result == mock_analyze_response

    @pytest.mark.asyncio
    async def test_search_products_by_embedding_success(
        self,
        mock_image_search_response: dict[str, Any],
        mock_embedding: list[float],
    ) -> None:
        """Test successful image similarity search."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_image_search_response
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = mock_response
            result = await client.search_products_by_embedding(
                embedding=mock_embedding,
                limit=5,
                max_distance=0.5,
            )

        assert result["found"] is True
        assert result["count"] == 2
        assert len(result["products"]) == 2
        assert result["products"][0]["sku"] == "TECH-001"
        assert result["products"][0]["similarity"] == 0.85

    @pytest.mark.asyncio
    async def test_search_products_by_embedding_not_found(
        self,
        mock_embedding: list[float],
    ) -> None:
        """Test image search when no products are found."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "found": False,
            "count": 0,
            "products": [],
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.return_value = mock_response
            result = await client.search_products_by_embedding(
                embedding=mock_embedding,
            )

        assert result["found"] is False
        assert result["count"] == 0
        assert result["products"] == []

    @pytest.mark.asyncio
    async def test_search_products_by_embedding_error(
        self,
        mock_embedding: list[float],
    ) -> None:
        """Test image search with HTTP error."""
        client = InternalServiceClient()

        with (
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch.object(
                client, "_request_with_retry", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_request.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

            with pytest.raises(httpx.HTTPStatusError):
                await client.search_products_by_embedding(embedding=mock_embedding)


class TestGetClient:
    """Tests for get_client singleton function."""

    def test_get_client_singleton(self) -> None:
        """Test that get_client returns the same instance."""
        # Reset singleton for test
        import telegram_bot.services.internal_client as module

        module._client = None

        client1 = get_client()
        client2 = get_client()

        assert client1 is client2

    def test_get_client_returns_instance(self) -> None:
        """Test that get_client returns an InternalServiceClient."""
        import telegram_bot.services.internal_client as module

        module._client = None

        client = get_client()

        assert isinstance(client, InternalServiceClient)
