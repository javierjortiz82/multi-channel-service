"""Tests for the Jinja2 templates module.

This module tests the TemplateManager and all template rendering functionality
including error messages, command responses, product display, and NLP prompts.
"""

from dataclasses import dataclass

import pytest

from telegram_bot.templates import (
    COMMAND_MESSAGES,
    DEFAULT_ERROR,
    ERROR_MESSAGES,
    PRODUCT_MESSAGES,
    TemplateManager,
    templates,
)

# =============================================================================
# Test fixtures
# =============================================================================


@dataclass
class MockProduct:
    """Mock product for testing."""

    sku: str = "SKU-001"
    name: str = "Test Product"
    brand: str | None = "Test Brand"
    description: str | None = "This is a test product description"
    price: float | None = 99.99
    image_url: str | None = "https://example.com/image.jpg"
    similarity: float = 0.85
    match_type: str = "similar"


# =============================================================================
# TemplateManager tests
# =============================================================================


class TestTemplateManager:
    """Tests for TemplateManager class."""

    def test_singleton_instance(self) -> None:
        """Test that templates is a singleton instance."""
        assert isinstance(templates, TemplateManager)

    def test_supported_languages(self) -> None:
        """Test supported languages are defined."""
        assert {"es", "en", "pt", "fr", "ar"} == templates.SUPPORTED_LANGUAGES
        assert templates.DEFAULT_LANGUAGE == "en"


class TestLanguageNormalization:
    """Tests for language code normalization."""

    def test_normalize_full_code(self) -> None:
        """Test normalizing full language codes like 'en-US'."""
        assert templates._normalize_language("en-US") == "en"
        assert templates._normalize_language("es-MX") == "es"
        assert templates._normalize_language("pt-BR") == "pt"

    def test_normalize_simple_code(self) -> None:
        """Test normalizing simple language codes."""
        assert templates._normalize_language("en") == "en"
        assert templates._normalize_language("es") == "es"
        assert templates._normalize_language("fr") == "fr"

    def test_normalize_unsupported_falls_back(self) -> None:
        """Test that unsupported languages fall back to default."""
        assert templates._normalize_language("zh") == "en"
        assert templates._normalize_language("de") == "en"
        assert templates._normalize_language("jp") == "en"

    def test_normalize_none_returns_default(self) -> None:
        """Test that None returns default language."""
        assert templates._normalize_language(None) == "en"

    def test_normalize_case_insensitive(self) -> None:
        """Test that normalization is case-insensitive."""
        assert templates._normalize_language("EN") == "en"
        assert templates._normalize_language("ES-mx") == "es"


# =============================================================================
# Error message tests
# =============================================================================


class TestErrorMessages:
    """Tests for error message rendering."""

    @pytest.mark.parametrize("lang", ["es", "en", "pt", "fr", "ar"])
    def test_render_error_all_languages(self, lang: str) -> None:
        """Test error messages render for all supported languages."""
        msg = templates.render_error("nlp_failed", lang)
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_render_error_spanish(self) -> None:
        """Test Spanish error message content."""
        msg = templates.render_error("nlp_failed", "es")
        assert "error" in msg.lower()
        assert "mensaje" in msg.lower()

    def test_render_error_english(self) -> None:
        """Test English error message content."""
        msg = templates.render_error("nlp_failed", "en")
        assert "error" in msg.lower()
        assert "message" in msg.lower()

    @pytest.mark.parametrize(
        "key",
        [
            "nlp_failed",
            "asr_failed",
            "ocr_failed",
            "download_failed",
            "empty_text",
            "empty_audio",
            "unsupported",
            "no_text_in_image",
            "low_confidence",
            "product_not_found",
        ],
    )
    def test_all_error_keys(self, key: str) -> None:
        """Test all error keys render without error."""
        msg = templates.render_error(key, "es")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_unknown_key_returns_fallback(self) -> None:
        """Test unknown error key returns fallback message."""
        msg = templates.render_error("unknown_key", "es")
        assert msg == DEFAULT_ERROR

    def test_all_languages_have_all_keys(self) -> None:
        """Test that all languages have all error keys defined."""
        # Get all keys from English as reference
        reference_keys = set(ERROR_MESSAGES["en"].keys())
        for lang in templates.SUPPORTED_LANGUAGES:
            lang_keys = set(ERROR_MESSAGES[lang].keys())
            assert lang_keys == reference_keys, (
                f"Language '{lang}' missing keys: {reference_keys - lang_keys}"
            )

    def test_error_messages_not_empty(self) -> None:
        """Test that no error message is empty."""
        for lang, messages in ERROR_MESSAGES.items():
            for key, value in messages.items():
                assert value, f"Empty message for key '{key}' in language '{lang}'"
                assert len(value) > 5, (
                    f"Message too short for key '{key}' in language '{lang}'"
                )


