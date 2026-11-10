"""Security and migration tests for the loopback local API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.document_vault import store_document
from app.local_data import upgrade_database
from app.main import create_app
from app.models import Essay, LocalProfile, PortalMapping, SavedScholarship, Scholarship, ScholarshipVersion, SourceScanRun, SourceScope, SourceSnapshot
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


def add_in_progress_scholarship(app, *, version_overrides: dict | None = None) -> str:
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
            data={
                "name": "Fixture Scholarship",
                "application_url": "https://example.academicworks.com/apply/1",
                **(version_overrides or {}),
            },
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
            "extension_id": "abcdefghijklmnopabcdefghijklmnop",
        }


def test_home_summary_exposes_operational_counts_and_actionable_alerts(tmp_path):
    app, _settings, _secrets = configured_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/home-summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_sources"] == 0
    assert payload["active_scholarships"] == 0
    assert payload["latest_job"] is None
    assert {alert["code"] for alert in payload["alerts"]} == {
        "school_missing", "sources_missing", "gemini_missing",
    }
    assert all(alert["href"].startswith("/") for alert in payload["alerts"])


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


def test_scholarship_detail_returns_local_evaluation_and_retained_evidence(tmp_path):
    app, _settings, _secrets = configured_app(tmp_path)
    scholarship_id = add_in_progress_scholarship(app, version_overrides={
        "description": "An official fixture scholarship.",
        "sponsor_name": "Fixture Foundation",
        "assistance_amount": "$1,000",
        "application_deadline": "2027-03-15",
        "application_availability": "open",
        "deadline_timezone": "America/New_York",
        "coverage": {"national": True, "states": [], "institutions": []},
        "coverage_complete": True,
        "eligibility_tree": {
            "type": "condition", "field": "gpa", "operator": "gte", "value": 3.0,
            "exceptions_complete": True,
            "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Fixture"},
        },
        "selection_factors": [{
            "description": "Community service considered",
            "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Fixture"},
        }],
        "checklist": [{
            "label": "Transcript", "required": True,
            "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Fixture"},
        }],
        "unresolved_conditions": [],
        "application_process": "separate_application",
        "official_rules_url": None,
        "automation_policy": "unknown",
        "ai_assistance_policy": "unknown",
    })
    with app.state.database.sessions.begin() as db:
        db.get(LocalProfile, 1).data = {"gpa": 3.8}

    with TestClient(app) as client:
        response = client.get(f"/api/scholarships/{scholarship_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Fixture Scholarship"
    assert payload["sponsor"] == "Fixture Foundation"
    assert payload["match_label"] == "Strong match"
    assert payload["criteria"] == [{
        "field": "gpa", "operator": "gte", "truth": "pass",
        "reason": "gpa passes this requirement.", "answerable": True,
        "evidence": {"snapshot_id": "snapshot-1", "excerpt": "Fixture"},
    }]
    assert payload["checklist"][0]["label"] == "Transcript"
    assert payload["selection_factors"][0]["description"] == "Community service considered"
    assert payload["saved_status"] == "in_progress"


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


def test_extension_learns_value_free_mappings_by_origin_and_form_signature(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    scholarship_id = add_in_progress_scholarship(app)
    headers = {"Origin": settings.extension_origin, "X-PathAid-Token": "correct-token"}
    form_signature = "d" * 64
    field_signature = "e" * 64
    payload = {
        "portal_origin": "https://example.academicworks.com",
        "scholarship_id": scholarship_id,
        "form_signature": form_signature,
        "mappings": [{"field_signature": field_signature, "profile_field": "major"}],
    }
    with TestClient(app) as client:
        saved = client.put("/api/extension/mappings", json=payload, headers=headers)
        assert saved.status_code == 200
        assert saved.json() == {"saved": 1}
        learned = client.get(
            "/api/extension/mappings",
            params={
                "portal_origin": payload["portal_origin"],
                "scholarship_id": scholarship_id,
                "form_signature": form_signature,
            },
            headers=headers,
        )
        assert learned.status_code == 200
        assert learned.headers["cache-control"] == "no-store"
        assert learned.json() == {
            "form_signature": form_signature,
            "mappings": [{"field_signature": field_signature, "profile_field": "major"}],
        }
        replaced = client.put(
            "/api/extension/mappings",
            json={**payload, "mappings": [{"field_signature": field_signature, "profile_field": "minor"}]},
            headers=headers,
        )
        assert replaced.status_code == 200
        deleted = client.put(
            "/api/extension/mappings",
            json={**payload, "mappings": [{"field_signature": field_signature, "profile_field": None}]},
            headers=headers,
        )
        assert deleted.status_code == 200
        assert client.get(
            "/api/extension/mappings",
            params={
                "portal_origin": payload["portal_origin"],
                "scholarship_id": scholarship_id,
                "form_signature": form_signature,
            },
            headers=headers,
        ).json()["mappings"] == []
        invalid = client.put(
            "/api/extension/mappings",
            json={**payload, "mappings": [{"field_signature": field_signature, "profile_field": "not_a_profile_field"}]},
            headers=headers,
        )
        assert invalid.status_code == 422
    with app.state.database.sessions() as db:
        assert db.query(PortalMapping).count() == 0


def test_extension_releases_no_profile_data_when_automation_is_blocked(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    scholarship_id = add_in_progress_scholarship(app, version_overrides={
        "automation_policy": "blocked",
        "automation_policy_evidence": {
            "snapshot_id": "snapshot-1",
            "excerpt": "Automated application tools are prohibited.",
        },
    })
    headers = {"Origin": settings.extension_origin, "X-PathAid-Token": "correct-token"}
    parameters = {
        "portal_origin": "https://example.academicworks.com",
        "scholarship_id": scholarship_id,
    }
    with TestClient(app) as client:
        context = client.get("/api/extension/context", params=parameters, headers=headers)
        assert context.status_code == 200
        assert context.json()["state"] == "policy_blocked"
        assert context.json()["automation_policy"] == "blocked"
        assert client.get("/api/extension/profile-values", params=parameters, headers=headers).status_code == 409
        assert client.get(
            "/api/extension/mappings",
            params={**parameters, "form_signature": "f" * 64},
            headers=headers,
        ).status_code == 409


def test_extension_prepares_only_retained_official_application(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    scholarship_id = add_in_progress_scholarship(app)
    with app.state.database.sessions.begin() as db:
        db.get(SavedScholarship, scholarship_id).status = "not_started"
    headers = {"Origin": settings.extension_origin, "X-PathAid-Token": "correct-token"}
    with TestClient(app) as client:
        response = client.put(
            f"/api/extension/applications/{scholarship_id}/prepare",
            json={}, headers=headers,
        )
        assert response.status_code == 200
        assert response.json() == {
            "scholarship_id": scholarship_id,
            "application_url": "https://example.academicworks.com/apply/1",
            "automation_policy": "unknown",
        }
        assert client.put(
            "/api/extension/applications/not-saved/prepare", json={}, headers=headers,
        ).status_code == 404
    with app.state.database.sessions() as db:
        assert db.get(SavedScholarship, scholarship_id).status == "in_progress"


def test_extension_document_content_requires_application_context(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    scholarship_id = add_in_progress_scholarship(app)
    plaintext = b"%PDF-1.7\nprivate transcript"
    store_document(
        app.state.database, app.state.secret_store, "transcript",
        "transcript.pdf", "application/pdf", plaintext,
    )
    headers = {"Origin": settings.extension_origin, "X-PathAid-Token": "correct-token"}
    parameters = {
        "portal_origin": "https://example.academicworks.com",
        "scholarship_id": scholarship_id,
    }
    with app.state.database.sessions.begin() as db:
        db.add(Essay(
            id="essay-1", title="Service & Leadership", original_prompt="Describe service",
            text="My own essay.", tags=["service"], themes=["leadership"], word_count=3,
            written_on=datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
        ))
    with TestClient(app) as client:
        metadata = client.get("/api/extension/documents", params=parameters, headers=headers)
        assert metadata.status_code == 200
        assert metadata.headers["cache-control"] == "no-store"
        assert metadata.json() == {"items": [{
            "document_type": "transcript",
            "original_name": "transcript.pdf",
            "size_bytes": len(plaintext),
        }], "essays": [{"id": "essay-1", "title": "Service & Leadership", "word_count": 3}]}
        content = client.get(
            "/api/extension/documents/transcript/content",
            params=parameters, headers=headers,
        )
        assert content.status_code == 200
        assert content.content == plaintext
        assert content.headers["cache-control"] == "no-store"
        essay = client.get(
            "/api/extension/essays/essay-1/content",
            params=parameters, headers=headers,
        )
        assert essay.status_code == 200
        assert essay.content == b"My own essay."
        assert essay.headers["content-type"].startswith("text/plain")
        assert essay.headers["x-pathaid-filename"] == "Service%20%20Leadership.txt"
        denied = client.get(
            "/api/extension/documents/transcript/content",
            params={**parameters, "portal_origin": "https://other.example"},
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
