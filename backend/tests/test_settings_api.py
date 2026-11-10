"""Security tests for local settings and encrypted backup downloads."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.local_data import BACKUP_MAGIC, restore_database, upgrade_database
from app.main import create_app
from app.secrets import DOCUMENT_KEY, EXTENSION_TOKEN, GEMINI_API_KEY
from conftest import FakeSecretStore


def configured_app(tmp_path):
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data, database_path=data / "pathaid.sqlite3",
        extension_id="abcdefghijklmnopabcdefghijklmnop",
    )
    upgrade_database(settings)
    secrets = FakeSecretStore({
        EXTENSION_TOKEN: "EXTENSION-VALUE-SECRET-CANARY",
        DOCUMENT_KEY: "DOCUMENT-VALUE-SECRET-CANARY",
    })
    return create_app(settings, secrets), settings, secrets


def test_settings_status_reports_presence_without_secret_values(tmp_path):
    app, _settings, _secrets = configured_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/settings/status")
    assert response.status_code == 200
    assert response.json()["gemini_configured"] is False
    assert response.json()["extension_token_available"] is True
    assert response.json()["document_vault_key_available"] is True
    assert response.json()["extension_id"] == "abcdefghijklmnopabcdefghijklmnop"
    assert "EXTENSION-VALUE-SECRET-CANARY" not in response.text
    assert "DOCUMENT-VALUE-SECRET-CANARY" not in response.text


def test_gemini_key_is_saved_to_keychain_boundary_not_database(tmp_path):
    app, settings, secrets = configured_app(tmp_path)
    canary = "GEMINI-SETTINGS-SECRET-CANARY"
    with TestClient(app) as client:
        response = client.put("/api/settings/gemini-key", json={"key": canary})
    assert response.json() == {"configured": True}
    assert secrets.values[GEMINI_API_KEY] == canary
    assert canary.encode() not in settings.database_path.read_bytes()
    assert canary not in response.text


def test_backup_download_is_encrypted_restorable_and_temporary(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    passphrase = "download backup passphrase"
    with TestClient(app) as client:
        response = client.post("/api/settings/backup", json={"passphrase": passphrase})
    assert response.status_code == 200
    assert response.content.startswith(BACKUP_MAGIC)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].endswith('.pathaid-backup"')
    assert list(settings.data_dir.glob(".pathaid-download-*")) == []

    archive = tmp_path / "download.pathaid-backup"
    archive.write_bytes(response.content)
    restored = tmp_path / "restored" / "pathaid.sqlite3"
    restore_database(archive, restored, passphrase=passphrase)
    assert restored.is_file()


def test_backup_download_rejects_short_passphrase_without_temp_file(tmp_path):
    app, settings, _secrets = configured_app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/settings/backup", json={"passphrase": "short"})
    assert response.status_code == 422
    assert list(settings.data_dir.glob(".pathaid-download-*")) == []