# =============================================================================
# Command template tests
# =============================================================================


class TestCommandTemplates:
    """Tests for command response templates."""

    def test_render_start_command_english(self) -> None:
        """Test /start command response in English (default)."""
        msg = templates.render_command("start")
        assert "<b>Welcome!</b>" in msg
        assert "/help" in msg

    def test_render_start_command_spanish(self) -> None:
        """Test /start command response in Spanish."""
        msg = templates.render_command("start", "es")
        assert "<b>¡Bienvenido!</b>" in msg
        assert "/help" in msg

    def test_render_help_command_english(self) -> None:
        """Test /help command response in English (default)."""
        msg = templates.render_command("help")
        assert "<b>Available commands:</b>" in msg
        assert "/start" in msg
        assert "/help" in msg

    def test_render_help_command_spanish(self) -> None:
        """Test /help command response in Spanish."""
        msg = templates.render_command("help", "es")
        assert "<b>Comandos disponibles:</b>" in msg
        assert "/start" in msg
        assert "/help" in msg

    @pytest.mark.parametrize("lang", ["es", "en", "pt", "fr", "ar"])
    def test_render_commands_all_languages(self, lang: str) -> None:
        """Test command responses render for all supported languages."""
        start_msg = templates.render_command("start", lang)
        help_msg = templates.render_command("help", lang)
        assert isinstance(start_msg, str)
        assert isinstance(help_msg, str)
        assert len(start_msg) > 0
        assert len(help_msg) > 0
        assert "/help" in start_msg
        assert "/start" in help_msg

    def test_all_languages_have_all_command_keys(self) -> None:
        """Test that all languages have all command keys defined."""
        reference_keys = set(COMMAND_MESSAGES["en"].keys())
        for lang in templates.SUPPORTED_LANGUAGES:
            lang_keys = set(COMMAND_MESSAGES[lang].keys())
            assert lang_keys == reference_keys, (
                f"Language '{lang}' missing keys: {reference_keys - lang_keys}"
            )


# =============================================================================
# Product template tests
# =============================================================================


