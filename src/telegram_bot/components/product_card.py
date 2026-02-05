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

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from telegram_bot.callbacks.callback_data import ProductCallback
from telegram_bot.logging_config import get_logger
from telegram_bot.utils.formatting import format_price
from telegram_bot.utils.i18n import normalize_language_code

logger = get_logger("components.product_card")

# Maximum caption length for Telegram photos
MAX_CAPTION_LENGTH = 1024

# Path to locales directory
LOCALES_DIR = Path(__file__).parent.parent / "locales"
DEFAULT_LANGUAGE = "en"


@lru_cache(maxsize=1)
def _load_button_labels() -> dict[str, dict[str, str]]:
    """Load button labels from JSON file.

    Uses LRU cache to load file only once at startup.

    Returns:
        Dictionary of language codes to button labels.
    """
    buttons_file = LOCALES_DIR / "buttons.json"

    try:
        with buttons_file.open(encoding="utf-8") as f:
            data = json.load(f)
            # Remove _meta key if present
            data.pop("_meta", None)
            logger.info("Loaded button labels for %d languages", len(data))
            return data
    except FileNotFoundError:
        logger.warning("Button labels file not found: %s", buttons_file)
        return _get_fallback_labels()
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in button labels: %s", e)
        return _get_fallback_labels()


def _get_fallback_labels() -> dict[str, dict[str, str]]:
    """Return fallback labels if JSON file is unavailable."""
    return {
        "en": {
            "details": "🔍 Details",
            "show_details": "📋 Show Details",
            "hide_details": "📋 Hide Details",
            "gallery_caption": "📸 Gallery: {name}",
            "add_to_cart": "🛒 Add to Cart",
            "view_cart": "🛒 View Cart",
            "checkout": "💳 Checkout",
            "clear_cart": "🗑️ Clear",
        },
    }


def _get_button_label(key: str, language_code: str | None) -> str:
    """Get localized button label.

    Args:
        key: Button key (e.g., 'details', 'add_to_cart')
        language_code: User's language code (e.g., 'en', 'es', 'es-MX')

    Returns:
        Localized button label
    """
    labels = _load_button_labels()
    lang = normalize_language_code(language_code)
    lang_labels = labels.get(lang, labels.get(DEFAULT_LANGUAGE, {}))
    default_labels = labels.get(DEFAULT_LANGUAGE, {})
    label = lang_labels.get(key, default_labels.get(key, key))
    logger.debug(
        "Button label: key=%s, input_lang=%s, resolved=%s", key, language_code, lang
    )
    return label


def _extract_specs(product: dict[str, Any], exclude_brand: bool = False) -> str:
    """Extract and format product specifications.

    Args:
        product: Product dictionary
        exclude_brand: If True, don't include brand in specs (already shown elsewhere)

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

    # Electronics/General specs (only if no real estate specs)
    if not exclude_brand and product.get("brand") and not specs:
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
    price = format_price(product.get("price"))
    description = product.get("description", "")
    location = product.get("location", "")
    brand = product.get("brand", "")

    # Build caption
    lines = [f"<b>{name}</b>"]
    lines.append(f"💰 <b>{price}</b>")

    # Track if brand was already shown
    brand_shown = False
    if location:
        lines.append(f"📍 {location}")
    elif brand:
        lines.append(f"🏷️ {brand}")
        brand_shown = True

    # Add specs (exclude brand if already shown above)
    specs = _extract_specs(product, exclude_brand=brand_shown)
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


def format_product_caption_expanded(product: dict[str, Any]) -> str:
    """Format expanded product caption with full details.

    Builds a detailed caption including all available product fields:
    name, price, location/brand, specs, and full description.
    Respects the 1024-char Telegram caption limit.

    Args:
        product: Product dictionary with all product fields.

    Returns:
        Formatted HTML caption string with full details.
    """
    name = product.get("name", "Producto")
    price = format_price(product.get("price"))
    description = product.get("description", "")
    brand = product.get("brand", "")
    category = product.get("category", "")
    sku = product.get("sku", "")
    condition = product.get("condition", "")
    warranty = product.get("warranty", "")
    location = product.get("location", "")
    bedrooms = product.get("bedrooms", "")
    bathrooms = product.get("bathrooms", "")
    sqft_raw = product.get("sqft", "") or product.get("area", "")

    try:
        sqft = int(float(sqft_raw)) if sqft_raw else 0
    except (ValueError, TypeError):
        sqft = 0

    lines = [f"<b>{name}</b>", f"💰 <b>{price}</b>"]

    # Location or brand
    if location:
        lines.append(f"📍 {location}")
    elif brand:
        lines.append(f"🏷️ {brand}")

    # Specs section
    specs_lines: list[str] = []
    if brand and not location:
        pass  # Already shown above
    elif brand:
        specs_lines.append(f"🏷️ {brand}")
    if category:
        specs_lines.append(f"📁 {category}")
    if sku:
        specs_lines.append(f"🔢 {sku}")
    if condition:
        specs_lines.append(f"✨ {condition}")
    if warranty:
        specs_lines.append(f"🛡️ {warranty}")

    # Real estate specs
    if bedrooms:
        specs_lines.append(f"🛏️ {bedrooms} hab")
    if bathrooms:
        specs_lines.append(f"🚿 {bathrooms} baños")
    if sqft:
        specs_lines.append(f"📐 {sqft:,} sqft")

    if specs_lines:
        lines.append("─" * 20)
        lines.extend(specs_lines)

    # Full description
    if description:
        lines.append("─" * 20)
        # Reserve space for header lines (~200 chars) to stay within 1024
        max_desc = MAX_CAPTION_LENGTH - 200
        if len(description) > max_desc:
            description = description[: max_desc - 3] + "..."
        lines.append(description)

    caption = "\n".join(lines)

    if len(caption) > MAX_CAPTION_LENGTH:
        caption = caption[: MAX_CAPTION_LENGTH - 3] + "..."

    return caption


def build_product_keyboard(
    product_id: int,
    page: int = 0,
    total: int = 1,
    show_pagination: bool = True,
    language_code: str | None = None,
    expanded: bool = False,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for a product card.

    Args:
        product_id: The product ID for callback data
        page: Current page index
        total: Total number of products
        show_pagination: Whether to show pagination buttons
        language_code: User's language code for button labels
        expanded: Whether the card is in expanded state

    Returns:
        InlineKeyboardMarkup with action and navigation buttons
    """
    keyboard: list[list[InlineKeyboardButton]] = []

    # Details toggle button
    if expanded:
        details_label = _get_button_label("hide_details", language_code)
        details_action = "hide"
    else:
        details_label = _get_button_label("show_details", language_code)
        details_action = "show"

    # Action buttons row
    action_row = [
        InlineKeyboardButton(
            text=details_label,
            callback_data=ProductCallback(
                action=details_action,
                product_id=product_id,
                page=page,
                total=total,
            ).pack(),
        ),
        InlineKeyboardButton(
            text=_get_button_label("add_to_cart", language_code),
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
    language_code: str | None = None,
) -> Message | None:
    """Send a product card with image and action buttons.

    Args:
        bot: The Bot instance
        chat_id: Chat ID to send to
        product: Product dictionary with id, name, price, image_url, etc.
        page: Current page index for pagination
        total: Total number of products in result set
        language_code: User's language code for button labels

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
        language_code=language_code,
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
    language_code: str | None = None,
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
        language_code: User's language code for button labels

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
            language_code=language_code,
        )
        if product_msg:
            messages.append(product_msg)

    return messages
