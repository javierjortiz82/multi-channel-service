"""Product callback handlers for inline keyboard interactions.

This module provides callback query handlers for product-related actions:
- View product details
- Add to cart
- Navigate between products (pagination)

Example:
    from telegram_bot.callbacks import create_callback_router

    dp = Dispatcher()
    dp.include_router(create_callback_router())
"""

import json
import re
from typing import Any

from aiogram import Bot, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from telegram_bot.callbacks.callback_data import (
    CartCallback,
    CartItemCallback,
    ProductCallback,
)
from telegram_bot.components.product_card import (
    _get_button_label,
    build_product_keyboard,
    format_product_caption,
    format_product_caption_expanded,
)
from telegram_bot.logging_config import get_logger
from telegram_bot.services.internal_client import get_client
from telegram_bot.services.product_cache import get_product_cache

logger = get_logger("callbacks.product")


def create_callback_router() -> Router:
    """Create and configure the callback query router.

    Returns:
        Router: Configured Router instance with callback handlers.
    """
    router = Router(name="callback_router")

    @router.callback_query(ProductCallback.filter())
    async def handle_product_callback(
        callback: CallbackQuery,
        callback_data: ProductCallback,
        bot: Bot,
    ) -> None:
        """Handle product card button clicks.

        Args:
            callback: The callback query from Telegram
            callback_data: Parsed callback data
            bot: The Bot instance
        """
        action = callback_data.action
        product_id = callback_data.product_id
        page = callback_data.page
        total = callback_data.total
        chat_id = callback.message.chat.id if callback.message else 0

        logger.info(
            "Product callback: action=%s, product_id=%d, page=%d/%d, chat=%d",
            action,
            product_id,
            page,
            total,
            chat_id,
        )

        if action in ("details", "show"):
            await _handle_show(callback, product_id, page, total, chat_id, bot)
        elif action == "hide":
            await _handle_hide(
                callback, product_id, callback_data.img, page, total, chat_id, bot
            )
        elif action == "cart":
            await _handle_add_to_cart(callback, product_id, chat_id, bot)
        elif action in ("img_prev", "img_next"):
            await _handle_gallery_nav(
                callback, product_id, callback_data.img, page, total, chat_id
            )
        elif action in ("prev", "next"):
            # page already contains the target page (set in keyboard builder)
            await _handle_navigation(callback, chat_id, page, total, bot)
        elif action == "noop":
            await callback.answer()

    @router.callback_query(CartCallback.filter())
    async def handle_cart_callback(
        callback: CallbackQuery,
        callback_data: CartCallback,
        bot: Bot,
    ) -> None:
        """Handle cart-related button clicks.

        Args:
            callback: The callback query from Telegram
            callback_data: Parsed callback data
            bot: The Bot instance
        """
        action = callback_data.action
        chat_id = callback.message.chat.id if callback.message else 0
        conversation_id = callback_data.conversation_id or str(chat_id)

        logger.info(
            "Cart callback: action=%s, conversation=%s", action, conversation_id
        )

        if action == "view":
            await _handle_view_cart(callback, conversation_id, bot)
        elif action == "checkout":
            await _handle_checkout(callback, conversation_id, bot)
        elif action == "clear":
            await _handle_clear_cart(callback, conversation_id, bot)

    @router.callback_query(CartItemCallback.filter())
    async def handle_cart_item_callback(
        callback: CallbackQuery,
        callback_data: CartItemCallback,
        bot: Bot,
    ) -> None:
        """Handle individual cart item actions.

        Args:
            callback: The callback query from Telegram
            callback_data: Parsed callback data
            bot: The Bot instance
        """
        action = callback_data.action
        item_idx = callback_data.item_idx
        chat_id = callback.message.chat.id if callback.message else 0
        conv_id = callback_data.conv_id or str(chat_id)

        logger.info(
            "Cart item callback: action=%s, item=%d, conv=%s",
            action,
            item_idx,
            conv_id,
        )

        if action == "qty_up":
            await _handle_qty_change(callback, conv_id, item_idx, delta=1, bot=bot)
        elif action == "qty_down":
            await _handle_qty_change(callback, conv_id, item_idx, delta=-1, bot=bot)
        elif action == "remove":
            await _handle_remove_confirm(callback, conv_id, item_idx, bot)
        elif action == "confirm_del":
            await _handle_remove_item(callback, conv_id, item_idx, bot)
        elif action == "cancel_del":
            await callback.answer("Cancelado")
            # Refresh cart view
            await _handle_view_cart(callback, conv_id, bot)

    return router


