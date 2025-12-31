"""Internal Service Client for Cloud Run service-to-service communication.

This module provides authenticated HTTP clients for calling internal Cloud Run
services using IAM-based authentication. It automatically obtains identity
tokens from the GCP metadata server when running in Cloud Run.

Example:
    from telegram_bot.services.internal_client import InternalServiceClient

    client = InternalServiceClient()
    result = await client.call_nlp_service("Hello, how are you?")
"""

import os
from typing import Any

import google.auth.transport.requests
import httpx
from google.oauth2 import id_token

from telegram_bot.logging_config import get_logger

logger = get_logger("internal_client")


class InternalServiceClient:
    """Client for calling internal Cloud Run services with IAM authentication."""

    def __init__(
        self,
        nlp_service_url: str | None = None,
        asr_service_url: str | None = None,
        ocr_service_url: str | None = None,
        timeout: float = 60.0,
    ):
        """Initialize the internal service client.

        Args:
            nlp_service_url: URL of nlp-service (or set NLP_SERVICE_URL env)
            asr_service_url: URL of asr-service (or set ASR_SERVICE_URL env)
            ocr_service_url: URL of ocr-service (or set OCR_SERVICE_URL env)
            timeout: Request timeout in seconds
        """
        self.nlp_url = nlp_service_url or os.getenv(
            "NLP_SERVICE_URL",
            "https://nlp-service-4k3haexkga-uc.a.run.app",
        )
        self.asr_url = asr_service_url or os.getenv(
            "ASR_SERVICE_URL",
            "https://asr-service-4k3haexkga-uc.a.run.app",
        )
        self.ocr_url = ocr_service_url or os.getenv(
            "OCR_SERVICE_URL",
            "https://ocr-service-4k3haexkga-uc.a.run.app",
        )
        self.timeout = timeout
        self._is_cloud_run = os.getenv("K_SERVICE") is not None

    def _get_identity_token(self, audience: str) -> str:
        """Get an identity token for the target service.

        Args:
            audience: The URL of the target service (used as the token audience)

        Returns:
            Identity token string

        Raises:
            ValueError: If token cannot be obtained

        Note:
            In Cloud Run, tokens are obtained from the metadata server.
            Locally, tokens use GOOGLE_APPLICATION_CREDENTIALS.
        """
        request = google.auth.transport.requests.Request()
        token = id_token.fetch_id_token(request, audience)
        if token is None:
            raise ValueError(f"Failed to obtain identity token for {audience}")
        return str(token)

    def _get_auth_headers(self, service_url: str) -> dict[str, str]:
        """Get authorization headers for a service call.

        Args:
            service_url: The target service URL

        Returns:
            Headers dict with Authorization bearer token
        """
        try:
            token = self._get_identity_token(service_url)
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        except Exception as e:
            logger.warning("Failed to get identity token: %s", e)
            return {"Content-Type": "application/json"}

    async def call_nlp_service(self, text: str) -> dict[str, Any]:
        """Call the NLP service for text processing using Gemini.

        Args:
            text: Text to process (max 32000 characters)

        Returns:
            NLP processing response: {
                "response": str,
                "model": str,
                "input_length": int,
                "output_length": int
            }

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        headers = self._get_auth_headers(self.nlp_url)
        payload = {"text": text}

        logger.info("Calling NLP service with %d characters", len(text))

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.nlp_url}/api/v1/process",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                "NLP service responded with %d characters",
                result.get("output_length", 0),
            )
            return result

    async def call_asr_service(
        self,
        audio_content: bytes,
        filename: str,
        language_hint: str | None = None,
    ) -> dict[str, Any]:
        """Call the ASR service to transcribe audio.

        Args:
            audio_content: Binary content of the audio file
            filename: Name of the audio file
            language_hint: Optional language hint (e.g., 'es', 'en')

        Returns:
            Transcription response with text and metadata

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        import uuid

        token = self._get_identity_token(self.asr_url)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Request-Id": str(uuid.uuid4()),
        }

        form_data = {
            "client_id": "telegram-bot",
            "quality_preference": "balanced",
        }
        if language_hint:
            form_data["language_hint"] = language_hint

        logger.info("Calling ASR service with audio file: %s", filename)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.asr_url}/transcribe",
                headers=headers,
                files={"audio_file": (filename, audio_content, "audio/ogg")},
                data=form_data,
            )
            response.raise_for_status()
            result = response.json()
            logger.info("ASR service transcribed: %s", result.get("text", "")[:50])
            return result

    async def call_ocr_service(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Call the OCR service to extract text from an image.

        Args:
            file_content: Binary content of the image file
            filename: Name of the file
            mime_type: MIME type of the file

        Returns:
            OCR extraction response with extracted text

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        token = self._get_identity_token(self.ocr_url)
        headers = {"Authorization": f"Bearer {token}"}

        logger.info("Calling OCR service with file: %s", filename)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.ocr_url}/ocr",
                headers=headers,
                files={"file": (filename, file_content, mime_type)},
            )
            response.raise_for_status()
            result = response.json()
            logger.info("OCR service extracted text")
            return result

    async def health_check(self) -> dict[str, Any]:
        """Check health of configured services.

        Returns:
            Health status of each service
        """
        services = {
            "nlp": self.nlp_url,
            "asr": self.asr_url,
            "ocr": self.ocr_url,
        }

        results = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, url in services.items():
                if not url:
                    results[name] = {"status": "not_configured"}
                    continue
                try:
                    headers = self._get_auth_headers(url)
                    response = await client.get(
                        f"{url}/health",
                        headers=headers,
                    )
                    if response.status_code == 200:
                        results[name] = {"status": "healthy", "url": url}
                    else:
                        results[name] = {"status": "unhealthy", "url": url}
                except Exception as e:
                    results[name] = {"status": "error", "url": url, "error": str(e)}

        return results


# Singleton instance for reuse
_client: InternalServiceClient | None = None


def get_client() -> InternalServiceClient:
    """Get the singleton internal service client instance."""
    global _client
    if _client is None:
        _client = InternalServiceClient()
    return _client
