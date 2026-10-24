"""Tests for safe client-address resolution behind private reverse proxies."""

import pytest
from starlette.requests import Request

from app.client_address import client_address


def request(peer: str, forwarded: str | None = None) -> Request:
    """Build a minimal HTTP request with a socket peer and optional header."""

    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers, "client": (peer, 1234)})


def test_forwarded_header_is_ignored_for_untrusted_peer(monkeypatch):
    """A direct client cannot select another rate-limit identity."""

    monkeypatch.setenv("PATHAID_TRUSTED_PROXY_CIDRS", "172.16.0.0/12")

    assert client_address(request("203.0.113.10", "198.51.100.20")) == "203.0.113.10"


def test_forwarded_header_is_ignored_when_no_proxy_is_configured(monkeypatch):
    """The safe default trusts no proxy, including private-address peers."""

    monkeypatch.delenv("PATHAID_TRUSTED_PROXY_CIDRS", raising=False)

    assert client_address(request("172.20.0.5", "198.51.100.20")) == "172.20.0.5"


def test_first_untrusted_hop_is_used_behind_private_proxies(monkeypatch):
    """Private Caddy and frontend hops resolve to the public browser address."""

    monkeypatch.setenv("PATHAID_TRUSTED_PROXY_CIDRS", "172.16.0.0/12")

    assert client_address(request("172.20.0.5", "198.51.100.20, 172.20.0.4")) == "198.51.100.20"


@pytest.mark.parametrize("forwarded", ["not-an-ip", "198.51.100.20, unknown", "x" * 2049])
def test_malformed_forwarding_chain_falls_back_to_peer(monkeypatch, forwarded):
    """Malformed or excessive metadata cannot bypass peer-based throttling."""

    monkeypatch.setenv("PATHAID_TRUSTED_PROXY_CIDRS", "172.16.0.0/12")

    assert client_address(request("172.20.0.5", forwarded)) == "172.20.0.5"


def test_ipv6_proxy_and_client_are_supported(monkeypatch):
    """The same trust rule applies to IPv6 deployments."""

    monkeypatch.setenv("PATHAID_TRUSTED_PROXY_CIDRS", "fd00::/8")

    assert client_address(request("fd00::5", "2001:db8::20, fd00::4")) == "2001:db8::20"


def test_invalid_trusted_proxy_configuration_fails_closed(monkeypatch):
    """A malformed deployment network must be corrected explicitly."""

    monkeypatch.setenv("PATHAID_TRUSTED_PROXY_CIDRS", "private-network")

    with pytest.raises(RuntimeError, match="invalid network"):
        client_address(request("172.20.0.5", "198.51.100.20"))
