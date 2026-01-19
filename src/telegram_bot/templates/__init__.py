"""Template management for message rendering.

This module provides a centralized template manager using Jinja2 for
rendering user-facing messages, product displays, and NLP prompts.

Example:
    from telegram_bot.templates import templates

    # Render error message
    msg = templates.render_error("nlp_failed", "es")

    # Render product list
    html = templates.render_product_list(products, has_exact_match=True)

    # Render command response
    msg = templates.render_command("start")
"""

from pathlib import Path
from typing import Any, Final

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Error messages by language (following FastAPI settings pattern)
ERROR_MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "nlp_failed": "Sorry, there was an error processing your message. Please try again.",
        "asr_failed": "I couldn't transcribe the audio. Please try again.",
        "ocr_failed": "I couldn't process the image. Please try again.",
        "download_failed": "I couldn't download the file. Please try again.",
        "empty_text": "I didn't receive any text to process.",
        "empty_audio": "I couldn't get the audio from the message.",
        "unsupported": "This content type is not supported yet. Please send text or audio.",
        "no_text_in_image": "I received your image, but I couldn't find any text to process.",
        "low_confidence": "I couldn't clearly understand the audio. Please speak more slowly and clearly, or reduce background noise.",
        "product_not_found": "I couldn't find similar products in our catalog. Can I help you with something else?",
    },
    "es": {
        "nlp_failed": "Lo siento, hubo un error procesando tu mensaje. Por favor intenta de nuevo.",
        "asr_failed": "No pude transcribir el audio. Por favor intenta de nuevo.",
        "ocr_failed": "No pude procesar la imagen. Por favor intenta de nuevo.",
        "download_failed": "No pude descargar el archivo. Por favor intenta de nuevo.",
        "empty_text": "No recibí ningún texto para procesar.",
        "empty_audio": "No pude obtener el audio del mensaje.",
        "unsupported": "Este tipo de contenido no está soportado aún. Por favor envía texto o audio.",
        "no_text_in_image": "He recibido tu imagen, pero no encontré texto para procesar.",
        "low_confidence": "No pude entender claramente el audio. Por favor, habla más despacio y claro, o reduce el ruido de fondo.",
        "product_not_found": "No encontré productos similares a tu imagen en nuestro catálogo. ¿Puedo ayudarte con algo más?",
    },
    "pt": {
        "nlp_failed": "Desculpe, houve um erro ao processar sua mensagem. Por favor, tente novamente.",
        "asr_failed": "Não consegui transcrever o áudio. Por favor, tente novamente.",
        "ocr_failed": "Não consegui processar a imagem. Por favor, tente novamente.",
        "download_failed": "Não consegui baixar o arquivo. Por favor, tente novamente.",
        "empty_text": "Não recebi nenhum texto para processar.",
        "empty_audio": "Não consegui obter o áudio da mensagem.",
        "unsupported": "Este tipo de conteúdo ainda não é suportado. Por favor, envie texto ou áudio.",
        "no_text_in_image": "Recebi sua imagem, mas não encontrei texto para processar.",
        "low_confidence": "Não consegui entender claramente o áudio. Por favor, fale mais devagar e claramente, ou reduza o ruído de fundo.",
        "product_not_found": "Não encontrei produtos semelhantes à sua imagem em nosso catálogo. Posso ajudá-lo com algo mais?",
    },
    "fr": {
        "nlp_failed": "Désolé, une erreur s'est produite lors du traitement de votre message. Veuillez réessayer.",
        "asr_failed": "Je n'ai pas pu transcrire l'audio. Veuillez réessayer.",
        "ocr_failed": "Je n'ai pas pu traiter l'image. Veuillez réessayer.",
        "download_failed": "Je n'ai pas pu télécharger le fichier. Veuillez réessayer.",
        "empty_text": "Je n'ai reçu aucun texte à traiter.",
        "empty_audio": "Je n'ai pas pu obtenir l'audio du message.",
        "unsupported": "Ce type de contenu n'est pas encore pris en charge. Veuillez envoyer du texte ou de l'audio.",
        "no_text_in_image": "J'ai reçu votre image, mais je n'ai trouvé aucun texte à traiter.",
        "low_confidence": "Je n'ai pas pu comprendre clairement l'audio. Veuillez parler plus lentement et clairement, ou réduire le bruit de fond.",
        "product_not_found": "Je n'ai pas trouvé de produits similaires à votre image dans notre catalogue. Puis-je vous aider avec autre chose?",
    },
    "ar": {
        "nlp_failed": "عذراً، حدث خطأ أثناء معالجة رسالتك. يرجى المحاولة مرة أخرى.",
        "asr_failed": "لم أتمكن من تحويل الصوت إلى نص. يرجى المحاولة مرة أخرى.",
        "ocr_failed": "لم أتمكن من معالجة الصورة. يرجى المحاولة مرة أخرى.",
        "download_failed": "لم أتمكن من تحميل الملف. يرجى المحاولة مرة أخرى.",
        "empty_text": "لم أستلم أي نص للمعالجة.",
        "empty_audio": "لم أتمكن من الحصول على الصوت من الرسالة.",
        "unsupported": "هذا النوع من المحتوى غير مدعوم حالياً. يرجى إرسال نص أو صوت.",
        "no_text_in_image": "استلمت صورتك، لكن لم أجد أي نص للمعالجة.",
        "low_confidence": "لم أتمكن من فهم الصوت بوضوح. يرجى التحدث ببطء ووضوح أكثر، أو تقليل الضوضاء المحيطة.",
        "product_not_found": "لم أجد منتجات مشابهة لصورتك في كتالوجنا. هل يمكنني مساعدتك بشيء آخر؟",
    },
}

