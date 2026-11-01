"""Security and migration tests for the loopback local API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.local_data import upgrade_database
from app.main import create_app
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
    paths = {route.path for route in app.routes}
    assert not any(path.startswith("/api/auth") for path in paths)
    assert not any(path.startswith("/api/admin") for path in paths)
    assert "/api/programs" not in paths
    assert "/api/evaluate" not in paths
