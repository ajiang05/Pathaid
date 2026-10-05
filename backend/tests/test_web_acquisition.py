"""Tests for bounded, redirect-aware, IP-pinned webpage acquisition."""

import socket

import pytest

from app.source_acquisition import (
    AcquisitionConfig,
    AcquisitionError,
    HttpResponse,
    SocketHttpTransport,
    WebSourceRequest,
    _PinnedHTTPSConnection,
    acquire_web_source,
    resolve_public_addresses,
    validate_source_url,
)


PUBLIC_IP = "93.184.216.34"


class FakeTransport:
    """Return scripted responses while recording every pinned destination."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def fetch(self, url, address, *, timeout_seconds, max_response_bytes):
        self.calls.append((url.url, address, timeout_seconds, max_response_bytes))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def public_resolver(hostname, port):
    """Resolve every synthetic host to one globally routable test address."""

    return [PUBLIC_IP]


def response(status=200, *, headers=None, body=b"Program details"):
    """Build a text response for acquisition tests."""

    return HttpResponse(status, {"content-type": "text/plain; charset=utf-8"} if headers is None else headers, body)


def test_rejects_dns_answers_when_any_address_is_not_public():
    """Mixed public/private DNS cannot select the public answer as a bypass."""

    url = validate_source_url("https://example.edu/source")
    with pytest.raises(AcquisitionError) as captured:
        resolve_public_addresses(url, lambda _host, _port: [PUBLIC_IP, "127.0.0.1"], 1)
    assert captured.value.code == "unsafe_address"
    assert captured.value.retryable is False


def test_acquisition_passes_validated_ip_to_transport():
    """The connection target comes from validation rather than a second lookup."""

    transport = FakeTransport([response(body=b"  Program details  ")])
    acquired = acquire_web_source(
        WebSourceRequest("https://example.edu/source"),
        resolver=public_resolver,
        transport=transport,
    )
    assert transport.calls[0][0:2] == ("https://example.edu/source", PUBLIC_IP)
    assert acquired.normalized_text == "Program details"
    assert acquired.source_byte_count == len(b"  Program details  ")


def test_each_redirect_is_resolved_and_validated():
    """A redirect receives a new DNS validation and pinned connection."""

    resolved = []

    def resolver(hostname, port):
        resolved.append(hostname)
        return [PUBLIC_IP]

    transport = FakeTransport([
        response(302, headers={"location": "https://provider.example/final"}, body=b""),
        response(200, headers={"content-type": "text/html"}, body=b"<p>Final details</p>"),
    ])
    acquired = acquire_web_source(WebSourceRequest("https://example.edu/start"), resolver=resolver, transport=transport)
    assert resolved == ["example.edu", "provider.example"]
    assert acquired.original_url == "https://example.edu/start"
    assert acquired.final_url == "https://provider.example/final"
    assert acquired.redirect_count == 1
    assert acquired.normalized_text == "Final details"


def test_redirect_limit_and_https_downgrade_are_rejected():
    """Redirects cannot loop indefinitely or reduce transport security."""

    looping = FakeTransport([
        response(302, headers={"location": "/again"}, body=b""),
        response(302, headers={"location": "/again"}, body=b""),
    ])
    with pytest.raises(AcquisitionError) as limited:
        acquire_web_source(
            WebSourceRequest("https://example.edu/start"),
            AcquisitionConfig(max_redirects=1),
            resolver=public_resolver,
            transport=looping,
        )
    assert limited.value.code == "redirect_limit"

    downgrade = FakeTransport([response(302, headers={"location": "http://example.edu/plain"}, body=b"")])
    with pytest.raises(AcquisitionError) as downgraded:
        acquire_web_source(WebSourceRequest("https://example.edu/start"), resolver=public_resolver, transport=downgrade)
    assert downgraded.value.code == "https_downgrade"


@pytest.mark.parametrize(
    ("scripted", "expected_code", "retryable"),
    [
        (response(429), "upstream_unavailable", True),
        (response(503), "upstream_unavailable", True),
        (response(404), "upstream_rejected", False),
        (response(headers={}), "unsupported_content_type", False),
        (response(headers={"content-type": "application/pdf"}), "unsupported_content_type", False),
        (response(headers={"content-type": "text/plain", "content-encoding": "gzip"}), "unsupported_content_encoding", False),
        (response(headers={"content-type": "text/plain; charset=unknown-charset"}), "invalid_text_encoding", False),
    ],
)
def test_classifies_provider_and_content_failures(scripted, expected_code, retryable):
    """Workflow errors distinguish retryable provider failures from bad input."""

    with pytest.raises(AcquisitionError) as captured:
        acquire_web_source(WebSourceRequest("https://example.edu/source"), resolver=public_resolver, transport=FakeTransport([scripted]))
    assert captured.value.code == expected_code
    assert captured.value.retryable is retryable


def test_enforces_body_limit_even_for_custom_transport():
    """The acquisition layer distrusts transports that return oversized bodies."""

    with pytest.raises(AcquisitionError) as captured:
        acquire_web_source(
            WebSourceRequest("https://example.edu/source"),
            AcquisitionConfig(max_response_bytes=4),
            resolver=public_resolver,
            transport=FakeTransport([response(body=b"12345")]),
        )
    assert captured.value.code == "response_too_large"


def test_retries_a_second_validated_address_after_network_failure():
    """A transient failure may try another public address within the deadline."""

    failure = AcquisitionError("network_failure", "The source could not be retrieved.", retryable=True)
    transport = FakeTransport([failure, response()])
    acquired = acquire_web_source(
        WebSourceRequest("https://example.edu/source"),
        resolver=lambda _host, _port: [PUBLIC_IP, "93.184.216.35"],
        transport=transport,
    )
    assert acquired.normalized_text == "Program details"
    assert [call[1] for call in transport.calls] == [PUBLIC_IP, "93.184.216.35"]


def test_http_transport_uses_pinned_ip_and_original_host_header(monkeypatch):
    """Plain HTTP connects to the validated IP while routing for the hostname."""

    observed = {}

    class FakeResponse:
        status = 200

        def getheaders(self):
            return [("Content-Type", "text/plain")]

        def read(self, amount):
            observed["read_amount"] = amount
            return b"Details"

    class FakeConnection:
        def __init__(self, host, port, timeout):
            observed.update(host=host, port=port, timeout=timeout)

        def request(self, method, target, headers):
            observed.update(method=method, target=target, headers=headers)

        def getresponse(self):
            return FakeResponse()

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr("app.source_acquisition.http.client.HTTPConnection", FakeConnection)
    result = SocketHttpTransport().fetch(
        validate_source_url("http://example.edu/details"),
        PUBLIC_IP,
        timeout_seconds=2,
        max_response_bytes=100,
    )
    assert observed["host"] == PUBLIC_IP
    assert observed["headers"]["Host"] == "example.edu"
    assert observed["target"] == "/details"
    assert observed["read_amount"] == 101
    assert observed["closed"] is True
    assert result.body == b"Details"


def test_https_connection_pins_tcp_but_uses_hostname_for_tls(monkeypatch):
    """TLS verification keeps the hostname even though TCP uses the safe IP."""

    observed = {}
    raw_socket = object()
    wrapped_socket = object()

    def create_connection(destination, timeout, source_address):
        observed.update(destination=destination, timeout=timeout, source_address=source_address)
        return raw_socket

    class FakeContext:
        def wrap_socket(self, sock, server_hostname):
            observed.update(sock=sock, server_hostname=server_hostname)
            return wrapped_socket

    monkeypatch.setattr(socket, "create_connection", create_connection)
    connection = _PinnedHTTPSConnection("example.edu", PUBLIC_IP, 443, 2)
    connection._context = FakeContext()
    connection.connect()
    assert observed["destination"] == (PUBLIC_IP, 443)
    assert observed["server_hostname"] == "example.edu"
    assert connection.sock is wrapped_socket
