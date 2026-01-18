"""Message processor service for routing messages to appropriate backends.

This module provides intelligent routing of Telegram messages based on their
type (text, audio, image) to the appropriate processing services (NLP, ASR, OCR).

Architecture:
    Message -> InputClassifier -> MessageProcessor -> InternalServiceClient -> Response

Example:
    from telegram_bot.services.message_processor import MessageProcessor

    processor = MessageProcessor()
    result = await processor.process_text("Hello, how are you?")
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from aiogram import Bot
from aiogram.types import Message

from telegram_bot.logging_config import get_logger
from telegram_bot.services.input_classifier import InputType
from telegram_bot.services.internal_client import get_client

logger = get_logger("message_processor")

# =============================================================================
# Internationalized Error Messages
# =============================================================================
ERROR_MESSAGES: dict[str, dict[str, str]] = {
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

DEFAULT_LANGUAGE = "es"

# Exact match threshold for image search (Google Lens style)
# Only products with ≥80% similarity are considered "exact matches"
# Products below this threshold trigger text-based search instead
EXACT_MATCH_THRESHOLD = 0.80


def _extract_error_code(error: Exception) -> str | None:
    """Extract error_code from an HTTP error response.

    Args:
        error: Exception that may contain error response data.

    Returns:
        Error code string if found, None otherwise.
    """
    import httpx

    if isinstance(error, httpx.HTTPStatusError):
        try:
            response_data: dict[str, Any] = error.response.json()
            error_code: str | None = response_data.get("error_code")
            return error_code
        except Exception:
            pass
    return None


def _get_message(key: str, language_code: str | None) -> str:
    """Get localized error message based on user's language.

    Args:
        key: Message key (e.g., 'asr_failed', 'nlp_failed')
        language_code: User's language code (e.g., 'en', 'es', 'en-US')

    Returns:
        Localized message string
    """
    # Handle codes like 'en-US' -> 'en'
    lang = language_code.split("-")[0].lower() if language_code else DEFAULT_LANGUAGE
    messages = ERROR_MESSAGES.get(lang, ERROR_MESSAGES[DEFAULT_LANGUAGE])
    return messages.get(key, ERROR_MESSAGES[DEFAULT_LANGUAGE][key])


class ProcessingStatus(str, Enum):
    """Status of message processing."""

    SUCCESS = "success"
    ERROR = "error"
    UNSUPPORTED = "unsupported"
    NO_CONTENT = "no_content"


@dataclass
class ProductCard:
    """Product card for carousel display.

    Attributes:
        sku: Product SKU/code
        name: Product name
        brand: Product brand
        description: Product description
        price: Product price
        image_url: URL to product image
        similarity: Match similarity score (0-1)
        match_type: 'exact' or 'similar'
    """

    sku: str
    name: str
    brand: str | None
    description: str | None
    price: float | None
    image_url: str | None
    similarity: float
    match_type: str


@dataclass
class ProcessingResult:
    """Result of message processing.

    Attributes:
        status: Processing status
        response: Response text to send to user
        input_type: Type of input that was processed
        raw_response: Raw response from the backend service
        error: Error message if processing failed
        product_carousel: List of products to display as carousel (optional)
    """

    status: ProcessingStatus
    response: str
    input_type: InputType
    raw_response: dict[str, Any] | None = None
    error: str | None = None
    product_carousel: list[ProductCard] | None = None


def _extract_user_info(message: Message) -> dict[str, Any] | None:
    """Extract user information from a Telegram message for tracking.

    Args:
        message: The Telegram message object.

    Returns:
        Dictionary with user info for NLP service, or None if no user info.
    """
    if not message.from_user:
        return None

    user = message.from_user
    return {
        "channel": "telegram",
        "external_id": str(user.id),
        "first_name": user.first_name or "Unknown",
        "last_name": user.last_name,
        "username": user.username,
        "language_code": user.language_code,
    }


class MessageProcessor:
    """Processor for routing messages to appropriate backend services.

    Routes messages based on their type:
        - TEXT: Sent to NLP service (Gemini)
        - VOICE/AUDIO: Transcribed via ASR, then sent to NLP
        - PHOTO: Processed via OCR (if text extraction needed)
        - Other types: Returns unsupported message
    """

    def __init__(self) -> None:
        """Initialize the message processor."""
        self._client = get_client()

    async def process_message(
        self,
        message: Message,
        input_type: InputType,
        bot: Bot,
    ) -> ProcessingResult:
        """Process a message based on its type.

        Routes the message to the appropriate backend service based on
        the classified input type.

        Args:
            message: The Telegram message to process
            input_type: The classified type of the message
            bot: The Bot instance for downloading files

        Returns:
            ProcessingResult with the response or error
        """
        logger.info(
            "Processing message type=%s from chat_id=%d",
            input_type.value,
            message.chat.id,
        )

        match input_type:
            case InputType.TEXT:
                return await self._process_text_message(message)
            case InputType.VOICE | InputType.AUDIO:
                return await self._process_audio_message(message, bot)
            case InputType.PHOTO:
                return await self._process_photo_message(message, bot)
            case InputType.COMMAND:
                # Commands are handled by command handlers, not here
                return ProcessingResult(
                    status=ProcessingStatus.SUCCESS,
                    response="",
                    input_type=input_type,
                )
            case _:
                lang = message.from_user.language_code if message.from_user else None
                return ProcessingResult(
                    status=ProcessingStatus.UNSUPPORTED,
                    response=_get_message("unsupported", lang),
                    input_type=input_type,
                )

    async def _process_text_message(self, message: Message) -> ProcessingResult:
        """Process a text message via NLP service.

        Args:
            message: The text message to process

        Returns:
            ProcessingResult with NLP response
        """
        text = message.text
        lang = message.from_user.language_code if message.from_user else None
        if not text:
            return ProcessingResult(
                status=ProcessingStatus.NO_CONTENT,
                response=_get_message("empty_text", lang),
                input_type=InputType.TEXT,
            )

        # Use chat_id as conversation_id for context continuity
        conversation_id = str(message.chat.id)
        # Extract user info for tracking
        user_info = _extract_user_info(message)
        # Extract language code to pass explicitly to NLP
        # This ensures the model responds in the user's language
        user_language = user_info.get("language_code") if user_info else None
        return await self.process_text(
            text,
            conversation_id=conversation_id,
            user_info=user_info,
            detected_language=user_language,
        )

    async def process_text(
        self,
        text: str,
        conversation_id: str | None = None,
        user_info: dict[str, Any] | None = None,
        detected_language: str | None = None,
    ) -> ProcessingResult:
        """Process text via NLP service.

        Args:
            text: The text to process
            conversation_id: Optional conversation ID for context continuity
            user_info: Optional user information for tracking
            detected_language: Optional language detected from ASR.
                Takes priority over user_info.language_code.

        Returns:
            ProcessingResult with NLP response
        """
        try:
            result = await self._client.call_nlp_service(
                text,
                conversation_id=conversation_id,
                user_info=user_info,
                detected_language=detected_language,
            )
            response = result.get("response", "")

            return ProcessingResult(
                status=ProcessingStatus.SUCCESS,
                response=response,
                input_type=InputType.TEXT,
                raw_response=result,
            )
        except Exception as e:
            logger.exception("NLP service error: %s", e)
            lang = user_info.get("language_code") if user_info else None
            return ProcessingResult(
                status=ProcessingStatus.ERROR,
                response=_get_message("nlp_failed", lang),
                input_type=InputType.TEXT,
                error=str(e),
            )

    async def _process_audio_message(
        self,
        message: Message,
        bot: Bot,
    ) -> ProcessingResult:
        """Process an audio/voice message via ASR then NLP.

        Args:
            message: The audio message to process
            bot: The Bot instance for downloading files

        Returns:
            ProcessingResult with transcribed and processed response
        """
        # Get the file (voice or audio)
        file_id = None
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id

        lang = message.from_user.language_code if message.from_user else None
        if not file_id:
            return ProcessingResult(
                status=ProcessingStatus.NO_CONTENT,
                response=_get_message("empty_audio", lang),
                input_type=InputType.VOICE,
            )

        try:
            # Download the audio file
            file = await bot.get_file(file_id)
            if not file.file_path:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=_get_message("download_failed", lang),
                    input_type=InputType.VOICE,
                )

            file_bytes = await bot.download_file(file.file_path)
            if not file_bytes:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=_get_message("download_failed", lang),
                    input_type=InputType.VOICE,
                )

            audio_content = file_bytes.read()

            # Transcribe via ASR (Chirp 2 with auto language detection)
            try:
                asr_result = await self._client.call_asr_service(
                    audio_content=audio_content,
                    filename="voice.ogg",
                )
            except Exception as asr_error:
                # Check if it's a low confidence error from ASR service
                error_code = _extract_error_code(asr_error)
                if error_code == "LOW_CONFIDENCE":
                    logger.warning("ASR low confidence error: %s", asr_error)
                    return ProcessingResult(
                        status=ProcessingStatus.ERROR,
                        response=_get_message("low_confidence", lang),
                        input_type=InputType.VOICE,
                        error=str(asr_error),
                    )
                raise

            # Check for error response from ASR
            if not asr_result.get("success", True):
                error_code = asr_result.get("error_code", "")
                if error_code == "LOW_CONFIDENCE":
                    return ProcessingResult(
                        status=ProcessingStatus.ERROR,
                        response=_get_message("low_confidence", lang),
                        input_type=InputType.VOICE,
                        raw_response=asr_result,
                    )
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=_get_message("asr_failed", lang),
                    input_type=InputType.VOICE,
                    raw_response=asr_result,
                )

            transcribed_text = asr_result.get("data", {}).get("transcription", "")
            if not transcribed_text:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=_get_message("asr_failed", lang),
                    input_type=InputType.VOICE,
                )

            # Log transcription with detected language
            detected_lang = asr_result.get("data", {}).get("language", "unknown")
            confidence = asr_result.get("data", {}).get("confidence", 0)
            logger.info(
                "Audio transcribed: %s (lang=%s, conf=%.2f)",
                transcribed_text[:100],
                detected_lang,
                confidence,
            )

            # Process transcribed text via NLP with conversation context
            # Pass detected language from ASR with priority over Telegram language_code
            conversation_id = str(message.chat.id)
            user_info = _extract_user_info(message)
            nlp_result = await self._client.call_nlp_service(
                transcribed_text,
                conversation_id=conversation_id,
                user_info=user_info,
                detected_language=detected_lang if detected_lang != "unknown" else None,
            )
            response = nlp_result.get("response", "")

            return ProcessingResult(
                status=ProcessingStatus.SUCCESS,
                response=response,
                input_type=InputType.VOICE,
                raw_response={
                    "asr": asr_result,
                    "nlp": nlp_result,
                    "transcribed_text": transcribed_text,
                },
            )

        except Exception as e:
            logger.exception("Audio processing error: %s", e)
            # Check for low confidence in exception message
            error_code = _extract_error_code(e)
            if error_code == "LOW_CONFIDENCE":
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=_get_message("low_confidence", lang),
                    input_type=InputType.VOICE,
                    error=str(e),
                )
            return ProcessingResult(
                status=ProcessingStatus.ERROR,
                response=_get_message("asr_failed", lang),
                input_type=InputType.VOICE,
                error=str(e),
            )

    async def _process_photo_message(
        self,
        message: Message,
        bot: Bot,
    ) -> ProcessingResult:
        """Process a photo message via OCR then NLP.

        Args:
            message: The photo message to process
            bot: The Bot instance for downloading files

        Returns:
            ProcessingResult with OCR extracted text and NLP response
        """
        lang = message.from_user.language_code if message.from_user else None
        if not message.photo:
            return ProcessingResult(
                status=ProcessingStatus.NO_CONTENT,
                response=_get_message("ocr_failed", lang),
                input_type=InputType.PHOTO,
            )

        try:
            # Get the largest photo (last in the list)
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)

            if not file.file_path:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=_get_message("download_failed", lang),
                    input_type=InputType.PHOTO,
                )

            file_bytes = await bot.download_file(file.file_path)
            if not file_bytes:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=_get_message("download_failed", lang),
                    input_type=InputType.PHOTO,
                )

            image_content = file_bytes.read()

            # Build client_id in required format user_id:chat_id
            user_id = str(message.from_user.id) if message.from_user else "unknown"
            chat_id = str(message.chat.id)
            client_id = f"{user_id}:{chat_id}"

            # Analyze image (auto-classifies and routes to OCR or Detection)
            analyze_result = await self._client.call_analyze_service(
                file_content=image_content,
                filename="photo.jpg",
                mime_type="image/jpeg",
                client_id=client_id,
            )

            # Extract classification info
            classification = analyze_result.get("classification", {})
            predicted_type = classification.get("predicted_type", "unknown")
            confidence = classification.get("confidence", 0)
            result_text = analyze_result.get("result", "")
            image_embedding = analyze_result.get("image_embedding")

            logger.info(
                "Image analyzed: type=%s, confidence=%.2f, result=%s, has_embedding=%s",
                predicted_type,
                confidence,
                result_text[:100] if result_text else "empty",
                image_embedding is not None,
            )

            # Build context for conversation
            conversation_id = str(message.chat.id)
            user_info = _extract_user_info(message)

            # =========================================================================
            # PRIORITY 1: Document with significant text -> OCR + NLP
            # =========================================================================
            if predicted_type == "document" and result_text:
                logger.info("Priority 1: Processing as document with OCR text")
                nlp_prompt = (
                    "El usuario ha enviado una imagen y he extraído el siguiente texto de ella:\n\n"
                    f'"""\n{result_text}\n"""\n\n'
                    "Por favor, ayuda al usuario interpretando este texto. "
                    "Si es un documento, resume su contenido. "
                    "Si son datos o una lista, organízalos. "
                    "Si es un mensaje o nota, responde apropiadamente. "
                    "Si el texto no tiene sentido o está incompleto, indica qué pudiste identificar."
                )

                nlp_result = await self._client.call_nlp_service(
                    nlp_prompt,
                    conversation_id=conversation_id,
                    user_info=user_info,
                )

                return ProcessingResult(
                    status=ProcessingStatus.SUCCESS,
                    response=nlp_result.get("response", ""),
                    input_type=InputType.PHOTO,
                    raw_response={
                        "analyze": analyze_result,
                        "classification": classification,
                        "nlp": nlp_result,
                        "result_text": result_text,
                        "priority": "document_ocr",
                    },
                )

            # =========================================================================
            # PRIORITY 2: Search products by image similarity
            # - Exact match (≥80%) → Return immediately with carousel
            # - Similar products (<80%) → Save carousel for Priority 3
            # =========================================================================
            similar_carousel: list[ProductCard] | None = None

            if image_embedding:
                logger.info("Priority 2: Searching products by image similarity")
                try:
                    search_result = await self._client.search_products_by_embedding(
                        embedding=image_embedding,
                        limit=5,
                        max_distance=0.5,  # Broader search to find similar products
                    )

                    if search_result.get("found") and search_result.get("products"):
                        products = search_result["products"]
                        best_similarity = products[0].get("similarity", 0)
                        logger.info(
                            "Image search found %d products (best: %.3f)",
                            len(products),
                            best_similarity,
                        )

                        # Build carousel for ALL found products
                        carousel_cards: list[ProductCard] = []
                        for p in products:
                            if p.get("image_url"):
                                is_exact = (
                                    p.get("similarity", 0) >= EXACT_MATCH_THRESHOLD
                                )
                                carousel_cards.append(
                                    ProductCard(
                                        sku=p.get("sku", "N/A"),
                                        name=p.get("name", "Producto"),
                                        brand=p.get("brand"),
                                        description=p.get("description"),
                                        price=p.get("price"),
                                        image_url=p.get("image_url"),
                                        similarity=p.get("similarity", 0),
                                        match_type="exact" if is_exact else "similar",
                                    )
                                )

                        # Exact match: return immediately
                        if best_similarity >= EXACT_MATCH_THRESHOLD:
                            product_name = products[0].get("name", "Producto")
                            intro_response = (
                                f"¡Encontré lo que buscas! Aquí tienes: {product_name}."
                            )

                            return ProcessingResult(
                                status=ProcessingStatus.SUCCESS,
                                response=intro_response,
                                input_type=InputType.PHOTO,
                                raw_response={
                                    "analyze": analyze_result,
                                    "classification": classification,
                                    "image_search": search_result,
                                    "priority": "exact_match",
                                },
                                product_carousel=carousel_cards
                                if carousel_cards
                                else None,
                            )

                        # Similar products found: save carousel for Priority 3
                        if carousel_cards:
                            similar_carousel = carousel_cards
                            logger.info(
                                "Saving %d similar products for carousel (best: %.3f)",
                                len(carousel_cards),
                                best_similarity,
                            )

                except Exception as e:
                    logger.warning("Image search failed: %s", e)
                    # Continue to priority 3

            # =========================================================================
            # PRIORITY 3: Process object name as user text + show similar products
            # Combines NLP response with product carousel (if available)
            # =========================================================================
            if result_text:
                logger.info(
                    "Priority 3: Processing object name as user text: %s", result_text
                )
                # Extract user's language to ensure NLP responds in correct language
                user_language = user_info.get("language_code") if user_info else None
                text_result = await self.process_text(
                    text=result_text,
                    conversation_id=conversation_id,
                    user_info=user_info,
                    detected_language=user_language,
                )
                # Add carousel if we found similar products
                if similar_carousel:
                    text_result.product_carousel = similar_carousel
                    text_result.raw_response = {
                        **(text_result.raw_response or {}),
                        "priority": "text_with_similar_products",
                        "similar_count": len(similar_carousel),
                    }
                return text_result

            # No content extracted from image
            return ProcessingResult(
                status=ProcessingStatus.SUCCESS,
                response=_get_message("no_text_in_image", lang),
                input_type=InputType.PHOTO,
                raw_response=analyze_result,
            )

        except Exception as e:
            logger.exception("Photo processing error: %s", e)
            return ProcessingResult(
                status=ProcessingStatus.ERROR,
                response=_get_message("ocr_failed", lang),
                input_type=InputType.PHOTO,
                error=str(e),
            )


# Singleton instance
_processor: MessageProcessor | None = None


def get_processor() -> MessageProcessor:
    """Get the singleton message processor instance."""
    global _processor
    if _processor is None:
        _processor = MessageProcessor()
    return _processor