# Fallback message for unknown keys
DEFAULT_ERROR: Final[str] = "An error occurred. Please try again."

# Product display messages by language
PRODUCT_MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "exact_match_header": "✅ <b>I found products that match your image!</b>",
        "similar_header": "🔍 <b>We don't have that exact product, but I found similar options:</b>",
        "ask_interest": "Are you interested in any of these products?",
        "price_contact": "Contact us",
        "similarity_label": "Similarity",
        "exact_match_intro": "I found what you're looking for! Here it is: {product_name}.",
        "product_fallback": "Product",
    },
    "es": {
        "exact_match_header": "✅ <b>¡Encontré productos que coinciden con tu imagen!</b>",
        "similar_header": "🔍 <b>No tenemos exactamente ese producto, pero encontré opciones similares:</b>",
        "ask_interest": "¿Te interesa alguno de estos productos?",
        "price_contact": "Consultar",
        "similarity_label": "Similitud",
        "exact_match_intro": "¡Encontré lo que buscas! Aquí tienes: {product_name}.",
        "product_fallback": "Producto",
    },
    "pt": {
        "exact_match_header": "✅ <b>Encontrei produtos que correspondem à sua imagem!</b>",
        "similar_header": "🔍 <b>Não temos exatamente esse produto, mas encontrei opções similares:</b>",
        "ask_interest": "Você tem interesse em algum desses produtos?",
        "price_contact": "Consultar",
        "similarity_label": "Similaridade",
        "exact_match_intro": "Encontrei o que você procura! Aqui está: {product_name}.",
        "product_fallback": "Produto",
    },
    "fr": {
        "exact_match_header": "✅ <b>J'ai trouvé des produits qui correspondent à votre image!</b>",
        "similar_header": "🔍 <b>Nous n'avons pas exactement ce produit, mais j'ai trouvé des options similaires:</b>",
        "ask_interest": "L'un de ces produits vous intéresse-t-il?",
        "price_contact": "Nous contacter",
        "similarity_label": "Similarité",
        "exact_match_intro": "J'ai trouvé ce que vous cherchez! Le voici: {product_name}.",
        "product_fallback": "Produit",
    },
    "ar": {
        "exact_match_header": "✅ <b>وجدت منتجات تطابق صورتك!</b>",
        "similar_header": "🔍 <b>ليس لدينا هذا المنتج بالضبط، لكن وجدت خيارات مشابهة:</b>",
        "ask_interest": "هل أنت مهتم بأي من هذه المنتجات؟",
        "price_contact": "اتصل بنا",
        "similarity_label": "التشابه",
        "exact_match_intro": "وجدت ما تبحث عنه! ها هو: {product_name}.",
        "product_fallback": "منتج",
    },
}

