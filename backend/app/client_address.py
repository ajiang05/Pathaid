"""Resolve a rate-limit address across explicitly trusted reverse proxies."""

from __future__ import annotations

import os
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network

from fastapi import Request


def client_address(request: Request) -> str:
    """Return the first untrusted address in a validated forwarding chain.

    Forwarding headers are ignored unless the socket peer belongs to a network
    configured in ``PATHAID_TRUSTED_PROXY_CIDRS``. This keeps local/direct
    deployments safe from client-supplied X-Forwarded-For values while allowing
    a private Caddy/Next.js chain to preserve per-client authentication limits.
    """

    peer = request.client.host if request.client else "unknown"
    networks = _trusted_networks()
    peer_ip = _parse_address(peer)
    if peer_ip is None or not _is_trusted(peer_ip, networks):
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    if not forwarded or len(forwarded) > 2048:
        return peer
    values = [value.strip() for value in forwarded.split(",")]
    if not values or len(values) > 20:
        return peer
    chain = [_parse_address(value) for value in values]
    if any(value is None for value in chain):
        return peer

    # Work from the application toward the browser. Trusted proxy hops are
    # skipped; the first untrusted hop is the address that owns the request.
    for value in reversed(chain):
        if value is not None and not _is_trusted(value, networks):
            return str(value)
    return str(chain[0])


def _trusted_networks():
    """Parse the deployment's comma-separated IPv4/IPv6 proxy networks."""

    configured = os.environ.get("PATHAID_TRUSTED_PROXY_CIDRS", "").strip()
    if not configured:
        return ()
    try:
        return tuple(ip_network(value.strip(), strict=False) for value in configured.split(",") if value.strip())
    except ValueError as error:
        raise RuntimeError("PATHAID_TRUSTED_PROXY_CIDRS contains an invalid network") from error


def _parse_address(value: str) -> IPv4Address | IPv6Address | None:
    """Parse one plain address, rejecting hostnames and address-port pairs."""

    try:
        return ip_address(value)
    except ValueError:
        return None


def _is_trusted(address: IPv4Address | IPv6Address, networks) -> bool:
    """Return whether an address belongs to one configured proxy network."""

    return any(address.version == network.version and address in network for network in networks)
