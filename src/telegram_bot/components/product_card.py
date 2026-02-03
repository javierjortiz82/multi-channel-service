"""Product card component for Telegram bot.

This module provides functions to send product cards with images,
formatted captions, and inline keyboard buttons for actions.

Example:
    from telegram_bot.components import send_product_card

    await send_product_card(
        bot=bot,
        chat_id=123456,
        product={"id": 1, "name": "Laptop", "price": 999.99, "image_url": "..."},
        page=0,
        total=5,
    )
"""

from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from telegram_bot.callbacks.callback_data import ProductCallback
from telegram_bot.logging_config import get_logger

logger = get_logger("components.product_card")

# Maximum caption length for Telegram photos
MAX_CAPTION_LENGTH = 1024


def _format_price(price: float | int | str | None) -> str:
    """Format price with thousands separator.

    Args:
        price: The price value to format

    Returns:
        Formatted price string
    """
    if price is None:
        return "Consultar"
    try:
        price_float = float(price)
        if price_float >= 1_000_000:
            return f"${price_float:,.0f}"
        elif price_float >= 1000:
            return f"${price_float:,.2f}"
        else:
            return f"${price_float:.2f}"
    except (ValueError, TypeError):
        return str(price)


def _extract_specs(product: dict[str, Any]) -> str:
    """Extract and format product specifications.

    Args:
        product: Product dictionary

    Returns:
        Formatted specifications string
    """
    specs = []

    # Real Estate specific specs
    if product.get("bedrooms"):
        specs.append(f"🛏️ {product['bedrooms']} hab")
    if product.get("bathrooms"):
        specs.append(f"🚿 {product['bathrooms']} baños")
    if product.get("sqft") or product.get("area"):
        area = product.get("sqft") or product.get("area")
        specs.append(f"📐 {area:,} sqft")

    # Electronics/General specs
    if product.get("brand") and not specs:
        specs.append(f"🏷️ {product['brand']}")
    if product.get("category") and not specs:
        specs.append(f"📦 {product['category']}")

    return " | ".join(specs) if specs else ""


def format_product_caption(
    product: dict[str, Any],
    include_description: bool = True,
    max_desc_length: int = 150,
) -> str:
    """Format product information as a caption for Telegram.

    Args:
        product: Product dictionary with keys like name, price, description, etc.
        include_description: Whether to include the description
        max_desc_length: Maximum length for description truncation

    Returns:
        Formatted HTML caption string
    """
    name = product.get("name", "Producto")
    price = _format_price(product.get("price"))
    description = product.get("description", "")
    location = product.get("location", "")
    brand = product.get("brand", "")

    # Build caption
    lines = [f"<b>{name}</b>"]
    lines.append(f"💰 <b>{price}</b>")

    if location:
        lines.append(f"📍 {location}")
    elif brand:
        lines.append(f"🏷️ {brand}")

    # Add specs
    specs = _extract_specs(product)
    if specs:
        lines.append(specs)

    # Add truncated description
    if include_description and description:
        if len(description) > max_desc_length:
            description = description[: max_desc_length - 3] + "..."
        lines.append(f"\n{description}")

    caption = "\n".join(lines)

    # Ensure caption doesn't exceed Telegram limit
    if len(caption) > MAX_CAPTION_LENGTH:
        caption = caption[: MAX_CAPTION_LENGTH - 3] + "..."

    return caption


def build_product_keyboard(
    product_id: int,
    page: int = 0,
    total: int = 1,
    show_pagination: bool = True,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for a product card.

    Args:
        product_id: The product ID for callback data
        page: Current page index
        total: Total number of products
        show_pagination: Whether to show pagination buttons

    Returns:
        InlineKeyboardMarkup with action and navigation buttons
    """
    keyboard: list[list[InlineKeyboardButton]] = []

    # Action buttons row
    action_row = [
        InlineKeyboardButton(
            text="🔍 Detalles",
            callback_data=ProductCallback(
                action="details",
                product_id=product_id,
                page=page,
                total=total,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="🛒 Agregar",
            callback_data=ProductCallback(
                action="cart",
                product_id=product_id,
                page=page,
                total=total,
            ).pack(),
        ),
    ]
    keyboard.append(action_row)

    # Pagination row (if multiple products)
    if show_pagination and total > 1:
        nav_row: list[InlineKeyboardButton] = []

        # Previous button
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=ProductCallback(
                        action="prev",
                        product_id=product_id,
                        page=page - 1,
                        total=total,
                    ).pack(),
                )
            )

        # Page indicator
        nav_row.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total}",
                callback_data=ProductCallback(
                    action="noop",
                    product_id=product_id,
                    page=page,
                    total=total,
                ).pack(),
            )
        )

        # Next button
        if page < total - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=ProductCallback(
                        action="next",
                        product_id=product_id,
                        page=page + 1,
                        total=total,
                    ).pack(),
                )
            )

        keyboard.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def send_product_card(
    bot: Bot,
    chat_id: int,
    product: dict[str, Any],
    page: int = 0,
    total: int = 1,
) -> Message | None:
    """Send a product card with image and action buttons.

    Args:
        bot: The Bot instance
        chat_id: Chat ID to send to
        product: Product dictionary with id, name, price, image_url, etc.
        page: Current page index for pagination
        total: Total number of products in result set

    Returns:
        The sent Message object, or None if sending failed
    """
    product_id = product.get("id", 0)
    image_url = product.get("image_url", "")
    name = product.get("name", "Producto")

    # Build caption and keyboard
    caption = format_product_caption(product)
    keyboard = build_product_keyboard(
        product_id=product_id,
        page=page,
        total=total,
        show_pagination=(total > 1),
    )

    try:
        if image_url:
            # Send photo with caption
            return await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            # No image - send text message instead
            return await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.warning(
            "Failed to send product card for %s: %s",
            name,
            e,
        )
        # Fallback: try without image
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e2:
            logger.error("Failed to send product card fallback: %s", e2)
            return None


async def send_product_list(
    bot: Bot,
    chat_id: int,
    products: list[dict[str, Any]],
    header: str | None = None,
    max_products: int = 5,
) -> list[Message]:
    """Send a list of product cards.

    Sends the first product as a card with pagination,
    allowing navigation through the rest.

    Args:
        bot: The Bot instance
        chat_id: Chat ID to send to
        products: List of product dictionaries
        header: Optional header message before products
        max_products: Maximum products to include in pagination

    Returns:
        List of sent Message objects
    """
    messages: list[Message] = []

    if not products:
        return messages

    # Limit products for pagination
    products = products[:max_products]
    total = len(products)

    # Send optional header
    if header:
        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=header,
                parse_mode="HTML",
            )
            messages.append(msg)
        except Exception as e:
            logger.warning("Failed to send product list header: %s", e)

    # Send first product card (with pagination if multiple)
    if products:
        product_msg = await send_product_card(
            bot=bot,
            chat_id=chat_id,
            product=products[0],
            page=0,
            total=total,
        )
        if product_msg:
            messages.append(product_msg)

    return messages
