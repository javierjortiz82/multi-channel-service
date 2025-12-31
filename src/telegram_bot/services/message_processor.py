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


class ProcessingStatus(str, Enum):
    """Status of message processing."""

    SUCCESS = "success"
    ERROR = "error"
    UNSUPPORTED = "unsupported"
    NO_CONTENT = "no_content"


@dataclass
class ProcessingResult:
    """Result of message processing.

    Attributes:
        status: Processing status
        response: Response text to send to user
        input_type: Type of input that was processed
        raw_response: Raw response from the backend service
        error: Error message if processing failed
    """

    status: ProcessingStatus
    response: str
    input_type: InputType
    raw_response: dict[str, Any] | None = None
    error: str | None = None


class MessageProcessor:
    """Processor for routing messages to appropriate backend services.

    Routes messages based on their type:
        - TEXT: Sent to NLP service (Gemini)
        - VOICE/AUDIO: Transcribed via ASR, then sent to NLP
        - PHOTO: Processed via OCR (if text extraction needed)
        - Other types: Returns unsupported message
    """

    # Error messages
    ERROR_NLP_FAILED = (
        "Lo siento, hubo un error procesando tu mensaje. Por favor intenta de nuevo."
    )
    ERROR_ASR_FAILED = "No pude transcribir el audio. Por favor intenta de nuevo."
    ERROR_OCR_FAILED = "No pude procesar la imagen. Por favor intenta de nuevo."
    ERROR_DOWNLOAD_FAILED = "No pude descargar el archivo. Por favor intenta de nuevo."
    ERROR_EMPTY_TEXT = "No recibí ningún texto para procesar."
    ERROR_EMPTY_AUDIO = "No pude obtener el audio del mensaje."
    MSG_UNSUPPORTED = (
        "Este tipo de contenido no está soportado aún. Por favor envía texto o audio."
    )

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
                return ProcessingResult(
                    status=ProcessingStatus.UNSUPPORTED,
                    response=self.MSG_UNSUPPORTED,
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
        if not text:
            return ProcessingResult(
                status=ProcessingStatus.NO_CONTENT,
                response=self.ERROR_EMPTY_TEXT,
                input_type=InputType.TEXT,
            )

        return await self.process_text(text)

    async def process_text(self, text: str) -> ProcessingResult:
        """Process text via NLP service.

        Args:
            text: The text to process

        Returns:
            ProcessingResult with NLP response
        """
        try:
            result = await self._client.call_nlp_service(text)
            response = result.get("response", "")

            return ProcessingResult(
                status=ProcessingStatus.SUCCESS,
                response=response,
                input_type=InputType.TEXT,
                raw_response=result,
            )
        except Exception as e:
            logger.exception("NLP service error: %s", e)
            return ProcessingResult(
                status=ProcessingStatus.ERROR,
                response=self.ERROR_NLP_FAILED,
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

        if not file_id:
            return ProcessingResult(
                status=ProcessingStatus.NO_CONTENT,
                response=self.ERROR_EMPTY_AUDIO,
                input_type=InputType.VOICE,
            )

        try:
            # Download the audio file
            file = await bot.get_file(file_id)
            if not file.file_path:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=self.ERROR_DOWNLOAD_FAILED,
                    input_type=InputType.VOICE,
                )

            file_bytes = await bot.download_file(file.file_path)
            if not file_bytes:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=self.ERROR_DOWNLOAD_FAILED,
                    input_type=InputType.VOICE,
                )

            audio_content = file_bytes.read()

            # Transcribe via ASR
            asr_result = await self._client.call_asr_service(
                audio_content=audio_content,
                filename="voice.ogg",
                language_hint=message.from_user.language_code
                if message.from_user
                else None,
            )

            transcribed_text = asr_result.get("text", "")
            if not transcribed_text:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=self.ERROR_ASR_FAILED,
                    input_type=InputType.VOICE,
                )

            logger.info("Audio transcribed: %s", transcribed_text[:100])

            # Process transcribed text via NLP
            nlp_result = await self._client.call_nlp_service(transcribed_text)
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
            return ProcessingResult(
                status=ProcessingStatus.ERROR,
                response=self.ERROR_ASR_FAILED,
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
        if not message.photo:
            return ProcessingResult(
                status=ProcessingStatus.NO_CONTENT,
                response=self.ERROR_OCR_FAILED,
                input_type=InputType.PHOTO,
            )

        try:
            # Get the largest photo (last in the list)
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)

            if not file.file_path:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=self.ERROR_DOWNLOAD_FAILED,
                    input_type=InputType.PHOTO,
                )

            file_bytes = await bot.download_file(file.file_path)
            if not file_bytes:
                return ProcessingResult(
                    status=ProcessingStatus.ERROR,
                    response=self.ERROR_DOWNLOAD_FAILED,
                    input_type=InputType.PHOTO,
                )

            image_content = file_bytes.read()

            # Extract text via OCR
            ocr_result = await self._client.call_ocr_service(
                file_content=image_content,
                filename="photo.jpg",
                mime_type="image/jpeg",
            )

            extracted_text = ocr_result.get("text", "")
            if not extracted_text:
                # No text found in image, just acknowledge
                return ProcessingResult(
                    status=ProcessingStatus.SUCCESS,
                    response="He recibido tu imagen, pero no encontré texto para procesar.",
                    input_type=InputType.PHOTO,
                    raw_response=ocr_result,
                )

            logger.info("OCR extracted: %s", extracted_text[:100])

            # Process extracted text via NLP
            nlp_result = await self._client.call_nlp_service(
                f"Analiza el siguiente texto extraído de una imagen:\n\n{extracted_text}"
            )
            response = nlp_result.get("response", "")

            return ProcessingResult(
                status=ProcessingStatus.SUCCESS,
                response=response,
                input_type=InputType.PHOTO,
                raw_response={
                    "ocr": ocr_result,
                    "nlp": nlp_result,
                    "extracted_text": extracted_text,
                },
            )

        except Exception as e:
            logger.exception("Photo processing error: %s", e)
            return ProcessingResult(
                status=ProcessingStatus.ERROR,
                response=self.ERROR_OCR_FAILED,
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
