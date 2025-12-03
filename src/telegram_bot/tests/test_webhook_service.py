"""Tests for webhook_service module.

Tests cover:
- IP address validation against Telegram's official ranges
- Client IP extraction from various headers
- Request validation with IP filtering
- IPv6 support
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from telegram_bot.services.webhook_service import (
    TELEGRAM_IP_RANGES,
    TELEGRAM_IP_RANGES_V4,
    TELEGRAM_IP_RANGES_V6,
    get_client_ip,
    is_telegram_ip,
    validate_telegram_request,
)


class TestTelegramIPRanges:
    """Tests for TELEGRAM_IP_RANGES constants."""

    def test_ip_ranges_v4_defined(self) -> None:
        """Verify that Telegram IPv4 ranges are defined."""
        assert len(TELEGRAM_IP_RANGES_V4) == 2

    def test_ip_ranges_v6_defined(self) -> None:
        """Verify that Telegram IPv6 ranges are defined."""
        assert len(TELEGRAM_IP_RANGES_V6) == 3

    def test_ip_ranges_backward_compatible(self) -> None:
        """Verify backward compatibility constant."""
        assert TELEGRAM_IP_RANGES == TELEGRAM_IP_RANGES_V4

    def test_ip_ranges_correct_networks(self) -> None:
        """Verify the correct IP networks are defined."""
        networks_v4 = [str(net) for net in TELEGRAM_IP_RANGES_V4]
        assert "149.154.160.0/20" in networks_v4
        assert "91.108.4.0/22" in networks_v4

        networks_v6 = [str(net) for net in TELEGRAM_IP_RANGES_V6]
        assert "2001:67c:4e8::/48" in networks_v6
        assert "2001:b28:f23d::/48" in networks_v6
        assert "2001:b28:f23f::/48" in networks_v6


class TestIsTelegramIP:
    """Tests for is_telegram_ip function."""

    # Valid Telegram IPs from 149.154.160.0/20 range
    @pytest.mark.parametrize(
        "ip",
        [
            "149.154.160.0",  # Network start
            "149.154.160.1",
            "149.154.167.128",
            "149.154.175.255",  # Network end
        ],
    )
    def test_valid_telegram_ip_range_1(self, ip: str) -> None:
        """Test IPs in the 149.154.160.0/20 range."""
        assert is_telegram_ip(ip) is True

    # Valid Telegram IPs from 91.108.4.0/22 range
    @pytest.mark.parametrize(
        "ip",
        [
            "91.108.4.0",  # Network start
            "91.108.4.1",
            "91.108.5.128",
            "91.108.7.255",  # Network end
        ],
    )
    def test_valid_telegram_ip_range_2(self, ip: str) -> None:
        """Test IPs in the 91.108.4.0/22 range."""
        assert is_telegram_ip(ip) is True

    # Invalid IPs (not in Telegram ranges)
    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "192.168.1.1",  # Private network
            "10.0.0.1",  # Private network
            "172.16.0.1",  # Private network
            "127.0.0.1",  # Localhost
            "149.154.159.255",  # Just before Telegram range
            "149.154.176.0",  # Just after Telegram range
            "91.108.3.255",  # Just before Telegram range
            "91.108.8.0",  # Just after Telegram range
        ],
    )
    def test_invalid_telegram_ip(self, ip: str) -> None:
        """Test IPs not in Telegram's ranges."""
        assert is_telegram_ip(ip) is False

    # Valid Telegram IPv6 addresses
    @pytest.mark.parametrize(
        "ip",
        [
            "2001:67c:4e8::1",  # From first IPv6 range
            "2001:b28:f23d::1",  # From second IPv6 range
            "2001:b28:f23f::1",  # From third IPv6 range
        ],
    )
    def test_valid_telegram_ipv6(self, ip: str) -> None:
        """Test valid Telegram IPv6 addresses."""
        assert is_telegram_ip(ip) is True

    # Invalid IPv6 addresses (not in Telegram ranges)
    @pytest.mark.parametrize(
        "ip",
        [
            "::1",  # IPv6 localhost
            "2001:db8::1",  # Documentation range
            "fe80::1",  # Link-local
            "2606:4700:4700::1111",  # Cloudflare DNS
        ],
    )
    def test_invalid_telegram_ipv6(self, ip: str) -> None:
        """Test invalid IPv6 addresses not in Telegram's ranges."""
        assert is_telegram_ip(ip) is False

    # Invalid IP formats and edge cases
    @pytest.mark.parametrize(
        "ip",
        [
            "invalid",
            "256.256.256.256",
            "1.2.3.4.5",
            "",
            "unknown",  # Special case - unknown IP should be blocked
        ],
    )
    def test_invalid_ip_format(self, ip: str) -> None:
        """Test invalid IP address formats."""
        assert is_telegram_ip(ip) is False

    def test_unknown_ip_returns_false(self) -> None:
        """Test that 'unknown' IP string returns False."""
        assert is_telegram_ip("unknown") is False

    def test_empty_ip_returns_false(self) -> None:
        """Test that empty IP string returns False."""
        assert is_telegram_ip("") is False

    def test_none_like_values_return_false(self) -> None:
        """Test that None-like values return False."""
        # These would normally cause issues without proper handling
        assert is_telegram_ip("") is False
        assert is_telegram_ip("unknown") is False


