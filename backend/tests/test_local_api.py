"""Security and migration tests for the loopback local API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.local_data import upgrade_database
from app.main import create_app
from app.models import LocalProfile, SavedScholarship, Scholarship, ScholarshipVersion, SourceScanRun, SourceScope, SourceSnapshot
from app.secrets import EXTENSION_TOKEN
from conftest import FakeSecretStore


def configured_app(tmp_path, *, extension_id="abcdefghijklmnopabcdefghijklmnop"):
    data_dir = tmp_path / "data"
    settings = Settings(
        data_dir=data_dir,
        database_path=data_dir / "pathaid.sqlite3",
        web_origin="http://127.0.0.1:3000",
        extension_id=extension_id,
    )
    upgrade_database(settings)
    secrets = FakeSecretStore({EXTENSION_TOKEN: "correct-token"})
    return create_app(settings, secrets), settings, secrets


def add_in_progress_scholarship(app) -> str:
    """Create the minimum retained evidence chain needed by extension context."""

    moment = datetime(2026, 11, 2, tzinfo=timezone.utc)
    with app.state.database.sessions.begin() as db:
        db.add(SourceScope(
            id="scope-1", name="Fixture", ownership="sponsor", adapter="academicworks",
            canonical_url="https://example.academicworks.com/", hostname="example.academicworks.com",
            allowed_path_prefix="/", status="paused", confirmed_at=moment, max_depth=1,
            page_budget=10, requests_per_minute=10, scan_interval_hours=24, policy_status="allowed",
        ))
        db.flush()
        db.add(SourceScanRun(
            id="run-1", source_scope_id="scope-1", status="succeeded", started_at=moment,
            finished_at=moment, pages_attempted=1, snapshots_created=1, unchanged_pages=0,
            traversal_truncated=False,
        ))
        db.flush()
        db.add(SourceSnapshot(
            id="snapshot-1", source_scope_id="scope-1", scan_run_id="run-1",
            canonical_url="https://example.academicworks.com/opportunities/1",
            final_url="https://example.academicworks.com/opportunities/1", acquired_at=moment,
            content_hash="a" * 64, media_type="text/html", normalized_text="Fixture",
            source_byte_count=7, redirect_count=0, depth=1,
        ))
        db.flush()
        scholarship = Scholarship(
            id="scholarship-1", source_url="https://example.academicworks.com/opportunities/1",
            status="active",
        )
        db.add(scholarship)
        db.flush()
        version = ScholarshipVersion(
            id="version-1", scholarship_id=scholarship.id, source_snapshot_id="snapshot-1",
            draft_hash="b" * 64, material_fingerprint="c" * 64,
            data={"name": "Fixture Scholarship", "application_url": "https://example.academicworks.com/apply/1"},
            validation_findings=[], extraction_model="fixture", prompt_version="2.1.0",
            schema_version="1.1.0", activated_at=moment,
        )
        db.add(version)
        db.flush()
        scholarship.active_version_id = version.id
        db.add(SavedScholarship(scholarship_id=scholarship.id, status="in_progress"))
    return scholarship.id


def test_health_and_nonsecret_local_status(tmp_path):
    app, _settings, _secrets = configured_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert client.get("/api/local/status").json() == {
            "mode": "local_single_user",
            "database": "sqlite",
            "extension_configured": True,
        }


def test_readiness_requires_current_migration(tmp_path):
    data_dir = tmp_path / "data"
    settings = Settings(data_dir=data_dir, database_path=data_dir / "empty.sqlite3")
    app = create_app(settings, FakeSecretStore())
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "reason": "database_migration_required"}


def test_extension_requires_exact_origin_and_installation_token(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    valid_headers = {"Origin": settings.extension_origin, "X-PathAid-Token": "correct-token"}
    with TestClient(app) as client:
        assert client.get("/api/extension/ping", headers=valid_headers).json() == {"status": "connected"}
        assert client.get("/api/extension/ping", headers={**valid_headers, "X-PathAid-Token": "wrong"}).status_code == 401
        assert client.get("/api/extension/ping", headers={**valid_headers, "Origin": "https://attacker.example"}).status_code == 403
        assert client.get("/api/extension/ping", headers={"X-PathAid-Token": "correct-token"}).status_code == 403
    assert b"correct-token" not in settings.database_path.read_bytes()


def test_extension_context_requires_exact_in_progress_portal_origin(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    scholarship_id = add_in_progress_scholarship(app)
    headers = {"Origin": settings.extension_origin, "X-PathAid-Token": "correct-token"}
    with TestClient(app) as client:
        supported = client.get(
            "/api/extension/context",
            params={"portal_origin": "https://example.academicworks.com", "scholarship_id": scholarship_id},
            headers=headers,
        )
        assert supported.status_code == 200
        assert supported.json() == {
            "state": "supported", "scholarship_id": scholarship_id,
            "scholarship_name": "Fixture Scholarship",
            "portal_origin": "https://example.academicworks.com",
            "application_url": "https://example.academicworks.com/apply/1",
            "adapter": "academicworks",
        }
        mismatch = client.get(
            "/api/extension/context",
            params={"portal_origin": "https://other.example"}, headers=headers,
        )
        assert mismatch.json()["state"] == "unsupported"
        invalid = client.get(
            "/api/extension/context",
            params={"portal_origin": "https://example.academicworks.com/path"}, headers=headers,
        )
        assert invalid.status_code == 422
        unauthenticated = client.get(
            "/api/extension/context",
            params={"portal_origin": "https://example.academicworks.com"},
        )
        assert unauthenticated.status_code == 403


def test_extension_profile_values_require_context_and_omit_unknowns(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    scholarship_id = add_in_progress_scholarship(app)
    with app.state.database.sessions.begin() as db:
        db.get(LocalProfile, 1).data = {
            "first_name": "Aidan", "email": "aidan@example.com",
            "gpa": 3.8, "pell_eligible": {"status": "unknown"},
        }
    headers = {"Origin": settings.extension_origin, "X-PathAid-Token": "correct-token"}
    with TestClient(app) as client:
        response = client.get(
            "/api/extension/profile-values",
            params={
                "portal_origin": "https://example.academicworks.com",
                "scholarship_id": scholarship_id,
            },
            headers=headers,
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "scholarship_id": scholarship_id,
            "fields": [
                {"name": "first_name", "label": "First name", "value": "Aidan", "sensitive": False},
                {"name": "email", "label": "Email address", "value": "aidan@example.com", "sensitive": True},
                {"name": "gpa", "label": "GPA", "value": 3.8, "sensitive": False},
            ],
        }
        denied = client.get(
            "/api/extension/profile-values",
            params={"portal_origin": "https://other.example", "scholarship_id": scholarship_id},
            headers=headers,
        )
        assert denied.status_code == 409


def test_unconfigured_extension_fails_closed(tmp_path):
    app, _settings, _secrets = configured_app(tmp_path, extension_id=None)
    with TestClient(app) as client:
        response = client.get(
            "/api/extension/ping",
            headers={"Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop", "X-PathAid-Token": "correct-token"},
        )
        assert response.status_code == 503


def test_host_and_cors_boundaries_are_narrow(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/health/live", headers={"Host": "attacker.example"}).status_code == 400
        preflight = client.options(
            "/api/extension/ping",
            headers={
                "Origin": settings.extension_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-PathAid-Token",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == settings.extension_origin
        denied = client.options(
            "/api/extension/ping",
            headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "GET"},
        )
        assert denied.status_code == 400


def test_legacy_account_admin_and_publication_routes_are_absent(tmp_path):
    app, _settings, _secrets = configured_app(tmp_path)
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert not any(path.startswith("/api/auth") for path in paths)
    assert not any(path.startswith("/api/admin") for path in paths)
    assert "/api/programs" not in paths
    assert "/api/evaluate" not in paths
