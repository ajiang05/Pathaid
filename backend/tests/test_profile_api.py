"""API and persistence tests for the private singleton student profile."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database
from app.local_data import upgrade_database
from app.main import create_app
from app.models import AppSetting, LocalProfile, ProfileExperience
from conftest import FakeSecretStore


def local_app(tmp_path):
    data = tmp_path / "data"
    settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")
    upgrade_database(settings)
    return create_app(settings, FakeSecretStore()), settings


def test_registry_separates_all_three_locations_and_has_no_aid_categories(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        payload = client.get("/api/profile-fields").json()
    fields = payload["fields"]
    assert {"school_state", "current_state", "permanent_state"} <= set(fields)
    assert "state" not in fields
    assert "assistance_categories" not in fields
    assert payload["unknown_answer"] == {"status": "unknown"}
    assert fields["race"]["sensitive"] is True
    assert fields["first_generation_student"]["sensitive"] is True
    assert fields["pell_eligible"]["sensitive"] is True


def test_structured_experiences_are_a_canonical_matching_field():
    from app.profile_fields import FIELDS, MATCH_FIELDS

    assert "experiences" not in FIELDS
    assert MATCH_FIELDS["experiences"]["type"] == "experience_list"


def test_profile_preserves_known_unknown_unanswered_and_structured_experiences(tmp_path):
    app, _settings = local_app(tmp_path)
    body = {
        "fields": {
            "school": "UMass Amherst",
            "school_state": "MA",
            "current_state": "NY",
            "permanent_state": {"status": "unknown"},
            "study_level": "undergraduate",
            "enrollment": "full_time",
            "gpa": 3.75,
            "gpa_scale": 4.0,
            "expected_graduation": "2028-05",
            "race": ["asian", "white"],
            "first_generation_student": True,
            "pell_eligible": False,
        },
        "experiences": [{
            "kind": "volunteering",
            "organization": "Community Food Bank",
            "title": "Team lead",
            "description": "Coordinated weekly volunteers.",
            "start_date": "2025-01-01",
            "current": True,
            "hours": 125,
            "leadership": True,
            "tags": ["Community Service", "Food Access"],
        }],
    }
    with TestClient(app) as client:
        saved = client.patch("/api/profile", json=body)
        assert saved.status_code == 200
        payload = saved.json()
        assert payload["fields"]["school"] == "University of Massachusetts Amherst"
        assert payload["fields"]["current_state"] == "NY"
        assert payload["fields"]["permanent_state"] == {"status": "unknown"}
        assert "permanent_city" not in payload["fields"]
        assert payload["completeness"]["unknown"] == 1
        assert payload["completeness"]["unanswered"] > 0
        assert payload["experiences"][0]["tags"] == ["community service", "food access"]
        assert payload["experiences"][0]["leadership"] is True
        reloaded = client.get("/api/profile").json()
        assert reloaded == {**payload, "school_changed": False}


def test_school_change_increments_revision_and_emits_onboarding_setting(tmp_path):
    app, settings = local_app(tmp_path)
    with TestClient(app) as client:
        first = client.patch("/api/profile", json={"fields": {"school": "First College"}}).json()
        unchanged = client.patch("/api/profile", json={"fields": {"major": "Computer Science"}}).json()
        changed = client.patch("/api/profile", json={"fields": {"school": "Second College"}}).json()
    assert first["school_changed"] is True and first["school_revision"] == 1
    assert unchanged["school_changed"] is False and unchanged["school_revision"] == 1
    assert changed["school_changed"] is True and changed["school_revision"] == 2

    database = Database(settings)
    with database.sessions() as session:
        assert session.get(AppSetting, "needs_school_source_onboarding").value == "true"
    database.close()


def test_profile_validation_never_echoes_sensitive_values(tmp_path):
    app, _settings = local_app(tmp_path)
    secret_value = "not-an-email-SENSITIVE-CANARY"
    with TestClient(app) as client:
        response = client.patch("/api/profile", json={"fields": {"email": secret_value}})
        assert response.status_code == 422
        assert secret_value not in response.text
        assert response.json() == {"detail": {"field": "email", "message": "Invalid profile answer"}}


def test_experience_replacement_and_profile_clear_are_local_and_accountless(tmp_path):
    app, settings = local_app(tmp_path)
    first = {"kind": "employment", "organization": "Company", "title": "Intern", "current": False, "tags": []}
    second = {"kind": "honor", "organization": "College", "title": "Dean's List", "current": False, "tags": []}
    with TestClient(app) as client:
        assert client.patch("/api/profile", json={"fields": {"major": "History"}, "experiences": [first]}).status_code == 200
        replaced = client.patch("/api/profile", json={"experiences": [second]}).json()
        assert [item["kind"] for item in replaced["experiences"]] == ["honor"]
        assert client.delete("/api/profile").status_code == 204
        cleared = client.get("/api/profile").json()
        assert cleared["fields"] == {}
        assert cleared["experiences"] == []
        assert client.get("/api/auth/session").status_code == 404

    database = Database(settings)
    with database.sessions() as session:
        assert session.get(LocalProfile, 1).data == {}
        assert session.query(ProfileExperience).count() == 0
    database.close()


def test_discover_boundary_is_empty_until_approved_sources_exist(tmp_path):
    app, _settings = local_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/matches")
    assert response.status_code == 200
    assert response.json()["catalog_status"] == "awaiting_approved_sources"
    assert response.json()["results"] == []