class TestGetClientIP:
    """Tests for get_client_ip function."""

    def _create_mock_request(
        self,
        x_forwarded_for: str | None = None,
        x_real_ip: str | None = None,
        client_host: str | None = None,
    ) -> MagicMock:
        """Create a mock FastAPI Request object."""
        request = MagicMock()
        headers = {}
        if x_forwarded_for:
            headers["X-Forwarded-For"] = x_forwarded_for
        if x_real_ip:
            headers["X-Real-IP"] = x_real_ip
        request.headers = headers

        if client_host:
            request.client = MagicMock()
            request.client.host = client_host
        else:
            request.client = None

        return request

    def test_x_forwarded_for_single_ip(self) -> None:
        """Test extraction from X-Forwarded-For with single IP."""
        request = self._create_mock_request(x_forwarded_for="149.154.160.1")
        assert get_client_ip(request) == "149.154.160.1"

    def test_x_forwarded_for_multiple_ips(self) -> None:
        """Test extraction from X-Forwarded-For with multiple IPs."""
        request = self._create_mock_request(
            x_forwarded_for="149.154.160.1, 10.0.0.1, 192.168.1.1"
        )
        assert get_client_ip(request) == "149.154.160.1"

    def test_x_forwarded_for_with_spaces(self) -> None:
        """Test extraction handles extra whitespace."""
        request = self._create_mock_request(x_forwarded_for="  149.154.160.1  ")
        assert get_client_ip(request) == "149.154.160.1"

    def test_x_real_ip(self) -> None:
        """Test extraction from X-Real-IP header."""
        request = self._create_mock_request(x_real_ip="91.108.4.1")
        assert get_client_ip(request) == "91.108.4.1"

    def test_x_real_ip_with_spaces(self) -> None:
        """Test extraction from X-Real-IP handles whitespace."""
        request = self._create_mock_request(x_real_ip="  91.108.4.1  ")
        assert get_client_ip(request) == "91.108.4.1"

    def test_x_forwarded_for_takes_priority(self) -> None:
        """Test that X-Forwarded-For takes priority over X-Real-IP."""
        request = self._create_mock_request(
            x_forwarded_for="149.154.160.1",
            x_real_ip="91.108.4.1",
            client_host="8.8.8.8",
        )
        assert get_client_ip(request) == "149.154.160.1"

    def test_x_real_ip_fallback(self) -> None:
        """Test fallback to X-Real-IP when X-Forwarded-For is absent."""
        request = self._create_mock_request(
            x_real_ip="91.108.4.1",
            client_host="8.8.8.8",
        )
        assert get_client_ip(request) == "91.108.4.1"

    def test_client_host_fallback(self) -> None:
        """Test fallback to client.host when headers are absent."""
        request = self._create_mock_request(client_host="149.154.160.1")
        assert get_client_ip(request) == "149.154.160.1"

    def test_no_ip_available(self) -> None:
        """Test when no IP information is available."""
        request = self._create_mock_request()
        assert get_client_ip(request) == "unknown"


class TestValidateTelegramRequest:
    """Tests for validate_telegram_request function."""

    def _create_mock_request(self, client_host: str) -> MagicMock:
        """Create a mock FastAPI Request with direct client IP."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = client_host
        return request

    @pytest.mark.asyncio
    async def test_filter_disabled_allows_any_ip(self) -> None:
        """Test that disabled filter allows any IP."""
        request = self._create_mock_request("8.8.8.8")
        # Should not raise
        await validate_telegram_request(request, ip_filter_enabled=False)

    @pytest.mark.asyncio
    async def test_filter_enabled_allows_telegram_ip(self) -> None:
        """Test that enabled filter allows Telegram IPs."""
        request = self._create_mock_request("149.154.160.1")
        # Should not raise
        await validate_telegram_request(request, ip_filter_enabled=True)

    @pytest.mark.asyncio
    async def test_filter_enabled_allows_telegram_ip_range_2(self) -> None:
        """Test that enabled filter allows IPs from second range."""
        request = self._create_mock_request("91.108.4.1")
        # Should not raise
        await validate_telegram_request(request, ip_filter_enabled=True)

    @pytest.mark.asyncio
    async def test_filter_enabled_blocks_non_telegram_ip(self) -> None:
        """Test that enabled filter blocks non-Telegram IPs."""
        request = self._create_mock_request("8.8.8.8")
        with pytest.raises(HTTPException) as exc_info:
            await validate_telegram_request(request, ip_filter_enabled=True)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Access denied"

    @pytest.mark.asyncio
    async def test_filter_enabled_blocks_private_ip(self) -> None:
        """Test that enabled filter blocks private IPs."""
        request = self._create_mock_request("192.168.1.1")
        with pytest.raises(HTTPException) as exc_info:
            await validate_telegram_request(request, ip_filter_enabled=True)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_filter_enabled_blocks_localhost(self) -> None:
        """Test that enabled filter blocks localhost."""
        request = self._create_mock_request("127.0.0.1")
        with pytest.raises(HTTPException) as exc_info:
            await validate_telegram_request(request, ip_filter_enabled=True)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_filter_with_x_forwarded_for(self) -> None:
        """Test that filter uses X-Forwarded-For header."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "149.154.160.1, 10.0.0.1"}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"  # Proxy IP
        # Should not raise - uses first IP from X-Forwarded-For
        await validate_telegram_request(request, ip_filter_enabled=True)

    @pytest.mark.asyncio
    async def test_filter_blocks_spoofed_x_forwarded_for(self) -> None:
        """Test that filter blocks if first IP in X-Forwarded-For is invalid."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "8.8.8.8, 149.154.160.1"}
        request.client = MagicMock()
        request.client.host = "149.154.160.1"
        with pytest.raises(HTTPException) as exc_info:
            await validate_telegram_request(request, ip_filter_enabled=True)
        assert exc_info.value.status_code == 403
