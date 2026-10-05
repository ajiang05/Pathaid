"""Safe, bounded acquisition of administrator-supplied program sources.

This module treats every URL and source body as untrusted input. The public
entry points return normalized text and provenance for later persistence; they
never interpret webpage text as instructions or grant it application authority.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from email.message import Message
from html.parser import HTMLParser
from typing import Callable, Iterable, Literal, Mapping, Protocol
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit


@dataclass(frozen=True)
class AcquisitionConfig:
    """Limits applied to pasted text and future network acquisition."""

    max_redirects: int = 5
    timeout_seconds: float = 10.0
    max_response_bytes: int = 2_000_000
    max_text_characters: int = 500_000


@dataclass(frozen=True)
class ValidatedUrl:
    """A normalized public HTTP(S) URL and its connection components."""

    url: str
    scheme: Literal["http", "https"]
    hostname: str
    port: int
    request_target: str


@dataclass(frozen=True)
class WebSourceRequest:
    """Request to retrieve and normalize one public webpage."""

    source_url: str


@dataclass(frozen=True)
class PastedSourceRequest:
    """Administrator-supplied text accompanied by its claimed source URL."""

    source_url: str
    source_text: str


@dataclass(frozen=True)
class AcquiredSource:
    """Validated content and provenance ready to become a source snapshot."""

    original_url: str
    final_url: str
    acquisition_method: Literal["webpage", "pasted_text"]
    media_type: str
    normalized_text: str
    content_hash: str
    source_byte_count: int
    redirect_count: int


@dataclass(frozen=True)
class HttpResponse:
    """One bounded HTTP response returned by an injectable single-hop transport."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class SingleHopTransport(Protocol):
    """Transport contract that connects to one already-validated IP address."""

    def fetch(
        self,
        url: ValidatedUrl,
        address: str,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse: ...


Resolver = Callable[[str, int], Iterable[str]]


class AcquisitionError(Exception):
    """A safe workflow error that never includes a source body or secret URL."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable

    def as_dict(self) -> dict[str, str | bool]:
        """Return the stable fields an ingestion run may persist or display."""

        return {
            "code": self.code,
            "message": self.safe_message,
            "retryable": self.retryable,
        }


def validate_source_url(source_url: str) -> ValidatedUrl:
    """Validate and normalize a source URL without performing DNS resolution."""

    if not isinstance(source_url, str) or not source_url.strip():
        raise AcquisitionError("invalid_url", "A source URL is required.")
    try:
        parsed = urlsplit(source_url.strip())
        port = parsed.port
    except ValueError as error:
        raise AcquisitionError("invalid_url", "The source URL is malformed.") from error

    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"}:
        raise AcquisitionError("invalid_url", "Only HTTP and HTTPS source URLs are supported.")
    if parsed.username is not None or parsed.password is not None:
        raise AcquisitionError("invalid_url", "Source URLs cannot contain credentials.")
    if parsed.fragment:
        raise AcquisitionError("invalid_url", "Source URLs cannot contain fragments.")
    if parsed.hostname is None:
        raise AcquisitionError("invalid_url", "The source URL must contain a hostname.")

    hostname = _normalize_hostname(parsed.hostname)
    default_port = 443 if scheme == "https" else 80
    if port is not None and port != default_port:
        raise AcquisitionError("unsafe_port", "Source URLs must use the standard HTTP or HTTPS port.")
    _reject_literal_or_local_hostname(hostname)

    path = parsed.path or "/"
    request_target = path + (f"?{parsed.query}" if parsed.query else "")
    display_host = f"[{hostname}]" if ":" in hostname else hostname
    normalized = urlunsplit(SplitResult(scheme, display_host, path, parsed.query, ""))
    return ValidatedUrl(normalized, scheme, hostname, default_port, request_target)


def prepare_pasted_source(
    request: PastedSourceRequest,
    config: AcquisitionConfig = AcquisitionConfig(),
) -> AcquiredSource:
    """Validate, normalize, and hash pasted administrator-supplied text."""

    validated_url = validate_source_url(request.source_url)
    if not isinstance(request.source_text, str):
        raise AcquisitionError("invalid_text", "Pasted source text must be a string.")
    encoded = request.source_text.encode("utf-8")
    if len(encoded) > config.max_response_bytes:
        raise AcquisitionError("response_too_large", "The supplied source exceeds the configured size limit.")
    normalized = normalize_text(request.source_text, config.max_text_characters)
    return AcquiredSource(
        original_url=validated_url.url,
        final_url=validated_url.url,
        acquisition_method="pasted_text",
        media_type="text/plain",
        normalized_text=normalized,
        content_hash=hash_text(normalized),
        source_byte_count=len(encoded),
        redirect_count=0,
    )


def acquire_web_source(
    request: WebSourceRequest,
    config: AcquisitionConfig = AcquisitionConfig(),
    *,
    resolver: Resolver | None = None,
    transport: SingleHopTransport | None = None,
) -> AcquiredSource:
    """Retrieve one public text page through validated, IP-pinned hops."""

    original = validate_source_url(request.source_url)
    current = original
    redirect_count = 0
    deadline = time.monotonic() + config.timeout_seconds
    resolver = resolver or system_resolver
    transport = transport or SocketHttpTransport()

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AcquisitionError("timeout", "Source acquisition timed out.", retryable=True)
        addresses = resolve_public_addresses(current, resolver, remaining)
        response = _fetch_from_addresses(current, addresses, transport, deadline, config.max_response_bytes)

        if response.status in {301, 302, 303, 307, 308}:
            if redirect_count >= config.max_redirects:
                raise AcquisitionError("redirect_limit", "The source exceeded the redirect limit.")
            location = response.headers.get("location")
            if not location:
                raise AcquisitionError("invalid_redirect", "The source returned a redirect without a destination.")
            destination = validate_source_url(urljoin(current.url, location))
            if current.scheme == "https" and destination.scheme == "http":
                raise AcquisitionError("https_downgrade", "HTTPS sources cannot redirect to HTTP.")
            current = destination
            redirect_count += 1
            continue

        if response.status == 429 or 500 <= response.status <= 599:
            raise AcquisitionError("upstream_unavailable", "The source provider is temporarily unavailable.", retryable=True)
        if not 200 <= response.status <= 299:
            raise AcquisitionError("upstream_rejected", "The source provider did not return a successful response.")
        if len(response.body) > config.max_response_bytes:
            # Defend against custom transports that fail to enforce the contract.
            raise AcquisitionError("response_too_large", "The source exceeds the configured size limit.")

        content_type = response.headers.get("content-type")
        if not content_type:
            raise AcquisitionError("unsupported_content_type", "The source did not identify a supported text type.")
        media_type, charset = _parse_content_type(content_type)
        if media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise AcquisitionError("unsupported_content_type", "The source is not a supported text page.")
        content_encoding = response.headers.get("content-encoding", "identity").strip().casefold()
        if content_encoding not in {"", "identity"}:
            raise AcquisitionError("unsupported_content_encoding", "The source returned an unsupported content encoding.")
        try:
            decoded = response.body.decode(charset or "utf-8", errors="strict")
        except (LookupError, UnicodeDecodeError) as error:
            raise AcquisitionError("invalid_text_encoding", "The source text encoding is invalid or unsupported.") from error

        normalized = (
            normalize_html(decoded, config.max_text_characters)
            if media_type in {"text/html", "application/xhtml+xml"}
            else normalize_text(decoded, config.max_text_characters)
        )
        return AcquiredSource(
            original_url=original.url,
            final_url=current.url,
            acquisition_method="webpage",
            media_type=media_type,
            normalized_text=normalized,
            content_hash=hash_text(normalized),
            source_byte_count=len(response.body),
            redirect_count=redirect_count,
        )


def system_resolver(hostname: str, port: int) -> Iterable[str]:
    """Resolve TCP addresses through the operating system resolver."""

    return [item[4][0] for item in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)]


def resolve_public_addresses(url: ValidatedUrl, resolver: Resolver, timeout_seconds: float) -> tuple[str, ...]:
    """Resolve a hostname and reject the whole result if any answer is unsafe."""

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pathaid-dns")
    future = executor.submit(lambda: tuple(resolver(url.hostname, url.port)))
    try:
        raw_addresses = future.result(timeout=max(timeout_seconds, 0.001))
    except FutureTimeoutError as error:
        future.cancel()
        raise AcquisitionError("timeout", "Source acquisition timed out.", retryable=True) from error
    except (OSError, socket.gaierror) as error:
        raise AcquisitionError("dns_failure", "The source hostname could not be resolved.", retryable=True) from error
    finally:
        # A platform DNS call cannot always be cancelled, so do not wait for a
        # timed-out resolver thread before returning the bounded workflow error.
        executor.shutdown(wait=False, cancel_futures=True)

    addresses: list[str] = []
    for raw_address in raw_addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as error:
            raise AcquisitionError("dns_failure", "The source hostname returned an invalid address.", retryable=True) from error
        if not _is_public_address(address):
            raise AcquisitionError("unsafe_address", "The source URL resolves to a prohibited destination.")
        normalized = str(address)
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses:
        raise AcquisitionError("dns_failure", "The source hostname did not resolve to an address.", retryable=True)
    return tuple(addresses)


class SocketHttpTransport:
    """Single-hop HTTP transport that connects to the validated address only."""

    def fetch(
        self,
        url: ValidatedUrl,
        address: str,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        connection: http.client.HTTPConnection
        if url.scheme == "https":
            connection = _PinnedHTTPSConnection(url.hostname, address, url.port, timeout_seconds)
        else:
            connection = http.client.HTTPConnection(address, url.port, timeout=timeout_seconds)
        headers = {
            "Host": _host_header(url),
            "User-Agent": "Pathaid/1.0 source-acquisition",
            "Accept": "text/html, application/xhtml+xml, text/plain",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        try:
            connection.request("GET", url.request_target, headers=headers)
            response = connection.getresponse()
            response_headers = {name.casefold(): value for name, value in response.getheaders()}
            length = response_headers.get("content-length")
            if length is not None:
                try:
                    if int(length) > max_response_bytes:
                        raise AcquisitionError("response_too_large", "The source exceeds the configured size limit.")
                except ValueError:
                    pass
            body = response.read(max_response_bytes + 1)
            if len(body) > max_response_bytes:
                raise AcquisitionError("response_too_large", "The source exceeds the configured size limit.")
            return HttpResponse(response.status, response_headers, body)
        except AcquisitionError:
            raise
        except (socket.timeout, TimeoutError) as error:
            raise AcquisitionError("timeout", "Source acquisition timed out.", retryable=True) from error
        except ssl.SSLError as error:
            raise AcquisitionError("tls_failure", "The source HTTPS certificate or connection is invalid.") from error
        except (OSError, http.client.HTTPException) as error:
            raise AcquisitionError("network_failure", "The source could not be retrieved.", retryable=True) from error
        finally:
            connection.close()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Use a validated IP for TCP while checking TLS against the hostname."""

    def __init__(self, hostname: str, address: str, port: int, timeout: float):
        super().__init__(hostname, port, timeout=timeout, context=ssl.create_default_context())
        self._validated_address = address

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._validated_address, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def _fetch_from_addresses(
    url: ValidatedUrl,
    addresses: tuple[str, ...],
    transport: SingleHopTransport,
    deadline: float,
    max_response_bytes: int,
) -> HttpResponse:
    """Try validated addresses in resolver order within the shared deadline."""

    last_error: AcquisitionError | None = None
    for address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AcquisitionError("timeout", "Source acquisition timed out.", retryable=True)
        try:
            return transport.fetch(
                url,
                address,
                timeout_seconds=remaining,
                max_response_bytes=max_response_bytes,
            )
        except AcquisitionError as error:
            if not error.retryable:
                raise
            last_error = error
    if last_error is not None:
        raise last_error
    raise AcquisitionError("network_failure", "The source could not be retrieved.", retryable=True)


def _parse_content_type(value: str) -> tuple[str, str | None]:
    """Parse a media type and optional charset using the standard email parser."""

    message = Message()
    message["content-type"] = value
    return message.get_content_type().casefold(), message.get_content_charset()


def _host_header(url: ValidatedUrl) -> str:
    """Return the original host syntax used for HTTP routing."""

    return f"[{url.hostname}]" if ":" in url.hostname else url.hostname


def normalize_text(value: str, max_characters: int) -> str:
    """Create stable Unicode text while retaining meaningful line boundaries."""

    # NFC preserves characters while ensuring visually equivalent sequences
    # hash consistently. Line endings and horizontal whitespace are normalized
    # so evidence excerpts can be matched against the retained representation.
    value = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in value.split("\n"):
        collapsed = re.sub(r"[\t\f\v ]+", " ", line).strip()
        if collapsed:
            lines.append(collapsed)
        elif lines and lines[-1] != "":
            lines.append("")
    normalized = "\n".join(lines).strip()
    if not normalized:
        raise AcquisitionError("empty_content", "The source does not contain usable text.")
    if len(normalized) > max_characters:
        raise AcquisitionError("response_too_large", "The normalized source exceeds the configured text limit.")
    return normalized


def normalize_html(value: str, max_characters: int) -> str:
    """Extract visible text from HTML and apply the common text normalizer."""

    parser = _VisibleTextParser()
    try:
        parser.feed(value)
        parser.close()
    except (AssertionError, ValueError) as error:
        raise AcquisitionError("invalid_html", "The source contains malformed HTML.") from error
    return normalize_text("".join(parser.parts), max_characters)


def hash_text(value: str) -> str:
    """Return the SHA-256 hash stored with the normalized source snapshot."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_hostname(hostname: str) -> str:
    """Convert internationalized hostnames to their lowercase ASCII form."""

    try:
        normalized = hostname.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as error:
        raise AcquisitionError("invalid_url", "The source hostname is invalid.") from error
    if not normalized or len(normalized) > 253:
        raise AcquisitionError("invalid_url", "The source hostname is invalid.")
    return normalized


def _reject_literal_or_local_hostname(hostname: str) -> None:
    """Reject obvious local names and non-public literal IP addresses."""

    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise AcquisitionError("unsafe_address", "The source URL resolves to a prohibited destination.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not _is_public_address(address):
        raise AcquisitionError("unsafe_address", "The source URL resolves to a prohibited destination.")


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return true only for globally routable unicast addresses."""

    # IPv4-mapped IPv6 values need the IPv4 classification as well.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast


class _VisibleTextParser(HTMLParser):
    """Collect visible HTML text while omitting executable or decorative data."""

    _ignored_tags = {"script", "style", "noscript", "template", "svg"}
    _block_tags = {
        "address", "article", "aside", "blockquote", "br", "div", "dl",
        "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
        "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav",
        "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.casefold()
        if tag in self._ignored_tags:
            self._ignored_depth += 1
        elif self._ignored_depth == 0 and tag in self._block_tags:
            self._append_break()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        elif self._ignored_depth == 0 and tag in self._block_tags:
            self._append_break()

    def handle_data(self, data: str) -> None:
        # Formatting whitespace between HTML tags has no visible meaning. Text
        # containing real characters is retained and normalized afterward.
        if self._ignored_depth == 0 and data.strip():
            self.parts.append(data)

    def _append_break(self) -> None:
        """Separate visible blocks without creating repeated blank lines."""

        if self.parts and self.parts[-1] != "\n":
            self.parts.append("\n")
