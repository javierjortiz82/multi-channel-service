"""UI components for Telegram bot responses.

This module provides reusable components for building rich
Telegram responses with images, buttons, and pagination.
"""

from telegram_bot.components.product_card import (
    format_product_caption,
    send_product_card,
    send_product_list,
)

__all__ = ["format_product_caption", "send_product_card", "send_product_list"]
