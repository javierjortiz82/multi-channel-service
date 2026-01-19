"""Internal Service Client for Cloud Run service-to-service communication.

This module provides authenticated HTTP clients for calling internal Cloud Run
services using IAM-based authentication with connection pooling and pre-warming.

Features:
    - Persistent HTTP client with connection pooling
    - Async token fetching (non-blocking)
    - Token caching with auto-refresh
    - Connection pre-warming at startup
    - Automatic retry on transient failures

Example:
    from telegram_bot.services.internal_client import get_client, warmup_client

    # At startup
    await warmup_client()

    # For requests
    client = get_client()
    result = await client.call_nlp_service("Hello")
"""

import asyncio
import contextlib
import os
import random
import time
from typing import Any

import httpx

from telegram_bot.logging_config import get_logger

logger = get_logger("internal_client")

# Token cache TTL (50 minutes, tokens valid for 1 hour)
TOKEN_CACHE_TTL = 50 * 60

# HTTP client settings for optimal performance
HTTP_TIMEOUT = httpx.Timeout(
    connect=10.0,  # Connection timeout
    read=60.0,  # Read timeout
    write=10.0,  # Write timeout
    pool=5.0,  # Pool timeout
)
HTTP_LIMITS = httpx.Limits(
    max_keepalive_connections=10,
    max_connections=20,
    keepalive_expiry=300.0,  # 5 minutes
)

# Retry configuration (based on Context7 best practices)
# HTTPTransport handles ConnectError/ConnectTimeout
# Manual retry handles WriteError, NetworkError, and 5xx errors
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 10.0  # seconds
RETRY_JITTER = 0.5  # random jitter factor

