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
        assert client.timeout == 60.0

    def test_init_with_custom_urls(self) -> None:
        """Test client initialization with custom URLs."""
        client = InternalServiceClient(
            nlp_service_url="https://custom-nlp.example.com",
            asr_service_url="https://custom-asr.example.com",
            ocr_service_url="https://custom-ocr.example.com",
            timeout=30.0,
        )

        assert client.nlp_url == "https://custom-nlp.example.com"
        assert client.asr_url == "https://custom-asr.example.com"
        assert client.ocr_url == "https://custom-ocr.example.com"
        assert client.timeout == 30.0

    def test_get_auth_headers_without_token(self) -> None:
        """Test auth headers when token fetch fails."""
        client = InternalServiceClient()

        # Mock token fetch to fail
        with patch.object(
            client,
            "_get_identity_token",
            side_effect=Exception("No credentials"),
        ):
            headers = client._get_auth_headers("https://example.com")

        # Should return headers without Authorization when token fails
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

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
                "_get_auth_headers",
                return_value={"Authorization": "Bearer test"},
            ),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.return_value = mock_response
            result = await client.call_nlp_service("Hello world")

        assert result == mock_nlp_response

    @pytest.mark.asyncio
    async def test_call_nlp_service_error(self) -> None:
        """Test NLP service call with HTTP error."""
        client = InternalServiceClient()

        with (
            patch.object(
                client,
                "_get_auth_headers",
                return_value={"Authorization": "Bearer test"},
            ),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

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
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.return_value = mock_response
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
            patch.object(client, "_get_identity_token", return_value="test_token"),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.return_value = mock_response
            result = await client.call_ocr_service(
                file_content=b"fake image",
                filename="test.jpg",
                mime_type="image/jpeg",
            )

        assert result == mock_ocr_response

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test health check for all services."""
        client = InternalServiceClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        with (
            patch.object(
                client,
                "_get_auth_headers",
                return_value={"Authorization": "Bearer test"},
            ),
            patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get,
        ):
            mock_get.return_value = mock_response
            result = await client.health_check()

        assert "nlp" in result
        assert "asr" in result
        assert "ocr" in result

    @pytest.mark.asyncio
    async def test_health_check_partial_failure(self) -> None:
        """Test health check when some services are unavailable."""
        client = InternalServiceClient()

        call_count = 0

        async def mock_get(*_args: Any, **_kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First service healthy
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {"status": "healthy"}
                return response
            else:
                # Other services fail
                raise httpx.ConnectError("Connection refused")

        with (
            patch.object(
                client,
                "_get_auth_headers",
                return_value={"Authorization": "Bearer test"},
            ),
            patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get_method,
        ):
            mock_get_method.side_effect = mock_get
            result = await client.health_check()

        # Should have results for all services (some healthy, some error)
        assert len(result) == 3


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