class TestProductTemplates:
    """Tests for product display templates."""

    def test_render_product_list_with_exact_match_english(self) -> None:
        """Test product list with exact match header in English (default)."""
        products = [
            MockProduct(match_type="exact", similarity=0.95),
            MockProduct(name="Product 2", sku="SKU-002"),
        ]
        html = templates.render_product_list(products, has_exact_match=True)
        assert "✅" in html
        assert "I found products that match" in html

    def test_render_product_list_with_exact_match_spanish(self) -> None:
        """Test product list with exact match header in Spanish."""
        products = [
            MockProduct(match_type="exact", similarity=0.95),
            MockProduct(name="Product 2", sku="SKU-002"),
        ]
        html = templates.render_product_list(
            products, has_exact_match=True, language_code="es"
        )
        assert "✅" in html
        assert "¡Encontré productos que coinciden" in html

    def test_render_product_list_without_exact_match(self) -> None:
        """Test product list without exact match header (English default)."""
        products = [MockProduct(), MockProduct(name="Product 2", sku="SKU-002")]
        html = templates.render_product_list(products, has_exact_match=False)
        assert "🔍" in html
        assert "don't have that exact product" in html

    def test_render_product_list_contains_product_info(self) -> None:
        """Test product list contains product information."""
        products = [MockProduct()]
        html = templates.render_product_list(products, has_exact_match=False)
        assert "Test Product" in html
        assert "Test Brand" in html
        assert "SKU-001" in html

    @pytest.mark.parametrize("lang", ["es", "en", "pt", "fr", "ar"])
    def test_render_product_list_all_languages(self, lang: str) -> None:
        """Test product list renders for all supported languages."""
        products = [MockProduct()]
        html = templates.render_product_list(
            products, has_exact_match=False, language_code=lang
        )
        assert isinstance(html, str)
        assert len(html) > 0
        assert "Test Product" in html  # Product name should be present

    def test_all_languages_have_all_product_keys(self) -> None:
        """Test that all languages have all product message keys defined."""
        reference_keys = set(PRODUCT_MESSAGES["en"].keys())
        for lang in templates.SUPPORTED_LANGUAGES:
            lang_keys = set(PRODUCT_MESSAGES[lang].keys())
            assert lang_keys == reference_keys, (
                f"Language '{lang}' missing keys: {reference_keys - lang_keys}"
            )

    def test_get_product_message_with_formatting(self) -> None:
        """Test get_product_message with format arguments."""
        msg = templates.get_product_message(
            "exact_match_intro", "en", product_name="Keyboard"
        )
        assert "Keyboard" in msg
        assert "found" in msg.lower()

    def test_get_product_message_spanish(self) -> None:
        """Test get_product_message returns Spanish text."""
        msg = templates.get_product_message("ask_interest", "es")
        assert "interesa" in msg.lower()


# =============================================================================
# NLP prompt tests
# =============================================================================


class TestNLPPrompts:
    """Tests for NLP prompt templates."""

    def test_render_document_prompt(self) -> None:
        """Test document analysis prompt."""
        extracted_text = "Invoice #12345\nTotal: $100.00"
        prompt = templates.render_document_prompt(extracted_text)
        assert "Invoice #12345" in prompt
        assert "Total: $100.00" in prompt
        assert "image" in prompt.lower()
        assert "document" in prompt.lower()

    def test_render_document_prompt_escapes_quotes(self) -> None:
        """Test document prompt handles special characters."""
        extracted_text = 'Text with "quotes" and <tags>'
        prompt = templates.render_document_prompt(extracted_text)
        # Template should preserve the text inside triple quotes
        assert 'Text with "quotes"' in prompt


# =============================================================================
# Custom filter tests
# =============================================================================


class TestCustomFilters:
    """Tests for Jinja2 custom filters."""

    def test_escape_html_filter(self) -> None:
        """Test escape_html filter."""
        from telegram_bot.templates import _escape_html

        assert _escape_html("Hello & World") == "Hello &amp; World"
        assert _escape_html("a < b > c") == "a &lt; b &gt; c"
        assert _escape_html(None) == ""

    def test_format_price_filter(self) -> None:
        """Test format_price filter."""
        from telegram_bot.templates import _format_price

        assert _format_price(99.99) == "$99.99"
        assert _format_price(100.00) == "$100.00"
        assert _format_price(None) == "Contact us"
        assert _format_price(None, contact_text="Consultar") == "Consultar"

    def test_format_percent_filter(self) -> None:
        """Test format_percent filter."""
        from telegram_bot.templates import _format_percent

        assert _format_percent(0.85) == "85%"
        assert _format_percent(1.0) == "100%"
        assert _format_percent(0.0) == "0%"

    def test_truncate_filter(self) -> None:
        """Test truncate_text filter."""
        from telegram_bot.templates import _truncate

        long_text = "A" * 150
        assert _truncate(long_text, 100) == "A" * 100 + "..."
        assert _truncate("Short", 100) == "Short"
        assert _truncate(None, 100) == ""
