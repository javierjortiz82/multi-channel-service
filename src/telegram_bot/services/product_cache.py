"""Product cache for storing search results for pagination.

This module provides an in-memory cache for product search results,
enabling navigation between products without re-querying the database.

The cache uses TTL (time-to-live) to automatically expire old entries.
"""

import time
from typing import Any

from telegram_bot.logging_config import get_logger

logger = get_logger("services.product_cache")

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes
MAX_CACHE_SIZE = 1000  # Maximum number of chat sessions to cache


class ProductCache:
    """In-memory cache for product search results.

    Stores products by chat_id with automatic TTL expiration.
    Thread-safe for async operations (single-threaded event loop).
    """

    def __init__(self, ttl: int = CACHE_TTL_SECONDS, max_size: int = MAX_CACHE_SIZE):
        """Initialize the cache.

        Args:
            ttl: Time-to-live in seconds for cache entries.
            max_size: Maximum number of entries before cleanup.
        """
        self._cache: dict[str, dict[str, Any]] = {}
        self._ttl = ttl
        self._max_size = max_size

    def store(
        self,
        chat_id: int | str,
        products: list[dict[str, Any]],
        language_code: str | None = None,
    ) -> None:
        """Store products for a chat session.

        Args:
            chat_id: The Telegram chat ID.
            products: List of product dictionaries to cache.
            language_code: Detected language code to use for button labels.
        """
        key = str(chat_id)

        # Cleanup if cache is too large
        if len(self._cache) >= self._max_size:
            self._cleanup_expired()

        self._cache[key] = {
            "products": products,
            "timestamp": time.time(),
            "language_code": language_code,
            "expanded_galleries": set(),
        }

        logger.debug(
            "Cached %d products for chat %s",
            len(products),
            key,
        )

    def get(self, chat_id: int | str) -> list[dict[str, Any]]:
        """Get cached products for a chat session.

        Args:
            chat_id: The Telegram chat ID.

        Returns:
            List of product dictionaries, or empty list if not found/expired.
        """
        key = str(chat_id)
        entry = self._cache.get(key)

        if not entry:
            return []

        # Check if expired
        if time.time() - entry["timestamp"] > self._ttl:
            del self._cache[key]
            return []

        products: list[dict[str, Any]] = entry["products"]
        return products

    def get_product(self, chat_id: int | str, index: int) -> dict[str, Any] | None:
        """Get a specific product by index.

        Args:
            chat_id: The Telegram chat ID.
            index: The product index (0-based).

        Returns:
            Product dictionary or None if not found.
        """
        products = self.get(chat_id)
        if 0 <= index < len(products):
            return products[index]
        return None

    def get_language(self, chat_id: int | str) -> str | None:
        """Get the cached language code for a chat session.

        Args:
            chat_id: The Telegram chat ID.

        Returns:
            Language code string or None if not found/expired.
        """
        key = str(chat_id)
        entry = self._cache.get(key)

        if not entry:
            return None

        if time.time() - entry["timestamp"] > self._ttl:
            return None

        return entry.get("language_code")

    def get_count(self, chat_id: int | str) -> int:
        """Get the number of cached products.

        Args:
            chat_id: The Telegram chat ID.

        Returns:
            Number of cached products.
        """
        return len(self.get(chat_id))

    def mark_gallery_sent(self, chat_id: int | str, product_id: int) -> None:
        """Track that gallery was already sent for this product.

        Args:
            chat_id: The Telegram chat ID.
            product_id: The product ID whose gallery was sent.
        """
        key = str(chat_id)
        entry = self._cache.get(key)
        if entry and time.time() - entry["timestamp"] <= self._ttl:
            entry["expanded_galleries"].add(product_id)

    def is_gallery_sent(self, chat_id: int | str, product_id: int) -> bool:
        """Check if gallery was already sent for this product.

        Args:
            chat_id: The Telegram chat ID.
            product_id: The product ID to check.

        Returns:
            True if gallery was already sent, False otherwise.
        """
        key = str(chat_id)
        entry = self._cache.get(key)
        if not entry or time.time() - entry["timestamp"] > self._ttl:
            return False
        return product_id in entry["expanded_galleries"]

    def clear(self, chat_id: int | str) -> None:
        """Clear cached products for a chat session.

        Args:
            chat_id: The Telegram chat ID.
        """
        key = str(chat_id)
        if key in self._cache:
            del self._cache[key]

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        now = time.time()
        expired_keys = [
            key
            for key, entry in self._cache.items()
            if now - entry["timestamp"] > self._ttl
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug("Cleaned up %d expired cache entries", len(expired_keys))


# Singleton instance
_cache: ProductCache | None = None


def get_product_cache() -> ProductCache:
    """Get the singleton product cache instance.

    Returns:
        ProductCache instance.
    """
    global _cache
    if _cache is None:
        _cache = ProductCache()
    return _cache