def _get_user_language(
    callback: CallbackQuery,
    chat_id: int,
) -> str | None:
    """Get user's language from cache or Telegram profile.

    Args:
        callback: The callback query.
        chat_id: The chat ID.

    Returns:
        Language code or None.
    """
    cache = get_product_cache()
    return cache.get_language(chat_id) or (
        callback.from_user.language_code if callback.from_user else None
    )


def _collect_product_images(product: dict[str, Any]) -> list[str]:
    """Collect all image URLs from a product.

    Args:
        product: Product dictionary

    Returns:
        List of image URLs (main image first, then additional)
    """
    images: list[str] = []

    # Primary image
    main_image = product.get("image_url", "")
    if main_image:
        images.append(main_image)

    # Additional images (check common field names)
    for field in ["images", "additional_images", "gallery", "photos"]:
        extra = product.get(field, [])
        # Parse JSON string if needed (PostgreSQL json_agg returns string)
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(extra, list):
            for img in extra:
                if isinstance(img, str) and img and img not in images:
                    images.append(img)
                elif isinstance(img, dict):
                    url = img.get("url") or img.get("src") or img.get("image_url")
                    if url and url not in images:
                        images.append(url)

    return images


async def _handle_show(
    callback: CallbackQuery,
    product_id: int,
    page: int,
    total: int,
    chat_id: int,
    bot: Bot,
) -> None:
    """Handle expand product details in-place.

    Edits the existing message caption to show full details and adds
    gallery navigation buttons for browsing images in-card.

    Args:
        callback: The callback query
        product_id: Product ID to show details for
        page: Current page index
        total: Total number of products
        chat_id: The chat ID
        bot: The Bot instance
    """
    await callback.answer()

    cache = get_product_cache()
    products = cache.get(chat_id)
    product = next((p for p in products if p.get("id") == product_id), None)

    if not product:
        await callback.answer("Productos expirados. Busca de nuevo.", show_alert=True)
        return

    lang = _get_user_language(callback, chat_id)
    all_images = _collect_product_images(product)
    total_imgs = len(all_images)

    caption = format_product_caption_expanded(product)
    keyboard = build_product_keyboard(
        product_id=product_id,
        page=page,
        total=total,
        show_pagination=(total > 1),
        language_code=lang,
        expanded=True,
        current_img=0,
        total_imgs=total_imgs,
    )

    message = callback.message
    try:
        if message and isinstance(message, Message) and message.photo:
            await message.edit_caption(
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        elif message and isinstance(message, Message):
            await message.edit_text(
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.error("Failed to edit message for expand: %s", e)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e2:
            logger.error("Fallback send also failed: %s", e2)


async def _handle_hide(
    callback: CallbackQuery,
    product_id: int,
    current_img: int,
    page: int,
    total: int,
    chat_id: int,
    bot: Bot,
) -> None:
    """Handle collapse product details back to compact view.

    If currently viewing a gallery image, swaps back to the main image.
    Otherwise just updates the caption.

    Args:
        callback: The callback query
        product_id: Product ID to collapse
        current_img: Current gallery image index
        page: Current page index
        total: Total number of products
        chat_id: The chat ID
        bot: The Bot instance
    """
    await callback.answer()

    cache = get_product_cache()
    products = cache.get(chat_id)
    product = next((p for p in products if p.get("id") == product_id), None)

    if not product:
        await callback.answer("Productos expirados. Busca de nuevo.", show_alert=True)
        return

    lang = _get_user_language(callback, chat_id)
    caption = format_product_caption(product)
    keyboard = build_product_keyboard(
        product_id=product_id,
        page=page,
        total=total,
        show_pagination=(total > 1),
        language_code=lang,
        expanded=False,
    )

    message = callback.message
    try:
        if message and isinstance(message, Message) and message.photo:
            if current_img > 0:
                # Swap back to main image + compact caption
                main_url = product.get("image_url", "")
                if main_url:
                    media = InputMediaPhoto(
                        media=main_url, caption=caption, parse_mode="HTML"
                    )
                    await message.edit_media(media=media, reply_markup=keyboard)
                else:
                    await message.edit_caption(
                        caption=caption, parse_mode="HTML", reply_markup=keyboard
                    )
            else:
                # Already on main image, just update caption
                await message.edit_caption(
                    caption=caption, parse_mode="HTML", reply_markup=keyboard
                )
        elif message and isinstance(message, Message):
            await message.edit_text(
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.error("Failed to edit message for collapse: %s", e)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e2:
            logger.error("Fallback send also failed: %s", e2)


async def _handle_gallery_nav(
    callback: CallbackQuery,
    product_id: int,
    new_img: int,
    page: int,
    total: int,
    chat_id: int,
) -> None:
    """Handle gallery image navigation (prev/next) in-place.

    Swaps the displayed photo via edit_media() without sending new messages.

    Args:
        callback: The callback query
        product_id: Product ID being viewed
        new_img: Target gallery image index
        page: Current page index
        total: Total number of products
        chat_id: The chat ID
    """
    await callback.answer()

    cache = get_product_cache()
    products = cache.get(chat_id)
    product = next((p for p in products if p.get("id") == product_id), None)

    if not product:
        await callback.answer("Productos expirados. Busca de nuevo.", show_alert=True)
        return

    all_images = _collect_product_images(product)
    total_imgs = len(all_images)

    # Validate bounds
    if new_img < 0 or new_img >= total_imgs:
        await callback.answer()
        return

    lang = _get_user_language(callback, chat_id)
    target_url = all_images[new_img]
    caption = format_product_caption_expanded(product)
    keyboard = build_product_keyboard(
        product_id=product_id,
        page=page,
        total=total,
        show_pagination=(total > 1),
        language_code=lang,
        expanded=True,
        current_img=new_img,
        total_imgs=total_imgs,
    )

    message = callback.message
    try:
        if message and isinstance(message, Message) and message.photo:
            media = InputMediaPhoto(
                media=target_url, caption=caption, parse_mode="HTML"
            )
            await message.edit_media(media=media, reply_markup=keyboard)
        elif message and isinstance(message, Message):
            # Text-only fallback (no photo to swap)
            await message.edit_text(
                text=caption, parse_mode="HTML", reply_markup=keyboard
            )
    except Exception as e:
        logger.error("Failed to navigate gallery image: %s", e)
        await callback.answer("Error cargando imagen", show_alert=True)


async def _handle_add_to_cart(
    callback: CallbackQuery,
    product_id: int,
    chat_id: int,
    bot: Bot,
) -> None:
    """Handle add to cart request.

    Calls NLP service to add product to cart via MCP.

    Args:
        callback: The callback query
        product_id: Product ID to add to cart
        chat_id: The chat ID
        bot: The Bot instance
    """
    await callback.answer("Agregando al carrito...", show_alert=False)

    # Get product name from cache for confirmation
    cache = get_product_cache()
    products = cache.get(chat_id)
    product = next((p for p in products if p.get("id") == product_id), None)
    product_name = product.get("name", "Producto") if product else "Producto"

    try:
        # Call NLP service with add to cart command
        client = get_client()
        conversation_id = str(chat_id)

        # Build command for NLP to interpret
        command = f"Agregar producto ID {product_id} al carrito"

        # Call NLP to add product (response not used - we show our own confirmation)
        await client.call_nlp_service(
            text=command,
            conversation_id=conversation_id,
        )

        # Get cached language for localized buttons
        lang = _get_user_language(callback, chat_id)

        # Build keyboard with "View Cart" button
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_get_button_label("view_cart", lang),
                        callback_data=CartCallback(
                            action="view",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                ],
            ]
        )

        # Always send confirmation with product name (NLP response may be empty)
        confirmation = _get_button_label("added_to_cart", lang).replace(
            "{name}", product_name
        )
        await bot.send_message(
            chat_id=chat_id,
            text=confirmation,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Failed to add to cart: %s", e)
        await callback.answer("Error agregando al carrito", show_alert=True)


async def _handle_navigation(
    callback: CallbackQuery,
    chat_id: int,
    new_page: int,
    total: int,
    bot: Bot,
) -> None:
    """Handle pagination navigation.

    Updates the message with the next/previous product from cache.

    Args:
        callback: The callback query
        chat_id: The chat ID
        new_page: The new page index to display
        total: Total number of products
        bot: The Bot instance
    """
    # Validate page bounds
    if new_page < 0 or new_page >= total:
        await callback.answer("No hay más productos", show_alert=False)
        return

    # Get product from cache
    cache = get_product_cache()
    product = cache.get_product(chat_id, new_page)

    if not product:
        await callback.answer("Productos expirados. Busca de nuevo.", show_alert=True)
        return

    await callback.answer()

    # Build new caption and keyboard
    caption = format_product_caption(product)
    # Use cached language (detected by NLP) instead of Telegram profile language
    user_lang = _get_user_language(callback, chat_id)
    keyboard = build_product_keyboard(
        product_id=product.get("id", 0),
        page=new_page,
        total=total,
        show_pagination=True,
        language_code=user_lang,
    )

    # Update message
    try:
        image_url = product.get("image_url", "")
        message = callback.message

        if message and isinstance(message, Message) and image_url:
            # Edit photo message
            media = InputMediaPhoto(media=image_url, caption=caption, parse_mode="HTML")
            await message.edit_media(media=media, reply_markup=keyboard)
        elif message and isinstance(message, Message):
            # Edit text message (no image)
            await message.edit_text(
                text=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        logger.info(
            "Navigated to product %d/%d: %s",
            new_page + 1,
            total,
            product.get("name", "Unknown"),
        )

    except Exception as e:
        logger.error("Failed to update product card: %s", e)
        # Fallback: send new message
        try:
            if image_url:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image_url,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
        except Exception as e2:
            logger.error("Fallback also failed: %s", e2)


def _parse_cart_items(response: str) -> int:
    """Parse cart response to count items.

    Looks for numbered items like "1.", "2.", etc.

    Args:
        response: Cart response text from NLP

    Returns:
        Number of items found in cart
    """
    # Match patterns like "1.", "2.", etc. at start of lines
    matches = re.findall(r"^\s*(\d+)\.", response, re.MULTILINE)
    return len(matches)


def _build_cart_item_buttons(
    item_count: int,
    conversation_id: str,
) -> list[list[InlineKeyboardButton]]:
    """Build inline keyboard rows for cart items.

    Args:
        item_count: Number of items in cart
        conversation_id: Conversation ID for callbacks

    Returns:
        List of keyboard rows with item action buttons
    """
    rows: list[list[InlineKeyboardButton]] = []

    for idx in range(1, item_count + 1):
        # Row per item: [➖] [Item N] [➕] [🗑️]
        row = [
            InlineKeyboardButton(
                text="➖",
                callback_data=CartItemCallback(
                    action="qty_down",
                    item_idx=idx,
                    conv_id=conversation_id,
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"Item {idx}",
                callback_data="noop",  # No action, just label
            ),
            InlineKeyboardButton(
                text="➕",
                callback_data=CartItemCallback(
                    action="qty_up",
                    item_idx=idx,
                    conv_id=conversation_id,
                ).pack(),
            ),
            InlineKeyboardButton(
                text="🗑️",
                callback_data=CartItemCallback(
                    action="remove",
                    item_idx=idx,
                    conv_id=conversation_id,
                ).pack(),
            ),
        ]
        rows.append(row)

    return rows


def _build_cart_action_row(
    conversation_id: str,
    lang: str | None,
) -> list[InlineKeyboardButton]:
    """Build the checkout + clear cart button row.

    Args:
        conversation_id: Conversation ID for callbacks.
        lang: Language code for button labels.

    Returns:
        List of InlineKeyboardButton for checkout and clear actions.
    """
    return [
        InlineKeyboardButton(
            text=_get_button_label("checkout", lang),
            callback_data=CartCallback(
                action="checkout",
                conversation_id=conversation_id,
            ).pack(),
        ),
        InlineKeyboardButton(
            text=_get_button_label("clear_cart", lang),
            callback_data=CartCallback(
                action="clear",
                conversation_id=conversation_id,
            ).pack(),
        ),
    ]


async def _handle_view_cart(
    callback: CallbackQuery,
    conversation_id: str,
    bot: Bot,
) -> None:
    """Handle view cart request.

    Calls NLP service to view cart contents and shows item-level buttons.

    Args:
        callback: The callback query
        conversation_id: The conversation ID
        bot: The Bot instance
    """
    await callback.answer()

    try:
        client = get_client()
        chat_id = callback.message.chat.id if callback.message else 0

        result = await client.call_nlp_service(
            text="Ver mi carrito",
            conversation_id=conversation_id,
        )

        response = result.get("response", "Tu carrito está vacío")

        # Get cached language for localized buttons
        lang = _get_user_language(callback, chat_id)

        # Check if cart has items (response contains price or items)
        cart_has_items = "$" in response or "item" in response.lower()

        if cart_has_items:
            # Parse item count and build per-item buttons
            item_count = _parse_cart_items(response)

            keyboard_rows: list[list[InlineKeyboardButton]] = []

            # Add per-item action buttons if we found items
            if item_count > 0:
                keyboard_rows.extend(
                    _build_cart_item_buttons(item_count, conversation_id)
                )

            keyboard_rows.append(_build_cart_action_row(conversation_id, lang))
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        else:
            keyboard = None

        await bot.send_message(
            chat_id=chat_id,
            text=response,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Failed to view cart: %s", e)
        await callback.answer("Error mostrando carrito", show_alert=True)


async def _handle_checkout(
    callback: CallbackQuery,
    conversation_id: str,
    bot: Bot,
) -> None:
    """Handle checkout button - create Stripe payment session.

    Calls NLP service to create checkout which triggers MCP create_checkout_session.

    Args:
        callback: The callback query
        conversation_id: The conversation ID
        bot: The Bot instance
    """
    await callback.answer("Procesando pago...")

    try:
        client = get_client()
        chat_id = callback.message.chat.id if callback.message else 0

        result = await client.call_nlp_service(
            text="Crear checkout para el carrito",
            conversation_id=conversation_id,
        )

        response = result.get("response", "Error al crear checkout")

        await bot.send_message(
            chat_id=chat_id,
            text=response,
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error("Failed to create checkout: %s", e)
        await callback.answer("Error al procesar pago", show_alert=True)


async def _handle_clear_cart(
    callback: CallbackQuery,
    conversation_id: str,
    bot: Bot,
) -> None:
    """Handle clear cart button.

    Calls NLP service to clear cart which triggers MCP clear_cart.

    Args:
        callback: The callback query
        conversation_id: The conversation ID
        bot: The Bot instance
    """
    await callback.answer("Vaciando carrito...")

    try:
        client = get_client()
        chat_id = callback.message.chat.id if callback.message else 0

        result = await client.call_nlp_service(
            text="Vaciar mi carrito",
            conversation_id=conversation_id,
        )

        response = result.get("response", "Carrito vaciado")

        await bot.send_message(
            chat_id=chat_id,
            text=response,
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error("Failed to clear cart: %s", e)
        await callback.answer("Error vaciando carrito", show_alert=True)


async def _handle_qty_change(
    callback: CallbackQuery,
    conversation_id: str,
    item_idx: int,
    delta: int,
    bot: Bot,
) -> None:
    """Handle quantity change for a cart item.

    Args:
        callback: The callback query
        conversation_id: The conversation ID
        item_idx: Item index in cart (1-based)
        delta: Quantity change (+1 or -1)
        bot: The Bot instance
    """
    await callback.answer()

    try:
        client = get_client()
        chat_id = callback.message.chat.id if callback.message else 0

        # Combined command: change quantity AND show updated cart (single NLP call)
        if delta > 0:
            command = f"Aumentar cantidad del item {item_idx} del carrito en 1 y mostrar el carrito actualizado"
        else:
            command = f"Reducir cantidad del item {item_idx} del carrito en 1 y mostrar el carrito actualizado"

        result = await client.call_nlp_service(
            text=command,
            conversation_id=conversation_id,
        )

        cart_response = result.get("response", "Cantidad actualizada")
        item_count = _parse_cart_items(cart_response)

        # Get cached language for localized buttons
        lang = _get_user_language(callback, chat_id)

        # Build keyboard
        keyboard_rows: list[list[InlineKeyboardButton]] = []
        if item_count > 0:
            keyboard_rows.extend(_build_cart_item_buttons(item_count, conversation_id))
            keyboard_rows.append(_build_cart_action_row(conversation_id, lang))
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        else:
            keyboard = None

        await bot.send_message(
            chat_id=chat_id,
            text=cart_response,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Failed to change quantity: %s", e)
        await callback.answer("Error cambiando cantidad", show_alert=True)


async def _handle_remove_confirm(
    callback: CallbackQuery,
    conversation_id: str,
    item_idx: int,
    bot: Bot,
) -> None:
    """Show confirmation dialog for removing an item.

    Args:
        callback: The callback query
        conversation_id: The conversation ID
        item_idx: Item index in cart (1-based)
        bot: The Bot instance
    """
    await callback.answer()

    chat_id = callback.message.chat.id if callback.message else 0

    # Get cached language for localized buttons
    lang = _get_user_language(callback, chat_id)

    # Build confirmation keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_get_button_label("yes_delete", lang),
                    callback_data=CartItemCallback(
                        action="confirm_del",
                        item_idx=item_idx,
                        conv_id=conversation_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text=_get_button_label("no_cancel", lang),
                    callback_data=CartItemCallback(
                        action="cancel_del",
                        item_idx=item_idx,
                        conv_id=conversation_id,
                    ).pack(),
                ),
            ],
        ]
    )

    confirm_text = _get_button_label("delete_confirm", lang).replace(
        "{idx}", str(item_idx)
    )
    await bot.send_message(
        chat_id=chat_id,
        text=confirm_text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def _handle_remove_item(
    callback: CallbackQuery,
    conversation_id: str,
    item_idx: int,
    bot: Bot,
) -> None:
    """Remove an item from the cart after confirmation.

    Args:
        callback: The callback query
        conversation_id: The conversation ID
        item_idx: Item index in cart (1-based)
        bot: The Bot instance
    """
    await callback.answer()

    try:
        client = get_client()
        chat_id = callback.message.chat.id if callback.message else 0

        # Combined command: remove item AND show updated cart (single NLP call)
        command = (
            f"Eliminar el item {item_idx} del carrito y mostrar el carrito actualizado"
        )

        result = await client.call_nlp_service(
            text=command,
            conversation_id=conversation_id,
        )

        cart_response = result.get("response", "Producto eliminado")
        item_count = _parse_cart_items(cart_response)

        # Get cached language for localized buttons
        lang = _get_user_language(callback, chat_id)

        # Build keyboard
        keyboard_rows: list[list[InlineKeyboardButton]] = []
        if item_count > 0:
            keyboard_rows.extend(_build_cart_item_buttons(item_count, conversation_id))
            keyboard_rows.append(_build_cart_action_row(conversation_id, lang))
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        else:
            keyboard = None

        await bot.send_message(
            chat_id=chat_id,
            text=cart_response,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Failed to remove item: %s", e)
        await callback.answer("Error eliminando producto", show_alert=True)
