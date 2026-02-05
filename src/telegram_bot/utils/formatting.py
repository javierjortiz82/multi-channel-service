"""Shared formatting utilities for the Telegram bot.

Provides consistent price formatting used across product cards and callbacks.
"""


def format_price(price: float | int | str | None) -> str:
    """Format price with thousands separator and currency symbol.

    Args:
        price: The price value to format. Accepts float, int, str, or None.

    Returns:
        Formatted price string (e.g., "$1,234.56") or "N/A" for None/invalid.
    """
    if price is None:
        return "N/A"
    try:
        price_float = float(price)
        if price_float >= 1_000_000:
            return f"${price_float:,.0f}"
        elif price_float >= 1000:
            return f"${price_float:,.2f}"
        else:
            return f"${price_float:.2f}"
    except (ValueError, TypeError):
        return str(price) if price else "N/A"
