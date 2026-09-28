"""Safe, bounded acquisition of administrator-supplied program sources.

This module treats every URL and source body as untrusted input. The public
entry points return normalized text and provenance for later persistence; they
never interpret webpage text as instructions or grant it application authority.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import SplitResult, urlsplit, urlunsplit


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
