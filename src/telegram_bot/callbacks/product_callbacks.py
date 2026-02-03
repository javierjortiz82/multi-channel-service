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
    build_product_keyboard,
    format_product_caption,
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

        if action == "details":
            await _handle_details(callback, product_id, chat_id, bot)
        elif action == "cart":
            await _handle_add_to_cart(callback, product_id, chat_id, bot)
        elif action == "prev":
            await _handle_navigation(callback, chat_id, page - 1, total, bot)
        elif action == "next":
            await _handle_navigation(callback, chat_id, page + 1, total, bot)
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


async def _handle_details(
    callback: CallbackQuery,
    product_id: int,
    chat_id: int,
    bot: Bot,
) -> None:
    """Handle product details request.

    Shows full product details with expanded description.

    Args:
        callback: The callback query
        product_id: Product ID to show details for
        chat_id: The chat ID
        bot: The Bot instance
    """
    await callback.answer()

    # Get product from cache
    cache = get_product_cache()
    products = cache.get(chat_id)

    # Find product by ID
    product = next((p for p in products if p.get("id") == product_id), None)

    if not product:
        await callback.answer("Producto no encontrado", show_alert=True)
        return

    # Build detailed view
    name = product.get("name", "Producto")
    price_raw = product.get("price", 0)
    description = product.get("description", "Sin descripción")
    brand = product.get("brand", "")
    category = product.get("category", "")
    sku = product.get("sku", "")

    # Real estate fields
    bedrooms = product.get("bedrooms", "")
    bathrooms = product.get("bathrooms", "")
    sqft_raw = product.get("sqft", "")
    location = product.get("location", "")

    # Format price (handle string/int/float)
    try:
        price = float(price_raw) if price_raw else 0
        price_str = f"${price:,.0f}" if price >= 1_000_000 else f"${price:,.2f}"
    except (ValueError, TypeError):
        price_str = str(price_raw) if price_raw else "Consultar"

    # Format sqft (handle string/int/float)
    try:
        sqft = int(float(sqft_raw)) if sqft_raw else 0
    except (ValueError, TypeError):
        sqft = 0

    # Build detailed message
    details = f"<b>📦 {name}</b>\n\n"
    details += f"💰 <b>Precio:</b> {price_str}\n"

    if brand:
        details += f"🏷️ <b>Marca:</b> {brand}\n"
    if category:
        details += f"📁 <b>Categoría:</b> {category}\n"
    if sku:
        details += f"🔢 <b>SKU:</b> {sku}\n"

    # Real estate details
    if location:
        details += f"📍 <b>Ubicación:</b> {location}\n"
    if bedrooms:
        details += f"🛏️ <b>Habitaciones:</b> {bedrooms}\n"
    if bathrooms:
        details += f"🚿 <b>Baños:</b> {bathrooms}\n"
    if sqft:
        details += f"📐 <b>Área:</b> {sqft:,} sq ft\n"

    details += f"\n<b>Descripción:</b>\n{description}"

    # Back button
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Agregar al Carrito",
                    callback_data=ProductCallback(
                        action="cart",
                        product_id=product_id,
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Volver",
                    callback_data=ProductCallback(
                        action="back",
                        product_id=product_id,
                        page=0,
                        total=len(products),
                    ).pack(),
                ),
            ],
        ]
    )

    # Send details message
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=details,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error("Failed to send product details: %s", e)
        await callback.answer("Error mostrando detalles", show_alert=True)


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

        # Build keyboard with "Ver Carrito" button
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 Ver Carrito",
                        callback_data=CartCallback(
                            action="view",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                ],
            ]
        )

        # Always send confirmation with product name (NLP response may be empty)
        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ <b>{product_name}</b> agregado al carrito",
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
    keyboard = build_product_keyboard(
        product_id=product.get("id", 0),
        page=new_page,
        total=total,
        show_pagination=True,
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
    import re

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

            # Add checkout and clear buttons at the bottom
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text="💳 Pagar",
                        callback_data=CartCallback(
                            action="checkout",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="🗑️ Vaciar Todo",
                        callback_data=CartCallback(
                            action="clear",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                ]
            )

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
    action_text = "Aumentando" if delta > 0 else "Reduciendo"
    await callback.answer(f"{action_text} cantidad...")

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

        # Build keyboard
        keyboard_rows: list[list[InlineKeyboardButton]] = []
        if item_count > 0:
            keyboard_rows.extend(_build_cart_item_buttons(item_count, conversation_id))
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text="💳 Pagar",
                        callback_data=CartCallback(
                            action="checkout",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="🗑️ Vaciar Todo",
                        callback_data=CartCallback(
                            action="clear",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                ]
            )
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

    # Build confirmation keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Sí, eliminar",
                    callback_data=CartItemCallback(
                        action="confirm_del",
                        item_idx=item_idx,
                        conv_id=conversation_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ No, cancelar",
                    callback_data=CartItemCallback(
                        action="cancel_del",
                        item_idx=item_idx,
                        conv_id=conversation_id,
                    ).pack(),
                ),
            ],
        ]
    )

    await bot.send_message(
        chat_id=chat_id,
        text=f"🗑️ <b>¿Eliminar el item {item_idx} del carrito?</b>",
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
    await callback.answer("Eliminando producto...")

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

        # Build keyboard
        keyboard_rows: list[list[InlineKeyboardButton]] = []
        if item_count > 0:
            keyboard_rows.extend(_build_cart_item_buttons(item_count, conversation_id))
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text="💳 Pagar",
                        callback_data=CartCallback(
                            action="checkout",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="🗑️ Vaciar Todo",
                        callback_data=CartCallback(
                            action="clear",
                            conversation_id=conversation_id,
                        ).pack(),
                    ),
                ]
            )
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
