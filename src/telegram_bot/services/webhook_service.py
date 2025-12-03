"""Webhook service with IP filtering and security features.

This module provides secure webhook handling for Telegram Bot API,
including IP filtering based on Telegram's official server ranges.

Reference:
- https://core.telegram.org/bots/webhooks
- IP ranges: 149.154.160.0/20, 91.108.4.0/22

Security Note:
- X-Forwarded-For and X-Real-IP headers can be spoofed by clients
- Only trust these headers when behind a properly configured reverse proxy
- The proxy should overwrite (not append to) X-Forwarded-For
"""

import ipaddress
from typing import Final

from fastapi import HTTPException, Request, status

from telegram_bot.logging_config import get_logger

logger = get_logger("webhook_service")

# Telegram Bot API server IP ranges (official)
# https://core.telegram.org/bots/webhooks#the-short-version
TELEGRAM_IP_RANGES_V4: Final[tuple[ipaddress.IPv4Network, ...]] = (
    ipaddress.IPv4Network("149.154.160.0/20"),
    ipaddress.IPv4Network("91.108.4.0/22"),
)

# IPv6 ranges for Telegram (currently Telegram uses IPv4, but future-proofing)
# Reference: https://core.telegram.org/bots/webhooks
TELEGRAM_IP_RANGES_V6: Final[tuple[ipaddress.IPv6Network, ...]] = (
    ipaddress.IPv6Network("2001:67c:4e8::/48"),
    ipaddress.IPv6Network("2001:b28:f23d::/48"),
    ipaddress.IPv6Network("2001:b28:f23f::/48"),
)

# Combined for backward compatibility
TELEGRAM_IP_RANGES = TELEGRAM_IP_RANGES_V4


def is_telegram_ip(ip_address: str) -> bool:
    """Check if an IP address belongs to Telegram's server ranges.

    Supports both IPv4 and IPv6 addresses.

    Args:
        ip_address: The IP address to check.

    Returns:
        True if the IP belongs to Telegram's ranges, False otherwise.
    """
    if not ip_address or ip_address == "unknown":
        logger.warning("Empty or unknown IP address received")
        return False

    try:
        # Try IPv4 first (most common case)
        ip = ipaddress.IPv4Address(ip_address)
        return any(ip in network for network in TELEGRAM_IP_RANGES_V4)
    except ipaddress.AddressValueError:
        pass

    try:
        # Try IPv6
        ip_v6 = ipaddress.IPv6Address(ip_address)
        return any(ip_v6 in network for network in TELEGRAM_IP_RANGES_V6)
    except ipaddress.AddressValueError:
        logger.warning("Invalid IP address format: %s", ip_address)
        return False


def get_client_ip(request: Request) -> str:
    """Extract the real client IP from the request.

    Handles cases where the app is behind a reverse proxy (nginx, etc.)
    by checking X-Forwarded-For and X-Real-IP headers.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The client's IP address.
    """
    # Check for proxy headers first
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The first one is the original client
        return x_forwarded_for.split(",")[0].strip()

    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip.strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


async def validate_telegram_request(request: Request, ip_filter_enabled: bool) -> None:
    """Validate that the request comes from Telegram servers.

    Args:
        request: The incoming FastAPI request.
        ip_filter_enabled: Whether IP filtering is enabled.

    Raises:
        HTTPException: If the IP is not from Telegram (when filtering enabled).
    """
    if not ip_filter_enabled:
        return

    client_ip = get_client_ip(request)

    if not is_telegram_ip(client_ip):
        logger.warning(
            "Blocked webhook request from non-Telegram IP: %s",
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    logger.debug("Webhook request from Telegram IP: %s", client_ip)
