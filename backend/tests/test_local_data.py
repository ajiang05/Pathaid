"""Backup, restore, reset, and secret-lifecycle tests."""

from __future__ import annotations

import sqlite3
import struct

import pytest

from app.config import Settings
from app.local_data import BACKUP_MAGIC, LocalDataError, backup_database, backup_metadata, reset_local_data, restore_database, upgrade_database, validate_database
from app.local_admin import copy_extension_token_to_clipboard
from app.secrets import (
    DOCUMENT_KEY,
    EXTENSION_TOKEN,
    GEMINI_API_KEY,
    KeychainSecretStore,
    get_or_create_document_key,
    get_or_create_extension_token,
)
from conftest import FakeSecretStore


PASSPHRASE = "correct horse battery staple"


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


def test_extension_token_can_be_copied_without_being_returned_or_logged():
    store = FakeSecretStore({EXTENSION_TOKEN: "private-extension-token"})
    captured = {}

    def runner(command, **kwargs):
        captured.update(command=command, **kwargs)

    assert copy_extension_token_to_clipboard(store, runner=runner) is None
    assert captured == {
        "command": ["pbcopy"], "input": "private-extension-token",
        "text": True, "check": True,
    }


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

    backup = tmp_path / "backups" / "pathaid.pathaid-backup"
    backup_database(settings.database_path, backup, passphrase=PASSPHRASE)
    assert backup.read_bytes().startswith(BACKUP_MAGIC)
    assert not backup.read_bytes().startswith(b"SQLite format 3")
    assert backup_metadata(backup) == {
        "format": "pathaid-encrypted-sqlite",
        "format_version": 1,
        "database_migration": "0013_essay_bank",
        "cipher": "AES-256-GCM",
        "excludes": [
            "macOS Keychain secrets", "document ciphertext", "browser data",
            "portal credentials", "cache files",
        ],
    }
    connection = sqlite3.connect(settings.database_path)
    connection.execute('UPDATE local_profile SET data = ? WHERE id = 1', ('{"school":"Changed"}',))
    connection.commit()
    connection.close()

    restore_database(backup, settings.database_path, passphrase=PASSPHRASE)
    validate_database(settings.database_path)
    assert profile_data(settings.database_path) == '{"school":"UMass"}'


def test_backup_rejects_overwrite_and_restore_rejects_corruption(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    destination = tmp_path / "backup.pathaid-backup"
    backup_database(settings.database_path, destination, passphrase=PASSPHRASE)
    with pytest.raises(LocalDataError, match="already exists"):
        backup_database(settings.database_path, destination, passphrase=PASSPHRASE)

    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a database")
    before = settings.database_path.read_bytes()
    with pytest.raises(LocalDataError):
        restore_database(corrupt, settings.database_path, passphrase=PASSPHRASE)
    assert settings.database_path.read_bytes() == before


def test_wrong_passphrase_and_tampering_never_change_live_database(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    backup = tmp_path / "backup.pathaid-backup"
    backup_database(settings.database_path, backup, passphrase=PASSPHRASE)
    before = settings.database_path.read_bytes()

    with pytest.raises(LocalDataError, match="passphrase|tampered"):
        restore_database(backup, settings.database_path, passphrase="incorrect passphrase value")
    assert settings.database_path.read_bytes() == before

    damaged = bytearray(backup.read_bytes())
    damaged[-1] ^= 1
    backup.write_bytes(damaged)
    with pytest.raises(LocalDataError, match="passphrase|tampered"):
        restore_database(backup, settings.database_path, passphrase=PASSPHRASE)
    assert settings.database_path.read_bytes() == before


def test_incompatible_backup_fails_before_replacing_database(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    backup = tmp_path / "backup.pathaid-backup"
    backup_database(settings.database_path, backup, passphrase=PASSPHRASE)
    raw = bytearray(backup.read_bytes())
    header_start = len(BACKUP_MAGIC) + 4
    header_size = struct.unpack(">I", raw[len(BACKUP_MAGIC):header_start])[0]
    header = raw[header_start:header_start + header_size]
    version_index = header.index(b'"format_version":1') + len(b'"format_version":')
    header[version_index] = ord("9")
    raw[header_start:header_start + header_size] = header
    backup.write_bytes(raw)
    before = settings.database_path.read_bytes()

    with pytest.raises(LocalDataError, match="incompatible"):
        restore_database(backup, settings.database_path, passphrase=PASSPHRASE)
    assert settings.database_path.read_bytes() == before


def test_backup_excludes_keychain_and_managed_document_bytes(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    document_dir = settings.data_dir / "documents"
    document_dir.mkdir()
    document_canary = b"RESUME-BYTES-MUST-NOT-BE-BACKED-UP"
    (document_dir / "resume.vault").write_bytes(document_canary)
    secret_canaries = [b"GEMINI-SECRET-CANARY", b"EXTENSION-SECRET-CANARY", b"DOCUMENT-KEY-CANARY"]
    store = FakeSecretStore(dict(zip(
        (GEMINI_API_KEY, EXTENSION_TOKEN, DOCUMENT_KEY),
        (item.decode() for item in secret_canaries), strict=True,
    )))
    backup = tmp_path / "backup.pathaid-backup"

    backup_database(settings.database_path, backup, passphrase=PASSPHRASE)
    raw = backup.read_bytes()
    assert document_canary not in raw
    assert all(canary not in raw for canary in secret_canaries)
    assert store.values[GEMINI_API_KEY] == "GEMINI-SECRET-CANARY"

    restored = tmp_path / "restored" / "pathaid.sqlite3"
    restore_database(backup, restored, passphrase=PASSPHRASE)
    assert restored.is_file()
    assert not (restored.parent / "documents").exists()


def test_backup_requires_strong_nonempty_passphrase(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    with pytest.raises(LocalDataError, match="12 characters"):
        backup_database(settings.database_path, tmp_path / "backup", passphrase="short")


def test_reset_requires_confirmation_and_deletes_only_managed_targets(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    unrelated = settings.data_dir / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    document_dir = settings.data_dir / "documents"
    document_dir.mkdir()
    ciphertext = document_dir / "resume-fixture.vault"
    ciphertext.write_bytes(b"encrypted")
    preserved = document_dir / "unexpected.txt"
    preserved.write_text("keep", encoding="utf-8")
    store = FakeSecretStore({GEMINI_API_KEY: "gemini", EXTENSION_TOKEN: "token", DOCUMENT_KEY: "key", "other": "keep"})

    with pytest.raises(LocalDataError, match="confirmation"):
        reset_local_data(settings, store, confirmed=False)
    assert settings.database_path.exists()

    reset_local_data(settings, store, confirmed=True)
    assert not settings.database_path.exists()
    assert not ciphertext.exists()
    assert preserved.read_text(encoding="utf-8") == "keep"
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert store.values == {"other": "keep"}
    assert set(store.deleted) == {GEMINI_API_KEY, EXTENSION_TOKEN, DOCUMENT_KEY}


def test_reset_refuses_database_outside_data_directory(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", database_path=tmp_path / "outside.sqlite3")
    settings.database_path.write_bytes(b"do not delete")
    with pytest.raises(LocalDataError, match="outside"):
        reset_local_data(settings, FakeSecretStore(), confirmed=True)
    assert settings.database_path.read_bytes() == b"do not delete"
