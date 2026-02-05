"""Shared internationalization utilities for the Telegram bot.

Provides language code normalization and localized message loading.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "es"

# Path to locales directory
LOCALES_DIR = Path(__file__).parent.parent / "locales"


def normalize_language_code(language_code: str | None) -> str:
    """Normalize a language code to ISO 639-1 two-letter format.

    Handles codes like 'en-US' -> 'en', 'pt-BR' -> 'pt'.
    Returns DEFAULT_LANGUAGE if input is None or empty.

    Args:
        language_code: Raw language code from Telegram or NLP detection.

    Returns:
        Normalized two-letter language code.
    """
    if not language_code:
        return DEFAULT_LANGUAGE
    return language_code.split("-")[0].lower()


@lru_cache(maxsize=1)
def _load_messages() -> dict[str, dict[str, str]]:
    """Load message strings from JSON file.

    Uses LRU cache to load file only once.

    Returns:
        Dictionary of language codes to message strings.
    """
    messages_file = LOCALES_DIR / "messages.json"
    try:
        with messages_file.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            data.pop("_meta", None)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_localized_message(key: str, language_code: str | None) -> str:
    """Get a localized message by key and language.

    Falls back to DEFAULT_LANGUAGE, then returns the key itself if not found.

    Args:
        key: Message key (e.g., 'nlp_failed', 'start_message').
        language_code: User's language code (e.g., 'en', 'es', 'en-US').

    Returns:
        Localized message string.
    """
    lang = normalize_language_code(language_code)
    messages = _load_messages()
    lang_messages = messages.get(lang, messages.get(DEFAULT_LANGUAGE, {}))
    default_messages = messages.get(DEFAULT_LANGUAGE, {})
    return lang_messages.get(key, default_messages.get(key, key))
