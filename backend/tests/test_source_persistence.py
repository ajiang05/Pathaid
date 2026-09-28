"""Tests for committing fully acquired source snapshots to the catalog."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import SourceSnapshot
from app.source_acquisition import AcquisitionError, HttpResponse, PastedSourceRequest, WebSourceRequest
from app.source_service import acquire_and_persist_source


PUBLIC_IP = "93.184.216.34"


@pytest.fixture
def database():
    """Create a clean database containing the complete current metadata."""

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


class OneResponseTransport:
    """Return one controlled webpage response without live network access."""

    def __init__(self, response):
        self.response = response

    def fetch(self, url, address, *, timeout_seconds, max_response_bytes):
        return self.response


def test_pasted_text_persists_complete_provenance(database):
    """Pasted content is explicitly labeled and stored in normalized form."""

    with Session(database) as db:
        snapshot = acquire_and_persist_source(
            db,
            PastedSourceRequest("https://example.edu/aid", "  Aid details.  "),
        )
        assert snapshot.id
        assert snapshot.source_url == snapshot.final_url == "https://example.edu/aid"
        assert snapshot.acquisition_method == "pasted_text"
        assert snapshot.media_type == "text/plain"
        assert snapshot.source_text == "Aid details."
        assert snapshot.source_byte_count == len("  Aid details.  ".encode())
        assert snapshot.redirect_count == 0
        assert snapshot.acquired_at is not None


def test_webpage_persists_final_url_and_redirect_count(database):
    """A fetched page stores both submitted and final destination metadata."""

    class RedirectTransport:
        def __init__(self):
            self.calls = 0

        def fetch(self, url, address, *, timeout_seconds, max_response_bytes):
            self.calls += 1
            if self.calls == 1:
                return HttpResponse(302, {"location": "https://provider.example/final"}, b"")
            return HttpResponse(200, {"content-type": "text/html"}, b"<p>Final details</p>")

    with Session(database) as db:
        snapshot = acquire_and_persist_source(
            db,
            WebSourceRequest("https://example.edu/start"),
            resolver=lambda _host, _port: [PUBLIC_IP],
            transport=RedirectTransport(),
        )
        assert snapshot.source_url == "https://example.edu/start"
        assert snapshot.final_url == "https://provider.example/final"
        assert snapshot.acquisition_method == "webpage"
        assert snapshot.media_type == "text/html"
        assert snapshot.redirect_count == 1
        assert snapshot.source_text == "Final details"


def test_identical_content_creates_distinct_snapshots(database):
    """Repeated acquisition preserves history instead of silently deduplicating."""

    request = PastedSourceRequest("https://example.edu/aid", "Same content")
    with Session(database) as db:
        first = acquire_and_persist_source(db, request)
        second = acquire_and_persist_source(db, request)
        assert first.id != second.id
        assert first.content_hash == second.content_hash
        assert len(db.scalars(select(SourceSnapshot)).all()) == 2


def test_acquisition_failure_leaves_no_snapshot(database):
    """Validation or retrieval failures occur before any database write."""

    failure = AcquisitionError("network_failure", "The source could not be retrieved.", retryable=True)

    class RaisingTransport(OneResponseTransport):
        def fetch(self, url, address, *, timeout_seconds, max_response_bytes):
            raise self.response

    with Session(database) as db:
        with pytest.raises(AcquisitionError):
            acquire_and_persist_source(
                db,
                WebSourceRequest("https://example.edu/source"),
                resolver=lambda _host, _port: [PUBLIC_IP],
                transport=RaisingTransport(failure),
            )
        assert db.scalars(select(SourceSnapshot)).all() == []


def test_database_failure_rolls_back_session():
    """A failed commit explicitly restores the session before propagating."""

    class FailingSession:
        def __init__(self):
            self.added = None
            self.rolled_back = False

        def add(self, value):
            self.added = value

        def commit(self):
            raise RuntimeError("synthetic database failure")

        def rollback(self):
            self.rolled_back = True

    db = FailingSession()
    with pytest.raises(RuntimeError, match="synthetic database failure"):
        acquire_and_persist_source(db, PastedSourceRequest("https://example.edu/source", "Details"))
    assert db.added is not None
    assert db.rolled_back is True
