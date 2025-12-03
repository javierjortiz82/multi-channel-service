"""End-to-end tests for the webhook endpoint."""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestWebhookEndpoint:
    """E2E tests for webhook endpoint."""

    def test_webhook_without_secret_returns_401(
        self, client: TestClient, sample_text_update: dict[str, Any]
    ) -> None:
        """Test webhook rejects requests without secret token."""
        response = client.post("/webhook", json=sample_text_update)
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid secret token"

    def test_webhook_with_invalid_secret_returns_401(
        self, client: TestClient, sample_text_update: dict[str, Any]
    ) -> None:
        """Test webhook rejects requests with invalid secret token."""
        response = client.post(
            "/webhook",
            json=sample_text_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid secret token"

    def test_webhook_text_message_returns_ok(
        self, client: TestClient, sample_text_update: dict[str, Any]
    ) -> None:
        """Test webhook processes text message and returns 200."""
        response = client.post(
            "/webhook",
            json=sample_text_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_webhook_photo_message_returns_ok(
        self, client: TestClient, sample_photo_update: dict[str, Any]
    ) -> None:
        """Test webhook processes photo message and returns 200."""
        response = client.post(
            "/webhook",
            json=sample_photo_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_webhook_command_message_returns_ok(
        self, client: TestClient, sample_command_update: dict[str, Any]
    ) -> None:
        """Test webhook processes command message and returns 200."""
        response = client.post(
            "/webhook",
            json=sample_command_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_webhook_document_message_returns_ok(
        self, client: TestClient, sample_document_update: dict[str, Any]
    ) -> None:
        """Test webhook processes document message and returns 200."""
        response = client.post(
            "/webhook",
            json=sample_document_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_webhook_location_message_returns_ok(
        self, client: TestClient, sample_location_update: dict[str, Any]
    ) -> None:
        """Test webhook processes location message and returns 200."""
        response = client.post(
            "/webhook",
            json=sample_location_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestWebhookEndpointAsync:
    """Async E2E tests for webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_async_text_message(
        self, async_client: AsyncClient, sample_text_update: dict[str, Any]
    ) -> None:
        """Test async webhook processing for text message."""
        response = await async_client.post(
            "/webhook",
            json=sample_text_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_webhook_async_photo_message(
        self, async_client: AsyncClient, sample_photo_update: dict[str, Any]
    ) -> None:
        """Test async webhook processing for photo message."""
        response = await async_client.post(
            "/webhook",
            json=sample_photo_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestWebhookInputClassification:
    """Tests verifying correct input classification through webhook.

    Note: These tests use async with a small delay to allow background
    tasks to complete before checking log output.
    """

    @pytest.mark.asyncio
    async def test_text_message_logs_text_type(
        self,
        async_client: AsyncClient,
        sample_text_update: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that text message is correctly classified and logged with content."""
        with caplog.at_level("INFO"):
            await async_client.post(
                "/webhook",
                json=sample_text_update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
            )
            await asyncio.sleep(0.1)  # Wait for background task
        assert "[INPUT TYPE] text | content:" in caplog.text
        assert "Hello, bot!" in caplog.text

    @pytest.mark.asyncio
    async def test_photo_message_logs_photo_type(
        self,
        async_client: AsyncClient,
        sample_photo_update: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that photo message is correctly classified and logged."""
        with caplog.at_level("INFO"):
            await async_client.post(
                "/webhook",
                json=sample_photo_update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
            )
            await asyncio.sleep(0.1)  # Wait for background task
        assert "[INPUT TYPE] photo" in caplog.text

    @pytest.mark.asyncio
    async def test_command_message_logs_command_type(
        self,
        async_client: AsyncClient,
        sample_command_update: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that command message is correctly classified and logged."""
        with caplog.at_level("INFO"):
            await async_client.post(
                "/webhook",
                json=sample_command_update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
            )
            await asyncio.sleep(0.1)  # Wait for background task
        assert "[INPUT TYPE] command" in caplog.text

    @pytest.mark.asyncio
    async def test_document_message_logs_document_type(
        self,
        async_client: AsyncClient,
        sample_document_update: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that document message is correctly classified and logged."""
        with caplog.at_level("INFO"):
            await async_client.post(
                "/webhook",
                json=sample_document_update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
            )
            await asyncio.sleep(0.1)  # Wait for background task
        assert "[INPUT TYPE] document" in caplog.text

    @pytest.mark.asyncio
    async def test_location_message_logs_location_type(
        self,
        async_client: AsyncClient,
        sample_location_update: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that location message is correctly classified and logged."""
        with caplog.at_level("INFO"):
            await async_client.post(
                "/webhook",
                json=sample_location_update,
                headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-token"},
            )
            await asyncio.sleep(0.1)  # Wait for background task
        assert "[INPUT TYPE] location" in caplog.text


class TestWebhookIPFiltering:
    """Integration tests for webhook IP filtering."""

    def test_ip_filter_allows_telegram_ip_via_x_forwarded_for(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that valid Telegram IP in X-Forwarded-For is allowed."""
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Forwarded-For": "149.154.160.1",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ip_filter_allows_telegram_ip_range_2(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that valid Telegram IP from second range is allowed."""
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Forwarded-For": "91.108.4.1",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ip_filter_blocks_non_telegram_ip(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that non-Telegram IP is blocked with 403."""
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Forwarded-For": "8.8.8.8",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    def test_ip_filter_blocks_private_ip(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that private IP is blocked with 403."""
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Forwarded-For": "192.168.1.1",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    def test_ip_filter_uses_first_ip_from_x_forwarded_for(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that only first IP in X-Forwarded-For is checked."""
        # First IP is Telegram, should pass
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Forwarded-For": "149.154.160.1, 10.0.0.1, 8.8.8.8",
            },
        )
        assert response.status_code == 200

    def test_ip_filter_blocks_spoofed_header(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that spoofed X-Forwarded-For with non-Telegram first IP is blocked."""
        # First IP is not Telegram, should fail even if later IPs are
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Forwarded-For": "8.8.8.8, 149.154.160.1",
            },
        )
        assert response.status_code == 403

    def test_ip_filter_allows_via_x_real_ip(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that valid Telegram IP in X-Real-IP is allowed."""
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Real-IP": "149.154.167.100",
            },
        )
        assert response.status_code == 200

    def test_ip_filter_disabled_allows_any_ip(
        self,
        client: TestClient,  # Uses settings with IP filter disabled
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that disabled IP filter allows any IP."""
        response = client.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "test-secret-token",
                "X-Forwarded-For": "8.8.8.8",  # Non-Telegram IP
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ip_filter_check_before_secret_token(
        self,
        client_with_ip_filter: TestClient,
        sample_text_update: dict[str, Any],
    ) -> None:
        """Test that IP filter is checked before secret token validation."""
        # Invalid IP without secret token - should get 403 (IP blocked), not 401
        response = client_with_ip_filter.post(
            "/webhook",
            json=sample_text_update,
            headers={
                "X-Forwarded-For": "8.8.8.8",
                # No secret token header
            },
        )
        assert response.status_code == 403  # IP blocked first