# Command response messages by language
COMMAND_MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "start": """<b>Welcome!</b> 👋

I'm a Telegram bot with webhook support.

I can process different types of messages:
• Text
• Photos
• Documents
• Videos
• Audio
• Locations
• And more...

Use /help to see available commands.""",
        "help": """<b>Available commands:</b>

/start - Start the bot
/help - Show this help

<b>Supported content types:</b>
• Text messages
• Photos and images
• Documents and files
• Videos and animations
• Voice and audio messages
• Locations and places
• Contacts
• Polls
• Stickers""",
    },
    "es": {
        "start": """<b>¡Bienvenido!</b> 👋

Soy un bot de Telegram con soporte para webhook.

Puedo procesar diferentes tipos de mensajes:
• Texto
• Fotos
• Documentos
• Videos
• Audio
• Ubicaciones
• Y más...

Usa /help para ver los comandos disponibles.""",
        "help": """<b>Comandos disponibles:</b>

/start - Iniciar el bot
/help - Mostrar esta ayuda

<b>Tipos de contenido soportados:</b>
• Mensajes de texto
• Fotos e imágenes
• Documentos y archivos
• Videos y animaciones
• Mensajes de voz y audio
• Ubicaciones y lugares
• Contactos
• Encuestas
• Stickers""",
    },
    "pt": {
        "start": """<b>Bem-vindo!</b> 👋

Sou um bot do Telegram com suporte a webhook.

Posso processar diferentes tipos de mensagens:
• Texto
• Fotos
• Documentos
• Vídeos
• Áudio
• Localizações
• E mais...

Use /help para ver os comandos disponíveis.""",
        "help": """<b>Comandos disponíveis:</b>

/start - Iniciar o bot
/help - Mostrar esta ajuda

<b>Tipos de conteúdo suportados:</b>
• Mensagens de texto
• Fotos e imagens
• Documentos e arquivos
• Vídeos e animações
• Mensagens de voz e áudio
• Localizações e lugares
• Contatos
• Enquetes
• Stickers""",
    },
    "fr": {
        "start": """<b>Bienvenue!</b> 👋

Je suis un bot Telegram avec support webhook.

Je peux traiter différents types de messages:
• Texte
• Photos
• Documents
• Vidéos
• Audio
• Localisations
• Et plus...

Utilisez /help pour voir les commandes disponibles.""",
        "help": """<b>Commandes disponibles:</b>

/start - Démarrer le bot
/help - Afficher cette aide

<b>Types de contenu pris en charge:</b>
• Messages texte
• Photos et images
• Documents et fichiers
• Vidéos et animations
• Messages vocaux et audio
• Localisations et lieux
• Contacts
• Sondages
• Stickers""",
    },
    "ar": {
        "start": """<b>مرحباً!</b> 👋

أنا بوت تيليجرام مع دعم webhook.

يمكنني معالجة أنواع مختلفة من الرسائل:
• النص
• الصور
• المستندات
• الفيديوهات
• الصوت
• المواقع
• والمزيد...

استخدم /help لرؤية الأوامر المتاحة.""",
        "help": """<b>الأوامر المتاحة:</b>

/start - بدء البوت
/help - عرض هذه المساعدة

<b>أنواع المحتوى المدعومة:</b>
• الرسائل النصية
• الصور
• المستندات والملفات
• الفيديوهات والرسوم المتحركة
• الرسائل الصوتية
• المواقع والأماكن
• جهات الاتصال
• الاستطلاعات
• الملصقات""",
    },
}

# Template directory relative to this module
TEMPLATES_DIR = Path(__file__).parent


