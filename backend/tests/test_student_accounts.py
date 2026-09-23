"""API-level tests for student authentication, profiles, and privacy rules."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Student, StudentSession


@pytest.fixture
def client():
    """Run each test against a new in-memory SQLite database."""

    # StaticPool makes every session reuse the same in-memory connection. An
    # ordinary pool could give each session a separate empty SQLite database.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # Tests create tables directly for speed. Migration behavior should also be
    # checked separately against PostgreSQL before deployment.
    Base.metadata.create_all(engine)

    def test_db():
        """Replace the production session dependency with the test database."""

        with Session(engine) as db:
            yield db

    # FastAPI dependency overrides let the real routes run unchanged while all
    # database reads and writes are isolated to this test's engine.
    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def signup(client, email="student@example.edu"):
    """Create a test account and return the CSRF token for mutations."""

    response = client.post("/api/auth/signup", json={"email": email, "password": "strong password 123"})
    assert response.status_code == 201, response.text
    return response.json()["csrf_token"]


def test_signup_profile_edit_reload_and_deletion(client):
    """Exercise the complete saved-profile and account deletion lifecycle."""

    api, engine = client
    signup_response = api.post("/api/auth/signup", json={"email": "student@example.edu", "password": "strong password 123"})
    assert signup_response.status_code == 201
    csrf = signup_response.json()["csrf_token"]
    # HttpOnly prevents browser JavaScript from reading the session cookie.
    assert "httponly" in signup_response.headers["set-cookie"].lower()
    response = api.patch(
        "/api/profile",
        headers={"X-CSRF-Token": csrf},
        json={"fields": {"school": "UMass Amherst", "state": "MA", "study_level": "undergraduate", "enrollment": "full_time", "assistance_categories": ["scholarships", "food"]}, "ai_opt_in": True},
    )
    assert response.status_code == 200, response.text
    # Common UMass spellings should be stored under one canonical name.
    assert response.json()["fields"]["school"] == "University of Massachusetts Amherst"
    assert api.get("/api/profile").json()["ai_opt_in"] is True
    fresh_csrf = api.get("/api/auth/session").json()["csrf_token"]
    # Rotating the CSRF token invalidates the token issued at sign-up.
    assert api.patch("/api/profile", headers={"X-CSRF-Token": csrf}, json={"fields": {}}).status_code == 403
    # Null removes a saved optional answer.
    assert api.patch("/api/profile", headers={"X-CSRF-Token": fresh_csrf}, json={"fields": {"school": None}}).status_code == 200
    assert "school" not in api.get("/api/profile").json()["fields"]
    assert api.delete("/api/profile", headers={"X-CSRF-Token": fresh_csrf}).status_code == 204
    assert api.get("/api/profile").status_code == 401
    # Check the database as well as the HTTP response to confirm deletion and
    # the session cascade actually occurred.
    with Session(engine) as db:
        assert db.scalars(select(Student)).all() == []
        assert db.scalars(select(StudentSession)).all() == []


def test_validation_and_csrf_do_not_echo_sensitive_values(client):
    """Ensure mutations require CSRF and errors omit submitted private data."""

    api, _ = client
    csrf = signup(api)
    assert api.patch("/api/profile", json={"fields": {"state": "MA"}}).status_code == 403
    secret = "private ethnicity value"
    response = api.patch("/api/profile", headers={"X-CSRF-Token": csrf}, json={"fields": {"ethnicity": secret * 10}})
    assert response.status_code == 422
    assert secret not in response.text
    response = api.patch("/api/profile", headers={"X-CSRF-Token": csrf}, json={"fields": {"gpa": "NaN"}})
    assert response.status_code == 422


def test_account_ownership_login_logout_and_throttle(client):
    """Keep profiles isolated and throttle repeated authentication attempts."""

    api, _ = client
    first_csrf = signup(api)
    assert api.patch("/api/profile", headers={"X-CSRF-Token": first_csrf}, json={"fields": {"school": "First College"}}).status_code == 200
    assert api.post("/api/auth/logout", headers={"X-CSRF-Token": first_csrf}).status_code == 204
    second_csrf = signup(api, "second@example.edu")
    # The second account must never inherit the first account's profile.
    assert api.get("/api/profile").json()["fields"] == {}
    assert api.patch("/api/profile", headers={"X-CSRF-Token": first_csrf}, json={"fields": {"state": "MA"}}).status_code == 403
    assert api.post("/api/auth/logout", headers={"X-CSRF-Token": second_csrf}).status_code == 204
    login = api.post("/api/auth/login", json={"email": "STUDENT@example.edu", "password": "strong password 123"})
    assert login.status_code == 200
    assert api.get("/api/profile").json()["fields"]["school"] == "First College"
    # Two successful sign-ups were already recorded for the shared test peer,
    # so eight failures fill the ten-request window.
    for _ in range(8):
        api.post("/api/auth/login", json={"email": "student@example.edu", "password": "incorrect pass 123"})
    assert api.post("/api/auth/login", json={"email": "student@example.edu", "password": "incorrect pass 123"}).status_code == 429


def test_field_registry_and_origin_check(client, monkeypatch):
    """Expose field metadata and reject browser requests from another origin."""

    api, _ = client
    registry = api.get("/api/profile-fields").json()["fields"]
    assert registry["income_range"]["sensitive"] is True
    assert registry["school"]["progressive"] is False
    monkeypatch.setenv("PATHAID_PUBLIC_ORIGIN", "https://pathaid.example")
    assert api.post("/api/auth/signup", headers={"Origin": "https://evil.example"}, json={"email": "x@example.edu", "password": "strong password 123"}).status_code == 403
