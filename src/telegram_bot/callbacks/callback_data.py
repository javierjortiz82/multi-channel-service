"""Callback data classes for inline keyboard interactions.

This module defines CallbackData classes used for product and cart actions.
Separated to avoid circular imports between components and callbacks.
"""

from aiogram.filters.callback_data import CallbackData


class ProductCallback(CallbackData, prefix="prod"):
    """Callback data for product-related actions.

    Attributes:
        action: The action to perform (details, cart, prev, next, back, noop)
        product_id: The product ID to act on
        page: Current page index for pagination
        total: Total number of products in the result set
    """

    action: str
    product_id: int
    page: int = 0
    total: int = 1


class CartCallback(CallbackData, prefix="cart"):
    """Callback data for cart-related actions.

    Attributes:
        action: The action to perform (view, clear, checkout, edit)
        conversation_id: Optional conversation ID for cart operations
    """

    action: str
    conversation_id: str = ""


class CartItemCallback(CallbackData, prefix="citm"):
    """Callback data for individual cart item actions.

    Attributes:
        action: The action (qty_up, qty_down, remove, confirm_del, cancel_del)
        item_idx: Item index in cart (1-based)
        conv_id: Conversation ID for cart operations
    """

    action: str
    item_idx: int
    conv_id: str = ""
