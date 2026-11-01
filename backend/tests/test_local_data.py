"""Backup, restore, reset, and secret-lifecycle tests."""

from __future__ import annotations

import sqlite3

import pytest

from app.config import Settings
from app.local_data import LocalDataError, backup_database, reset_local_data, restore_database, upgrade_database, validate_database
from app.secrets import (
    DOCUMENT_KEY,
    EXTENSION_TOKEN,
    GEMINI_API_KEY,
    KeychainSecretStore,
    get_or_create_document_key,
    get_or_create_extension_token,
)
from conftest import FakeSecretStore


def settings_for(tmp_path) -> Settings:
    data = tmp_path / "data"
    return Settings(data_dir=data, database_path=data / "pathaid.sqlite3")


def profile_data(path):
    connection = sqlite3.connect(path)
    raw = connection.execute("SELECT data FROM local_profile WHERE id = 1").fetchone()[0]
    connection.close()
    return raw


def test_extension_and_document_secrets_are_created_once():
    store = FakeSecretStore()
    first_token = get_or_create_extension_token(store)
    first_key = get_or_create_document_key(store)
    assert get_or_create_extension_token(store) == first_token
    assert get_or_create_document_key(store) == first_key
    assert len(first_token) >= 48
    assert len(first_key) >= 32
    assert store.values[EXTENSION_TOKEN] == first_token
    assert store.values[DOCUMENT_KEY] == first_key


def test_keychain_adapter_uses_service_scoped_password_api(monkeypatch):
    class MissingPassword(Exception):
        pass

    class FakeKeyring:
        class errors:
            PasswordDeleteError = MissingPassword

        def __init__(self):
            self.values = {}

        def get_password(self, service, name):
            return self.values.get((service, name))

        def set_password(self, service, name, value):
            self.values[(service, name)] = value

        def delete_password(self, service, name):
            if (service, name) not in self.values:
                raise MissingPassword
            del self.values[(service, name)]

    backend = FakeKeyring()
    monkeypatch.setattr(KeychainSecretStore, "_keyring", staticmethod(lambda: backend))
    store = KeychainSecretStore("com.pathaid.test")
    assert store.get(GEMINI_API_KEY) is None
    store.set(GEMINI_API_KEY, "secret")
    assert store.get(GEMINI_API_KEY) == "secret"
    store.delete(GEMINI_API_KEY)
    store.delete(GEMINI_API_KEY)
    with pytest.raises(ValueError, match="cannot be empty"):
        store.set(GEMINI_API_KEY, "")


def test_backup_and_restore_round_trip(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    connection = sqlite3.connect(settings.database_path)
    connection.execute('UPDATE local_profile SET data = ? WHERE id = 1', ('{"school":"UMass"}',))
    connection.commit()
    connection.close()

    backup = tmp_path / "backups" / "pathaid.sqlite3"
    backup_database(settings.database_path, backup)
    connection = sqlite3.connect(settings.database_path)
    connection.execute('UPDATE local_profile SET data = ? WHERE id = 1', ('{"school":"Changed"}',))
    connection.commit()
    connection.close()

    restore_database(backup, settings.database_path)
    validate_database(settings.database_path)
    assert profile_data(settings.database_path) == '{"school":"UMass"}'


def test_backup_rejects_overwrite_and_restore_rejects_corruption(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    destination = tmp_path / "backup.sqlite3"
    backup_database(settings.database_path, destination)
    with pytest.raises(LocalDataError, match="already exists"):
        backup_database(settings.database_path, destination)

    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a database")
    before = settings.database_path.read_bytes()
    with pytest.raises(LocalDataError):
        restore_database(corrupt, settings.database_path)
    assert settings.database_path.read_bytes() == before


def test_reset_requires_confirmation_and_deletes_only_managed_targets(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    unrelated = settings.data_dir / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    store = FakeSecretStore({GEMINI_API_KEY: "gemini", EXTENSION_TOKEN: "token", DOCUMENT_KEY: "key", "other": "keep"})

    with pytest.raises(LocalDataError, match="confirmation"):
        reset_local_data(settings, store, confirmed=False)
    assert settings.database_path.exists()

    reset_local_data(settings, store, confirmed=True)
    assert not settings.database_path.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert store.values == {"other": "keep"}
    assert set(store.deleted) == {GEMINI_API_KEY, EXTENSION_TOKEN, DOCUMENT_KEY}


def test_reset_refuses_database_outside_data_directory(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", database_path=tmp_path / "outside.sqlite3")
    settings.database_path.write_bytes(b"do not delete")
    with pytest.raises(LocalDataError, match="outside"):
        reset_local_data(settings, FakeSecretStore(), confirmed=True)
    assert settings.database_path.read_bytes() == b"do not delete"