def _escape_html(text: str | None) -> str:
    """Escape HTML special characters for Telegram's HTML parse mode.

    Args:
        text: The text to escape, or None.

    Returns:
        Text with HTML special characters escaped, or empty string if None.
    """
    if text is None:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_price(
    price: float | None, currency: str = "$", contact_text: str = "Contact us"
) -> str:
    """Format price for display.

    Args:
        price: The price value, or None.
        currency: Currency symbol (default: $).
        contact_text: Text to show when price is None.

    Returns:
        Formatted price string, or contact text if None.
    """
    if price is None:
        return contact_text
    return f"{currency}{price:.2f}"


def _format_percent(value: float) -> str:
    """Format a float as percentage.

    Args:
        value: The value (0-1).

    Returns:
        Formatted percentage string (e.g., "85%").
    """
    return f"{value:.0%}"


def _truncate(text: str | None, length: int = 100) -> str:
    """Truncate text to specified length with ellipsis.

    Args:
        text: The text to truncate, or None.
        length: Maximum length (default: 100).

    Returns:
        Truncated text with ellipsis if needed.
    """
    if text is None:
        return ""
    if len(text) <= length:
        return text
    return text[:length] + "..."


class TemplateManager:
    """Jinja2 template manager for message rendering.

    Provides methods to render various template types with proper
    localization, escaping, and formatting.

    Attributes:
        env: The Jinja2 Environment instance.
    """

    # Supported languages for error messages
    SUPPORTED_LANGUAGES = {"es", "en", "pt", "fr", "ar"}
    DEFAULT_LANGUAGE = "en"

    def __init__(self) -> None:
        """Initialize the template manager with Jinja2 environment."""
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.env.filters["escape_html"] = _escape_html
        self.env.filters["format_price"] = _format_price
        self.env.filters["format_percent"] = _format_percent
        self.env.filters["truncate_text"] = _truncate

    def _normalize_language(self, language_code: str | None) -> str:
        """Normalize language code to supported language.

        Handles codes like 'en-US' -> 'en', falls back to default if unsupported.

        Args:
            language_code: User's language code (e.g., 'en', 'es', 'en-US').

        Returns:
            Normalized language code from supported set.
        """
        if not language_code:
            return self.DEFAULT_LANGUAGE
        # Extract base language (e.g., 'en-US' -> 'en')
        base_lang = language_code.split("-")[0].lower()
        if base_lang in self.SUPPORTED_LANGUAGES:
            return base_lang
        return self.DEFAULT_LANGUAGE

    def render(self, template_name: str, **context: Any) -> str:
        """Render a template with the given context.

        Args:
            template_name: Path to template file (e.g., 'messages/errors/es.j2').
            **context: Variables to pass to the template.

        Returns:
            Rendered template string.

        Raises:
            jinja2.TemplateNotFound: If template file doesn't exist.
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_error(self, key: str, language_code: str | None = None) -> str:
        """Get localized error message.

        Args:
            key: Error key (e.g., 'nlp_failed', 'asr_failed').
            language_code: User's language code.

        Returns:
            Localized error message.
        """
        lang = self._normalize_language(language_code)
        messages = ERROR_MESSAGES.get(lang, ERROR_MESSAGES[self.DEFAULT_LANGUAGE])
        return messages.get(key, DEFAULT_ERROR)

    def render_command(self, command: str, language_code: str | None = None) -> str:
        """Get localized command response.

        Args:
            command: Command name ('start' or 'help').
            language_code: User's language code.

        Returns:
            Localized command response HTML string.
        """
        lang = self._normalize_language(language_code)
        msgs = COMMAND_MESSAGES.get(lang, COMMAND_MESSAGES[self.DEFAULT_LANGUAGE])
        return msgs.get(command, "")

    def render_product_list(
        self,
        products: list[Any],
        has_exact_match: bool = False,
        language_code: str | None = None,
    ) -> str:
        """Render a list of products as text.

        Args:
            products: List of product objects.
            has_exact_match: Whether any product is an exact match.
            language_code: User's language code for localization.

        Returns:
            Formatted product list HTML.
        """
        lang = self._normalize_language(language_code)
        msgs = PRODUCT_MESSAGES.get(lang, PRODUCT_MESSAGES[self.DEFAULT_LANGUAGE])

        lines: list[str] = []

        # Header
        if has_exact_match:
            lines.append(msgs["exact_match_header"])
        else:
            lines.append(msgs["similar_header"])
        lines.append("")

        # Product cards (limit to 5)
        for idx, product in enumerate(products[:5], start=1):
            lines.append(self._format_product_card(product, idx, msgs))
            lines.append("")

        # Footer
        lines.append(msgs["ask_interest"])

        return "\n".join(lines)

    def _format_product_card(
        self, product: Any, index: int, msgs: dict[str, str]
    ) -> str:
        """Format a single product card.

        Args:
            product: Product object with name, brand, description, price, etc.
            index: Product index (1-based).
            msgs: Localized messages dictionary.

        Returns:
            Formatted product card string.
        """
        name = _escape_html(getattr(product, "name", ""))
        brand = getattr(product, "brand", None)
        description = getattr(product, "description", None)
        price = getattr(product, "price", None)
        similarity = getattr(product, "similarity", 0)
        sku = getattr(product, "sku", "N/A")

        card_lines = [f"<b>{index}. {name}</b>"]

        if brand:
            card_lines.append(f"   🏢 {_escape_html(brand)}")

        if description:
            card_lines.append(f"   📝 {_escape_html(_truncate(description, 100))}")

        price_str = _format_price(price, "$", msgs["price_contact"])
        similarity_str = _format_percent(similarity)
        card_lines.append(
            f"   💰 {price_str} | {msgs['similarity_label']}: {similarity_str}"
        )
        card_lines.append(f"   📦 SKU: {sku}")

        return "\n".join(card_lines)

    def get_product_message(
        self, key: str, language_code: str | None = None, **kwargs: Any
    ) -> str:
        """Get a localized product-related message.

        Args:
            key: Message key (e.g., 'exact_match_intro', 'product_fallback').
            language_code: User's language code.
            **kwargs: Format arguments for the message.

        Returns:
            Localized message string.
        """
        lang = self._normalize_language(language_code)
        msgs = PRODUCT_MESSAGES.get(lang, PRODUCT_MESSAGES[self.DEFAULT_LANGUAGE])
        message = msgs.get(key, "")
        if kwargs:
            return message.format(**kwargs)
        return message

    def render_document_prompt(self, extracted_text: str) -> str:
        """Render the NLP prompt for document analysis.

        Args:
            extracted_text: Text extracted from OCR.

        Returns:
            Formatted prompt for NLP service.
        """
        return self.render(
            "prompts/document_analysis.j2",
            extracted_text=extracted_text,
        )

    def format_nlp_products(
        self,
        products: list[dict[str, Any]],
        language_code: str | None = None,
        limit: int = 5,
    ) -> str:
        """Format products from NLP service response for Telegram display.

        Uses Jinja2 template for elegant card format with image links.

        Args:
            products: List of product dictionaries with keys:
                - sku: Product SKU/code
                - name: Product name
                - brand: Product brand (optional)
                - price: Product price (optional)
                - description: Short description (optional)
                - category: Product category (optional)
                - image_url: URL to product image (optional)
            language_code: User's language code for localization.
            limit: Maximum number of products to display (default: 5).

        Returns:
            Formatted product list as Telegram HTML string.
        """
        if not products:
            return ""

        lang = self._normalize_language(language_code)
        msgs = PRODUCT_MESSAGES.get(lang, PRODUCT_MESSAGES[self.DEFAULT_LANGUAGE])

        return self.render(
            "products/list_products.j2",
            products=products,
            msgs=msgs,
            limit=limit,
        )


# Singleton instance for global access
templates = TemplateManager()

__all__ = [
    "templates",
    "TemplateManager",
    "ERROR_MESSAGES",
    "DEFAULT_ERROR",
    "PRODUCT_MESSAGES",
    "COMMAND_MESSAGES",
]
