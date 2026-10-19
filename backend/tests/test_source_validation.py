"""Tests for source URL validation, normalization, and pasted provenance."""

import pytest

from app.source_acquisition import (
    AcquisitionConfig,
    AcquisitionError,
    PastedSourceRequest,
    hash_text,
    normalize_html,
    normalize_text,
    prepare_pasted_source,
    validate_source_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.edu/source",
        "https://user:secret@example.edu/source",
        "https://example.edu:8443/source",
        "https://example.edu/source#requirements",
        "https://localhost/source",
        "https://catalog.local/source",
        "http://127.0.0.1/source",
        "http://10.0.0.1/source",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/source",
        "not a URL",
    ],
)
def test_rejects_malformed_or_obviously_unsafe_urls(url):
    """Unsafe URL forms fail before DNS or network access can occur."""

    with pytest.raises(AcquisitionError):
        validate_source_url(url)


def test_normalizes_public_url_and_request_target():
    """Hostname case, default ports, and empty paths receive stable forms."""

    result = validate_source_url("HTTPS://ExAmPlE.edu:443?cycle=2027")
    assert result.url == "https://example.edu/?cycle=2027"
    assert result.hostname == "example.edu"
    assert result.port == 443
    assert result.request_target == "/?cycle=2027"


def test_normalizes_text_and_hash_deterministically():
    """Equivalent whitespace and Unicode representations produce one hash."""

    first = normalize_text("  Caf\u00e9  \r\n\r\n  Requirements  ", 100)
    second = normalize_text("Cafe\u0301\n\nRequirements", 100)
    assert first == second == "Caf\u00e9\n\nRequirements"
    assert hash_text(first) == hash_text(second)


def test_html_extraction_omits_scripts_styles_and_templates():
    """Only visible webpage content enters the retained extraction text."""

    html = """
    <html><head><style>secret-style</style><script>secret-script</script></head>
    <body><h1>Scholarship &amp; Grant</h1><p>Apply today.</p>
    <template>secret-template</template></body></html>
    """
    normalized = normalize_html(html, 1_000)
    assert normalized == "Scholarship & Grant\nApply today."
    assert "secret" not in normalized


def test_pasted_source_records_unverified_method_without_network():
    """Pasted text retains its claimed URL and receives deterministic metadata."""

    result = prepare_pasted_source(PastedSourceRequest("https://example.edu/aid", " Aid details. "))
    assert result.original_url == result.final_url == "https://example.edu/aid"
    assert result.acquisition_method == "pasted_text"
    assert result.media_type == "text/plain"
    assert result.normalized_text == "Aid details."
    assert result.content_hash == hash_text("Aid details.")
    assert result.redirect_count == 0


def test_empty_and_oversized_pasted_sources_return_safe_errors():
    """Errors identify the problem without repeating submitted source content."""

    secret = "private-source-value"
    with pytest.raises(AcquisitionError) as empty:
        prepare_pasted_source(PastedSourceRequest("https://example.edu", " \n "))
    assert empty.value.code == "empty_content"

    with pytest.raises(AcquisitionError) as oversized:
        prepare_pasted_source(
            PastedSourceRequest("https://example.edu", secret),
            AcquisitionConfig(max_response_bytes=4),
        )
    assert oversized.value.code == "response_too_large"
    assert secret not in str(oversized.value)
