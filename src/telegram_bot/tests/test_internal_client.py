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
        "data": {
            "transcription": "Transcribed audio text",
            "confidence": 0.95,
            "language": "en",
        },
        "success": True,
    }


@pytest.fixture
def mock_ocr_response() -> dict[str, Any]:
    """Mock OCR service response."""
    return {
        "text": "Extracted text from image",
        "confidence": 0.98,
        "pages": 1,
    }


class TestInternalServiceClient:
    """Tests for InternalServiceClient class."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default URLs."""
        client = InternalServiceClient()

        assert "nlp-service" in client.nlp_url
        assert "asr-service" in client.asr_url
        assert "ocr-service" in client.ocr_url

    def test_init_with_custom_urls(self) -> None:
        """Test client initialization with custom URLs."""
        client = InternalServiceClient(
            nlp_service_url="https://custom-nlp.example.com",
            asr_service_url="https://custom-asr.example.com",
            ocr_service_url="https://custom-ocr.example.com",
        )

        assert client.nlp_url == "https://custom-nlp.example.com"
        assert client.asr_url == "https://custom-asr.example.com"
        assert client.ocr_url == "https://custom-ocr.example.com"

    @pytest.mark.asyncio
    async def test_get_identity_token_caching(self) -> None:
        """Test that identity tokens are cached."""
        client = InternalServiceClient()

        with patch.object(
            client,
            "_fetch_token_sync",
            return_value="test_token_123",
        ):
            # First call - should fetch new token
            token1 = await client._get_identity_token("https://example.com")
            # Second call - should use cached token
            token2 = await client._get_identity_token("https://example.com")

        assert token1 == "test_token_123"
        assert token2 == "test_token_123"

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
            patch.object(
                client,
                "_get_identity_token",
                new_callable=AsyncMock,
                return_value="test_token",
            ),
            patch.object(
                client,
                "_request_with_retry",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            result = await client.call_nlp_service("Hello world")

        assert result == mock_nlp_response

    @pytest.mark.asyncio
    async def test_call_nlp_service_with_embedding(
        self,
        mock_nlp_response: dict[str, Any],
    ) -> None:
        """Test NLP service call with image embedding for visual search."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_nlp_response
        mock_response.raise_for_status = MagicMock()

        # Create a mock embedding (1536 dimensions)
        mock_embedding = [0.1] * 1536

        with (
            patch.object(
                client,
                "_get_identity_token",
                new_callable=AsyncMock,
                return_value="test_token",
            ),
            patch.object(
                client,
                "_request_with_retry",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_request,
        ):
            result = await client.call_nlp_service(
                "Find similar products",
                conversation_id="12345",
                image_embedding=mock_embedding,
                image_description="laptop HP silver",
            )

        # Verify the embedding was included in the payload
        call_args = mock_request.call_args
        json_payload = call_args.kwargs.get("json", {})
        assert json_payload.get("image_embedding") == mock_embedding
        assert json_payload.get("image_description") == "laptop HP silver"
        assert result == mock_nlp_response

    @pytest.mark.asyncio
    async def test_call_nlp_service_error(self) -> None:
        """Test NLP service call with HTTP error."""
        client = InternalServiceClient()

        with (
            patch.object(
                client,
                "_get_identity_token",
                new_callable=AsyncMock,
                return_value="test_token",
            ),
            patch.object(
                client,
                "_request_with_retry",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError(
                    "Server error",
                    request=MagicMock(),
                    response=MagicMock(status_code=500),
                ),
            ),
            pytest.raises(httpx.HTTPStatusError),
        ):
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
            patch.object(
                client,
                "_get_identity_token",
                new_callable=AsyncMock,
                return_value="test_token",
            ),
            patch.object(
                client,
                "_request_with_retry",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            result = await client.call_asr_service(
                audio_content=b"fake audio",
                filename="test.ogg",
                language_hint="en",
            )

        assert result == mock_asr_response

    @pytest.mark.asyncio
    async def test_call_ocr_service_success(
        self,
        mock_ocr_response: dict[str, Any],
    ) -> None:
        """Test successful OCR service call."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_ocr_response
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(
                client,
                "_get_identity_token",
                new_callable=AsyncMock,
                return_value="test_token",
            ),
            patch.object(
                client,
                "_request_with_retry",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            result = await client.call_ocr_service(
                file_content=b"fake image",
                filename="test.jpg",
                mime_type="image/jpeg",
            )

        assert result == mock_ocr_response

    @pytest.mark.asyncio
    async def test_call_analyze_service_success(self) -> None:
        """Test successful analyze service call."""
        client = InternalServiceClient()

        mock_analyze_response = {
            "classification": {"predicted_type": "object", "confidence": 0.95},
            "detection_result": {"objects": [{"name": "laptop"}]},
            "image_embedding": [0.1] * 1536,
            "image_description": "A laptop on a desk",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_analyze_response
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(
                client,
                "_get_identity_token",
                new_callable=AsyncMock,
                return_value="test_token",
            ),
            patch.object(
                client,
                "_request_with_retry",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            result = await client.call_analyze_service(
                file_content=b"fake image",
                filename="test.jpg",
                mode="auto",
            )

        assert result["classification"]["predicted_type"] == "object"
        assert "image_embedding" in result

    @pytest.mark.asyncio
    async def test_warmup_fetches_tokens(self) -> None:
        """Test that warmup pre-fetches tokens for all services."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch.object(
                client,
                "_get_identity_token",
                new_callable=AsyncMock,
                return_value="test_token",
            ) as mock_get_token,
            patch.object(
                client,
                "_get_http_client",
                new_callable=AsyncMock,
            ) as mock_get_client,
        ):
            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = mock_response
            mock_get_client.return_value = mock_http_client

            await client.warmup()

        # Should have fetched tokens for all 3 services
        assert mock_get_token.call_count == 3

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self) -> None:
        """Test that close properly closes the HTTP client."""
        client = InternalServiceClient()

        # Create a mock HTTP client
        mock_http_client = AsyncMock()
        client._http_client = mock_http_client

        await client.close()

        mock_http_client.aclose.assert_called_once()
        assert client._http_client is None


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
