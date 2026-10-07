"""Protected API tests for ingestion submission, inspection, and retry."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, password_hash
from app.models import IngestionRun, SourceSnapshot


@pytest.fixture
def admin_client(monkeypatch):
    """Return an authenticated-capable API and isolated database."""

    monkeypatch.setenv("PATHAID_ADMIN_EMAIL", "admin@pathaid.example")
    monkeypatch.setenv("PATHAID_ADMIN_PASSWORD_HASH", password_hash("strong admin password 123"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def authenticate(client):
    """Log in as the configured administrator and return mutation headers."""

    response = client.post(
        "/api/admin/auth/login",
        json={"email": "admin@pathaid.example", "password": "strong admin password 123"},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_admin_authentication_and_csrf_protect_ingestion_routes(admin_client):
    """Neither anonymous users nor read-only sessions can queue work."""

    api, _ = admin_client
    body = {"idempotency_key": "request-1", "source_url": "https://example.edu/aid", "source_method": "webpage"}
    assert api.get("/api/admin/ingestion-runs").status_code == 401
    assert api.post("/api/admin/ingestion-runs", json=body).status_code == 401
    authenticate(api)
    assert api.post("/api/admin/ingestion-runs", json=body).status_code == 403


def test_submit_list_and_idempotently_return_a_run(admin_client):
    """Protected submissions use the existing durable idempotency contract."""

    api, _ = admin_client
    headers = authenticate(api)
    body = {
        "idempotency_key": "request-1",
        "source_url": "https://example.edu/aid",
        "source_method": "pasted_text",
        "source_text": "Official synthetic details.",
    }
    first = api.post("/api/admin/ingestion-runs", headers=headers, json=body)
    second = api.post("/api/admin/ingestion-runs", headers=headers, json=body)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    listed = api.get("/api/admin/ingestion-runs").json()
    assert len(listed) == 1
    assert listed[0]["state"] == "queued"
    # Summary endpoints do not return retained or submitted source bodies.
    assert "source_text" not in listed[0]
    assert "Official synthetic details" not in api.get("/api/admin/ingestion-runs").text


def test_conflicting_idempotency_and_invalid_source_shapes_are_rejected(admin_client):
    """Changed payloads and mismatched source methods have explicit outcomes."""

    api, _ = admin_client
    headers = authenticate(api)
    base = {"idempotency_key": "same", "source_url": "https://example.edu/aid", "source_method": "webpage"}
    assert api.post("/api/admin/ingestion-runs", headers=headers, json=base).status_code == 201
    changed = {**base, "source_url": "https://example.edu/other"}
    assert api.post("/api/admin/ingestion-runs", headers=headers, json=changed).status_code == 409
    invalid = {**base, "idempotency_key": "invalid", "source_text": "body"}
    assert api.post("/api/admin/ingestion-runs", headers=headers, json=invalid).status_code == 422


def test_detail_exposes_retained_source_only_to_admin(admin_client):
    """The protected detail endpoint supplies side-by-side review material."""

    api, engine = admin_client
    headers = authenticate(api)
    with Session(engine) as db:
        snapshot = SourceSnapshot(
            source_url="https://example.edu/aid",
            final_url="https://example.edu/aid",
            acquisition_method="pasted_text",
            content_hash="a" * 64,
            source_text="Retained private review text.",
        )
        db.add(snapshot)
        db.flush()
        run = IngestionRun(
            idempotency_key="detail",
            request_fingerprint="b" * 64,
            source_url=snapshot.source_url,
            source_method="pasted_text",
            state="awaiting_review",
            source_snapshot_id=snapshot.id,
            validation_findings=[{"code": "warning"}],
            extracted_draft={"name": "Draft"},
        )
        db.add(run)
        db.commit()
        run_id = run.id
    detail = api.get(f"/api/admin/ingestion-runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["source_snapshot"]["source_text"] == "Retained private review text."
    api.cookies.clear()
    assert api.get(f"/api/admin/ingestion-runs/{run_id}").status_code == 401


def test_manual_retry_links_failed_run_and_reuses_snapshot(admin_client):
    """A protected retry retains history and starts from completed acquisition."""

    api, engine = admin_client
    headers = authenticate(api)
    with Session(engine) as db:
        snapshot = SourceSnapshot(
            source_url="https://example.edu/aid",
            acquisition_method="webpage",
            content_hash="c" * 64,
            source_text="Saved source.",
        )
        db.add(snapshot)
        db.flush()
        failed = IngestionRun(
            idempotency_key="failed",
            request_fingerprint="d" * 64,
            source_url=snapshot.source_url,
            source_method="webpage",
            state="failed",
            source_snapshot_id=snapshot.id,
            validation_findings=[],
        )
        db.add(failed)
        db.commit()
        failed_id = failed.id
        snapshot_id = snapshot.id
    response = api.post(
        f"/api/admin/ingestion-runs/{failed_id}/retry",
        headers=headers,
        json={"idempotency_key": "manual-retry"},
    )
    assert response.status_code == 201
    assert response.json()["parent_run_id"] == failed_id
    assert response.json()["state"] == "extracting"
    with Session(engine) as db:
        assert db.get(IngestionRun, response.json()["id"]).source_snapshot_id == snapshot_id
