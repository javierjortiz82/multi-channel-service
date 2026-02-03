"""Callback handlers for inline keyboard buttons.

This module provides callback query handlers for product interactions
including details, cart, and pagination navigation.

Note: create_callback_router should be imported directly from
telegram_bot.callbacks.product_callbacks to avoid circular imports.
"""

from telegram_bot.callbacks.callback_data import CartCallback, ProductCallback

__all__ = ["CartCallback", "ProductCallback"]
