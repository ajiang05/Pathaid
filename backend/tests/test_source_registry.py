"""Acceptance tests for explicit source approval and school ownership."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database
from app.local_data import upgrade_database
from app.main import create_app
from app.models import SourceScope
from app.source_registry import import_ipeds_directory, scope_allows_url
from conftest import FakeSecretStore


def local_app(tmp_path):
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    csv_path = tmp_path / "HD2025.csv"
    csv_path.write_text(
        "UNITID,INSTNM,ALIAS,CITY,STABBR,WEBADDR\n"
        "166629,University of Massachusetts Amherst,UMass Amherst|UMass,Amherst,MA,www.umass.edu\n"
        "190150,Columbia University,,New York,NY,www.columbia.edu\n",
        encoding="utf-8",
    )
    database = Database(settings)
    with database.sessions.begin() as db:
        assert import_ipeds_directory(db, csv_path, source_year=2025) == 2
    database.close()
    return create_app(settings, FakeSecretStore()), settings


def select_umass(client: TestClient):
    response = client.post("/api/institutions/166629/select")
    assert response.status_code == 200
    return response.json()


def school_scope(**overrides):
    body = {
        "name": "UMass scholarships",
        "ownership": "school",
        "adapter": "generic",
        "canonical_url": "https://www.umass.edu/financialaid/undergraduate-scholarships",
        "allowed_path_prefix": "/financialaid",
        "institution_unit_id": "166629",
        "max_depth": 2,
        "page_budget": 20,
        "requests_per_minute": 6,
        "scan_interval_hours": 24,
    }
    body.update(overrides)
    return body


def sponsor_scope(**overrides):
    body = {
        "name": "Example sponsor",
        "ownership": "sponsor",
        "adapter": "generic",
        "canonical_url": "https://scholarships.example.org/awards",
        "allowed_path_prefix": "/awards",
        "institution_unit_id": None,
        "max_depth": 1,
        "page_budget": 10,
        "requests_per_minute": 5,
        "scan_interval_hours": 48,
    }
    body.update(overrides)
    return body


def test_ipeds_search_and_selection_updates_authoritative_profile_fields(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        results = client.get("/api/institutions", params={"q": "umass"}).json()
        assert [(item["unit_id"], item["source"], item["source_year"]) for item in results] == [("166629", "NCES IPEDS", 2025)]
        selected = select_umass(client)
        assert selected["changed"] is True
        profile = client.get("/api/profile").json()
        expected = {
            "school_id": "166629", "school": "University of Massachusetts Amherst",
            "school_city": "Amherst", "school_state": "MA",
        }
        assert expected.items() <= profile["fields"].items()


def test_unconfirmed_scope_cannot_scan_and_confirmation_is_explicit(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        select_umass(client)
        proposal = client.post("/api/sources", json=school_scope())
        assert proposal.status_code == 201
        source = proposal.json()
        assert source["status"] == "proposed"
        assert source["confirmed_at"] is None and source["next_scan_at"] is None
        blocked = client.post(f"/api/sources/{source['id']}/scan-now")
        assert blocked.status_code == 422
        active = client.post(f"/api/sources/{source['id']}/confirm").json()
        assert active["status"] == "active"
        assert active["confirmed_at"] is not None and active["next_scan_at"] is not None
        queued = client.post(f"/api/sources/{source['id']}/scan-now").json()
        assert queued["scan_requested_at"] is not None


def test_exact_host_and_path_boundary_never_silently_widens(tmp_path):
    app, settings = local_app(tmp_path)
    with TestClient(app) as client:
        select_umass(client)
        source_id = client.post("/api/sources", json=school_scope()).json()["id"]
    database = Database(settings)
    with database.sessions() as db:
        scope = db.get(SourceScope, source_id)
        assert scope_allows_url(scope, "https://www.umass.edu/financialaid/scholarships/one")
        assert not scope_allows_url(scope, "https://www.umass.edu/financial-aid/one")
        assert not scope_allows_url(scope, "https://www.umass.edu/financialaid-other/one")
        assert not scope_allows_url(scope, "https://evil.example/financialaid/one")
    database.close()


def test_pause_resume_preserves_scan_history(tmp_path):
    app, settings = local_app(tmp_path)
    with TestClient(app) as client:
        select_umass(client)
        source_id = client.post("/api/sources", json=school_scope()).json()["id"]
        client.post(f"/api/sources/{source_id}/confirm")
        database = Database(settings)
        historical = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with database.sessions.begin() as db:
            db.get(SourceScope, source_id).last_success_at = historical
        database.close()
        paused = client.post(f"/api/sources/{source_id}/pause").json()
        assert paused["status"] == "paused" and paused["next_scan_at"] is None
        assert paused["last_success_at"].startswith("2026-10-01")
        assert client.post(f"/api/sources/{source_id}/scan-now").status_code == 422
        resumed = client.post(f"/api/sources/{source_id}/resume").json()
        assert resumed["status"] == "active" and resumed["next_scan_at"] is not None
        assert resumed["last_success_at"].startswith("2026-10-01")


def test_manual_lead_does_not_create_or_authorize_a_scope(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        lead = client.post("/api/leads", json={"title": "BigFuture lead", "url": "https://bigfuture.collegeboard.org/scholarships/example"})
        assert lead.status_code == 201 and lead.json()["status"] == "unverified"
        assert client.get("/api/sources").json() == []
        prohibited = client.post("/api/sources", json=sponsor_scope(
            canonical_url="https://bigfuture.collegeboard.org/scholarships",
            allowed_path_prefix="/scholarships",
        ))
        assert prohibited.status_code == 422
        assert prohibited.json()["detail"]["code"] == "manual_only_source"


def test_school_change_deactivates_only_school_owned_scopes(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        select_umass(client)
        school = client.post("/api/sources", json=school_scope()).json()
        sponsor = client.post("/api/sources", json=sponsor_scope()).json()
        client.post(f"/api/sources/{school['id']}/confirm")
        client.post(f"/api/sources/{sponsor['id']}/confirm")
        changed = client.post("/api/institutions/190150/select").json()
        assert changed["changed"] is True
        items = {item["id"]: item for item in client.get("/api/sources").json()}
        assert items[school["id"]]["status"] == "inactive"
        assert items[school["id"]]["next_scan_at"] is None
        assert items[sponsor["id"]]["status"] == "active"


def test_free_text_school_change_clears_stale_unit_id_and_deactivates_scope(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        select_umass(client)
        school = client.post("/api/sources", json=school_scope()).json()
        client.post(f"/api/sources/{school['id']}/confirm")
        changed = client.patch("/api/profile", json={"fields": {"school": "A different institution"}}).json()
        assert "school_id" not in changed["fields"]
        assert changed["school_changed"] is True
        stored = {item["id"]: item for item in client.get("/api/sources").json()}
        assert stored[school["id"]]["status"] == "inactive"


def test_generic_school_scope_requires_official_host_and_current_school(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        select_umass(client)
        unofficial = client.post("/api/sources", json=school_scope(canonical_url="https://example.com/scholarships", allowed_path_prefix="/scholarships"))
        assert unofficial.status_code == 422
        assert unofficial.json()["detail"]["code"] == "unofficial_school_host"
        wrong_school = client.post("/api/sources", json=school_scope(institution_unit_id="190150"))
        assert wrong_school.status_code == 422
        assert wrong_school.json()["detail"]["code"] == "school_mismatch"
        suffix_trick = client.post("/api/sources", json=school_scope(canonical_url="https://edu/scholarships", allowed_path_prefix="/scholarships"))
        assert suffix_trick.status_code == 422
        assert suffix_trick.json()["detail"]["code"] == "unofficial_school_host"


def test_academicworks_scope_requires_explicit_root_boundary(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        select_umass(client)
        too_narrow = client.post("/api/sources", json=school_scope(
            adapter="academicworks",
            canonical_url="https://umass.academicworks.com/opportunities",
            allowed_path_prefix="/opportunities",
        ))
        assert too_narrow.status_code == 422
        assert too_narrow.json()["detail"]["code"] == "invalid_adapter_boundary"
        valid = client.post("/api/sources", json=school_scope(
            adapter="academicworks",
            canonical_url="https://umass.academicworks.com/opportunities",
            allowed_path_prefix="/",
        ))
        assert valid.status_code == 201
