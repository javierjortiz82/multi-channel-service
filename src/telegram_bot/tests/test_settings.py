"""Unit tests for settings configuration."""

import pytest
from pydantic import ValidationError

from telegram_bot.config.settings import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_settings_loads_from_env(self, settings: Settings) -> None:
        """Test settings loads correctly from environment."""
        assert (
            settings.telegram_bot_token.get_secret_value()
            == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        )
        assert settings.webhook_host == "https://test.example.com"
        assert settings.webhook_path == "/webhook"
        assert settings.webhook_secret.get_secret_value() == "test-secret-token"

    def test_settings_webhook_url_property(self, settings: Settings) -> None:
        """Test webhook_url property combines host and path."""
        assert settings.webhook_url == "https://test.example.com/webhook"

    def test_settings_defaults(self, settings: Settings) -> None:
        """Test settings has correct defaults."""
        assert settings.server_host == "0.0.0.0"
        assert settings.server_port == 8002
        assert settings.environment == "development"
        assert settings.log_level == "DEBUG"
        assert settings.debug is False

    def test_webhook_host_strips_trailing_slash(self) -> None:
        """Test webhook host validation strips trailing slash."""
        test_settings = Settings(
            telegram_bot_token="123456789:TestTokenForValidation",
            webhook_host="https://example.com/",
            webhook_secret="secret",
        )
        assert test_settings.webhook_host == "https://example.com"

    def test_webhook_host_requires_protocol(self) -> None:
        """Test webhook host validation requires http(s) protocol."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                telegram_bot_token="123456789:TestTokenForValidation",
                webhook_host="example.com",
                webhook_secret="secret",
            )
        assert "webhook_host must start with http://" in str(exc_info.value)

    def test_server_port_validation(self) -> None:
        """Test server port must be in valid range."""
        with pytest.raises(ValidationError):
            Settings(
                telegram_bot_token="123456789:TestTokenForValidation",
                webhook_host="https://example.com",
                webhook_secret="secret",
                server_port=70000,
            )

    def test_environment_validation(self) -> None:
        """Test environment must be valid value."""
        with pytest.raises(ValidationError):
            Settings(
                telegram_bot_token="123456789:TestTokenForValidation",
                webhook_host="https://example.com",
                webhook_secret="secret",
                environment="invalid",
            )

    def test_log_level_validation(self) -> None:
        """Test log level must be valid value."""
        with pytest.raises(ValidationError):
            Settings(
                telegram_bot_token="123456789:TestTokenForValidation",
                webhook_host="https://example.com",
                webhook_secret="secret",
                log_level="INVALID",
            )

    def test_secret_values_are_hidden(self, settings: Settings) -> None:
        """Test that secret values are not exposed in string representation."""
        settings_str = str(settings)
        assert "ABCdefGHIjklMNOpqrsTUVwxyz" not in settings_str
        assert "test-secret-token" not in settings_str
