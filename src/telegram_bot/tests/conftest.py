"""Test configuration and fixtures."""

import os
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from telegram_bot.app import create_app
from telegram_bot.config.settings import Settings


@pytest.fixture(scope="session", autouse=True)
def set_test_env() -> None:
    """Set test environment variables."""
    # Token format: numeric_id:alphanumeric (aiogram validates format)
    os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    os.environ["WEBHOOK_HOST"] = "https://test.example.com"
    os.environ["WEBHOOK_PATH"] = "/webhook"
    os.environ["WEBHOOK_SECRET"] = "test-secret-token"
    os.environ["WEBHOOK_IP_FILTER_ENABLED"] = "false"  # Disabled for most tests
    os.environ["ENVIRONMENT"] = "development"
    os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture
def settings() -> Settings:
    """Create test settings with IP filter disabled."""
    return Settings(
        # Token format: numeric_id:alphanumeric (aiogram validates format)
        telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        webhook_host="https://test.example.com",
        webhook_path="/webhook",
        webhook_secret="test-secret-token",
        webhook_ip_filter_enabled=False,  # Disabled for normal tests
        environment="development",
        log_level="DEBUG",
    )


@pytest.fixture
def settings_with_ip_filter() -> Settings:
    """Create test settings with IP filter enabled."""
    return Settings(
        telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        webhook_host="https://test.example.com",
        webhook_path="/webhook",
        webhook_secret="test-secret-token",
        webhook_ip_filter_enabled=True,  # Enabled for security tests
        environment="development",
        log_level="DEBUG",
    )


@pytest.fixture
def app(settings: Settings) -> Any:
    """Create test FastAPI application."""
    test_app = create_app(settings)

    # Mock the bot methods to avoid real Telegram API calls
    test_app.state.bot.set_webhook = AsyncMock()
    test_app.state.bot.delete_webhook = AsyncMock()
    test_app.state.bot.session.close = AsyncMock()

    return test_app


@pytest.fixture
def app_with_ip_filter(settings_with_ip_filter: Settings) -> Any:
    """Create test FastAPI application with IP filter enabled."""
    test_app = create_app(settings_with_ip_filter)

    # Mock the bot methods to avoid real Telegram API calls
    test_app.state.bot.set_webhook = AsyncMock()
    test_app.state.bot.delete_webhook = AsyncMock()
    test_app.state.bot.session.close = AsyncMock()

    return test_app


@pytest.fixture
def client(app: Any) -> TestClient:
    """Create synchronous test client."""
    return TestClient(app)


@pytest.fixture
def client_with_ip_filter(app_with_ip_filter: Any) -> TestClient:
    """Create synchronous test client with IP filter enabled."""
    return TestClient(app_with_ip_filter)


@pytest.fixture
async def async_client(app: Any) -> AsyncIterator[AsyncClient]:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_message() -> MagicMock:
    """Create a mock Telegram message."""
    message = MagicMock()
    message.chat.id = 123456789
    message.from_user.id = 987654321
    message.from_user.username = "testuser"
    message.text = None
    message.caption = None
    message.photo = None
    message.document = None
    message.video = None
    message.audio = None
    message.voice = None
    message.video_note = None
    message.sticker = None
    message.animation = None
    message.location = None
    message.venue = None
    message.contact = None
    message.poll = None
    message.dice = None
    return message


@pytest.fixture
def sample_text_update() -> dict[str, Any]:
    """Sample Telegram text message update."""
    return {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
            },
            "chat": {
                "id": 987654321,
                "first_name": "Test",
                "username": "testuser",
                "type": "private",
            },
            "date": 1234567890,
            "text": "Hello, bot!",
        },
    }


@pytest.fixture
def sample_photo_update() -> dict[str, Any]:
    """Sample Telegram photo message update."""
    return {
        "update_id": 123456790,
        "message": {
            "message_id": 2,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
            },
            "chat": {
                "id": 987654321,
                "first_name": "Test",
                "username": "testuser",
                "type": "private",
            },
            "date": 1234567891,
            "photo": [
                {
                    "file_id": "photo_file_id",
                    "file_unique_id": "photo_unique_id",
                    "width": 100,
                    "height": 100,
                    "file_size": 1000,
                }
            ],
        },
    }


@pytest.fixture
def sample_command_update() -> dict[str, Any]:
    """Sample Telegram command update."""
    return {
        "update_id": 123456791,
        "message": {
            "message_id": 3,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
            },
            "chat": {
                "id": 987654321,
                "first_name": "Test",
                "username": "testuser",
                "type": "private",
            },
            "date": 1234567892,
            "text": "/start",
            "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
        },
    }


@pytest.fixture
def sample_document_update() -> dict[str, Any]:
    """Sample Telegram document message update."""
    return {
        "update_id": 123456792,
        "message": {
            "message_id": 4,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
            },
            "chat": {
                "id": 987654321,
                "first_name": "Test",
                "username": "testuser",
                "type": "private",
            },
            "date": 1234567893,
            "document": {
                "file_id": "doc_file_id",
                "file_unique_id": "doc_unique_id",
                "file_name": "test.pdf",
                "mime_type": "application/pdf",
                "file_size": 5000,
            },
        },
    }


@pytest.fixture
def sample_location_update() -> dict[str, Any]:
    """Sample Telegram location message update."""
    return {
        "update_id": 123456793,
        "message": {
            "message_id": 5,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
            },
            "chat": {
                "id": 987654321,
                "first_name": "Test",
                "username": "testuser",
                "type": "private",
            },
            "date": 1234567894,
            "location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
        },
    }