# Retryable exceptions (WriteError, NetworkError, and base classes)
RETRYABLE_EXCEPTIONS = (
    httpx.WriteError,
    httpx.ReadError,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


class InternalServiceClient:
    """Client for calling internal Cloud Run services with IAM authentication.

    Uses persistent HTTP connections and token caching for optimal performance.
    """

    def __init__(
        self,
        nlp_service_url: str | None = None,
        asr_service_url: str | None = None,
        ocr_service_url: str | None = None,
        mcp_service_url: str | None = None,
    ):
        """Initialize the internal service client.

        Args:
            nlp_service_url: URL of nlp-service (or set NLP_SERVICE_URL env)
            asr_service_url: URL of asr-service (or set ASR_SERVICE_URL env)
            ocr_service_url: URL of ocr-service (or set OCR_SERVICE_URL env)
            mcp_service_url: URL of mcp-server (or set MCP_SERVICE_URL env)
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
        self.mcp_url = mcp_service_url or os.getenv(
            "MCP_SERVICE_URL",
            "https://mcp-server-4k3haexkga-uc.a.run.app",
        )

        # Token cache: {audience: (token, expiry_time)}
        self._token_cache: dict[str, tuple[str, float]] = {}
        self._token_lock = asyncio.Lock()

        # Persistent HTTP client (created lazily)
        self._http_client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the persistent HTTP client.

        Uses HTTPTransport with retries for connection errors (Context7 best practice).
        """
        if self._http_client is None or self._http_client.is_closed:
            async with self._client_lock:
                if self._http_client is None or self._http_client.is_closed:
                    # HTTPTransport with retries handles ConnectError/ConnectTimeout
                    transport = httpx.AsyncHTTPTransport(
                        retries=2,  # Retry connection errors twice
                        http2=True,  # HTTP/2 for better multiplexing
                    )
                    self._http_client = httpx.AsyncClient(
                        transport=transport,
                        timeout=HTTP_TIMEOUT,
                        limits=HTTP_LIMITS,
                    )
        return self._http_client

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        max_retries: int = MAX_RETRIES,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute HTTP request with retry logic for transient errors.

        Implements exponential backoff with jitter for WriteError, NetworkError,
        and 5xx server errors (Context7 best practice for resilient HTTP clients).

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Request headers
            max_retries: Maximum number of retry attempts
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: If request fails after all retries
            httpx.RequestError: If network error persists after all retries
        """
        client = await self._get_http_client()
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                response = await client.request(method, url, headers=headers, **kwargs)

                # Retry on 5xx server errors (except 501 Not Implemented)
                is_retryable_5xx = (
                    response.status_code >= 500
                    and response.status_code != 501
                    and attempt < max_retries
                )
                if is_retryable_5xx:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        "Server error %d, retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue

                return response

            except RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                if attempt < max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        "%s error, retrying in %.1fs (attempt %d/%d): %s",
                        type(e).__name__,
                        delay,
                        attempt + 1,
                        max_retries,
                        str(e)[:100],
                    )
                    await asyncio.sleep(delay)
                    # Reset HTTP client on network errors to get fresh connection
                    await self._reset_http_client()
                else:
                    logger.error(
                        "%s error after %d retries: %s",
                        type(e).__name__,
                        max_retries,
                        str(e),
                    )
                    raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state in retry loop")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base * 2^attempt
        delay: float = RETRY_BASE_DELAY * (2**attempt)
        # Add random jitter
        jitter: float = delay * RETRY_JITTER * random.random()
        delay = delay + jitter
        # Cap at max delay
        return float(min(delay, RETRY_MAX_DELAY))

    async def _reset_http_client(self) -> None:
        """Reset HTTP client to get fresh connections after network errors."""
        async with self._client_lock:
            if self._http_client is not None:
                with contextlib.suppress(Exception):
                    await self._http_client.aclose()
                self._http_client = None

    def _fetch_token_sync(self, audience: str) -> str:
        """Synchronously fetch identity token (runs in thread pool).

        Uses the GCP metadata server in Cloud Run, or ADC locally.
        """
        import google.auth.transport.requests
        from google.oauth2 import id_token

        request = google.auth.transport.requests.Request()
        token = id_token.fetch_id_token(request, audience)
        if token is None:
            raise ValueError(f"Failed to obtain identity token for {audience}")
        return str(token)

    async def _get_identity_token(self, audience: str) -> str:
        """Get an identity token asynchronously with caching.

        Args:
            audience: The URL of the target service

        Returns:
            Identity token string
        """
        # Check cache first (without lock for performance)
        if audience in self._token_cache:
            token, expiry = self._token_cache[audience]
            if time.time() < expiry:
                return token

        # Fetch new token with lock to prevent thundering herd
        async with self._token_lock:
            # Double-check after acquiring lock
            if audience in self._token_cache:
                token, expiry = self._token_cache[audience]
                if time.time() < expiry:
                    return token

            logger.info("Fetching new identity token for %s", audience)
            start = time.perf_counter()
            token = await asyncio.to_thread(self._fetch_token_sync, audience)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info("Token fetched in %.0fms", elapsed)

            # Cache the token
            self._token_cache[audience] = (token, time.time() + TOKEN_CACHE_TTL)
            return token

    async def warmup(self) -> None:
        """Pre-warm tokens and connections for all services.

        Call this at application startup to eliminate cold-start latency.
        """
        logger.info("Warming up internal service client...")
        start = time.perf_counter()

        # Pre-fetch tokens for all services in parallel
        services = [
            ("nlp", self.nlp_url),
            ("asr", self.asr_url),
            ("ocr", self.ocr_url),
            ("mcp", self.mcp_url),
        ]

        async def warmup_service(name: str, url: str) -> None:
            if not url:
                return
            try:
                # Get token
                token = await self._get_identity_token(url)

                # Warm up connection with health check
                client = await self._get_http_client()
                headers = {"Authorization": f"Bearer {token}"}

                # Use /health endpoint if available, otherwise just connect
                health_url = f"{url}/health"
                if "nlp" in name:
                    health_url = f"{url}/api/v1/health"

                response = await client.get(health_url, headers=headers)
                logger.info(
                    "Warmed up %s: status=%d",
                    name,
                    response.status_code,
                )
            except Exception as e:
                logger.warning("Failed to warmup %s: %s", name, e)

        await asyncio.gather(*[warmup_service(n, u) for n, u in services])

        elapsed = (time.perf_counter() - start) * 1000
        logger.info("Client warmup completed in %.0fms", elapsed)

    async def call_nlp_service(
        self,
        text: str,
        conversation_id: str | None = None,
        user_info: dict[str, Any] | None = None,
        detected_language: str | None = None,
    ) -> dict[str, Any]:
        """Call the NLP service for text processing using Gemini.

        Args:
            text: Text to process (max 32000 characters)
            conversation_id: Optional conversation ID for context continuity.
                Typically the Telegram chat_id.
            user_info: Optional user information for tracking. Should contain:
                - channel: 'telegram' or 'instagram'
                - external_id: User's ID in the channel
                - first_name: User's first name
                - last_name: User's last name (optional)
                - username: User's handle (optional)
                - language_code: User's language (optional)
            detected_language: Optional language detected from ASR.
                Takes priority over user_info.language_code.

        Returns:
            NLP processing response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        token = await self._get_identity_token(self.nlp_url)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"text": text}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if user_info:
            payload["user"] = user_info
        if detected_language:
            payload["detected_language"] = detected_language

        logger.info(
            "Calling NLP service with %d characters, conversation_id=%s, has_user=%s, detected_lang=%s",
            len(text),
            conversation_id,
            user_info is not None,
            detected_language,
        )
        start = time.perf_counter()

        response = await self._request_with_retry(
            "POST",
            f"{self.nlp_url}/api/v1/process",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "NLP service responded with %d chars in %.0fms",
            result.get("output_length", 0),
            elapsed,
        )
        return result

    async def call_asr_service(
        self,
        audio_content: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """Call the ASR service to transcribe audio.

        Args:
            audio_content: Binary content of the audio file
            filename: Name of the audio file

        Returns:
            Transcription response with text and metadata

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        import uuid

        token = await self._get_identity_token(self.asr_url)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Request-Id": str(uuid.uuid4()),
        }

        form_data = {
            "client_id": "telegram-bot",
            "quality_preference": "balanced",
        }

        logger.info("Calling ASR service with audio file: %s", filename)

        response = await self._request_with_retry(
            "POST",
            f"{self.asr_url}/transcribe",
            headers=headers,
            files={"audio_file": (filename, audio_content, "audio/ogg")},
            data=form_data,
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        transcription = result.get("data", {}).get("transcription", "")
        logger.info(
            "ASR service transcribed: %s", transcription[:50] if transcription else ""
        )
        return result

    async def call_analyze_service(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        client_id: str = "telegram-bot",
    ) -> dict[str, Any]:
        """Call the analyze service to auto-classify and process an image.

        The analyze endpoint automatically classifies the image and routes it
        to the appropriate service:
        - Documents → OCR for text extraction
        - Objects → Detection for object identification

        Args:
            file_content: Binary content of the image file
            filename: Name of the file
            mime_type: MIME type of the file
            client_id: Client identifier for tracking

        Returns:
            Analysis response with:
            - result: Extracted text or detected object
            - classification: {predicted_type, confidence}
            - ocr_result or detection_result depending on type

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        token = await self._get_identity_token(self.ocr_url)
        headers = {"Authorization": f"Bearer {token}"}

        logger.info("Calling analyze service with file: %s", filename)

        response = await self._request_with_retry(
            "POST",
            f"{self.ocr_url}/analyze/upload",
            headers=headers,
            files={"file": (filename, file_content, mime_type)},
            data={"client_id": client_id, "mode": "auto"},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()

        # Log classification result
        classification = result.get("classification", {})
        predicted_type = classification.get("predicted_type", "unknown")
        confidence = classification.get("confidence", 0)
        logger.info(
            "Analyze service classified as %s (confidence=%.2f)",
            predicted_type,
            confidence,
        )
        return result

    async def search_products_by_embedding(
        self,
        embedding: list[float],
        limit: int = 5,
        max_distance: float = 0.5,
    ) -> dict[str, Any]:
        """Search products by image embedding similarity (Google Lens style).

        Calls the MCP server's image search endpoint to find products
        with similar embeddings.

        Args:
            embedding: 1536-dimensional vector from image embedding.
            limit: Maximum number of results (default: 5, max: 20).
            max_distance: Maximum L2 distance for matches (default: 0.5).

        Returns:
            Search results with format:
            {
                "found": bool,
                "count": int,
                "products": [
                    {
                        "sku": str,
                        "name": str,
                        "description": str,
                        "category": str,
                        "brand": str,
                        "price": float,
                        "image_url": str | None,
                        "similarity": float
                    },
                    ...
                ]
            }

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        token = await self._get_identity_token(self.mcp_url)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "embedding": embedding,
            "limit": limit,
            "max_distance": max_distance,
        }

        logger.info(
            "Searching products by embedding (limit=%d, max_distance=%.2f)",
            limit,
            max_distance,
        )
        start = time.perf_counter()

        response = await self._request_with_retry(
            "POST",
            f"{self.mcp_url}/api/v1/image-search",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()

        elapsed = (time.perf_counter() - start) * 1000
        found = result.get("found", False)
        count = result.get("count", 0)
        logger.info(
            "Image search completed: found=%s, count=%d in %.0fms",
            found,
            count,
            elapsed,
        )

        return result

    async def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None


# Singleton instance for reuse
_client: InternalServiceClient | None = None


def get_client() -> InternalServiceClient:
    """Get the singleton internal service client instance."""
    global _client
    if _client is None:
        _client = InternalServiceClient()
    return _client


async def warmup_client() -> None:
    """Warmup the singleton client. Call at application startup."""
    client = get_client()
    await client.warmup()
