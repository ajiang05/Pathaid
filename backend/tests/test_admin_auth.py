"""API tests for deployment-configured administrator authentication."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, password_hash
from app.models import AdminAuthAttempt, AdminSession


ADMIN_EMAIL = "admin@pathaid.example"
ADMIN_PASSWORD = "strong admin password 123"


@pytest.fixture
def client(monkeypatch):
    """Configure one administrator and an isolated application database."""

    monkeypatch.setenv("PATHAID_ADMIN_EMAIL", ADMIN_EMAIL)
    monkeypatch.setenv("PATHAID_ADMIN_PASSWORD_HASH", password_hash(ADMIN_PASSWORD))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def login(api):
    """Authenticate and return the issued CSRF token."""

    response = api.post("/api/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return response


def test_login_session_rotation_and_logout(client):
    """Exercise the complete revocable admin session lifecycle."""

    api, engine = client
    response = login(api)
    csrf = response.json()["csrf_token"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "path=/api/admin" in cookie

    refreshed = api.get("/api/admin/auth/session")
    assert refreshed.status_code == 200
    fresh_csrf = refreshed.json()["csrf_token"]
    assert fresh_csrf != csrf
    assert api.post("/api/admin/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 403
    assert api.post("/api/admin/auth/logout", headers={"X-CSRF-Token": fresh_csrf}).status_code == 204
    assert api.get("/api/admin/auth/session").status_code == 401
    with Session(engine) as db:
        assert db.scalars(select(AdminSession)).all() == []


def test_invalid_credentials_are_generic_and_throttled(client):
    """Do not reveal which credential failed and stop repeated attempts."""

    api, engine = client
    for _ in range(5):
        response = api.post(
            "/api/admin/auth/login",
            json={"email": "unknown@example.edu", "password": "incorrect"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"
        assert "unknown@example.edu" not in response.text
    assert api.post("/api/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).status_code == 429
    with Session(engine) as db:
        assert len(db.scalars(select(AdminAuthAttempt)).all()) == 5


def test_missing_configuration_fails_without_creating_session(client, monkeypatch):
    """An absent deployment secret is an explicit non-authentication outcome."""

    api, engine = client
    monkeypatch.delenv("PATHAID_ADMIN_PASSWORD_HASH")
    response = api.post("/api/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert response.status_code == 503
    with Session(engine) as db:
        assert db.scalars(select(AdminSession)).all() == []


def test_admin_origin_and_csrf_are_enforced(client, monkeypatch):
    """Cross-origin requests and missing CSRF tokens cannot mutate admin state."""

    api, _ = client
    monkeypatch.setenv("PATHAID_PUBLIC_ORIGIN", "https://pathaid.example")
    assert api.post(
        "/api/admin/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    ).status_code == 403
    response = api.post(
        "/api/admin/auth/login",
        headers={"Origin": "https://pathaid.example"},
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    assert api.post("/api/admin/auth/logout").status_code == 403


def test_student_session_does_not_authorize_admin_routes(client):
    """Student and administrator cookies remain separate security boundaries."""

    api, _ = client
    assert api.post(
        "/api/auth/signup",
        json={"email": "student@example.edu", "password": "strong password 123"},
    ).status_code == 201
    assert api.get("/api/admin/auth/session").status_code == 401
