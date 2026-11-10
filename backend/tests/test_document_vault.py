"""Authenticated encryption and managed document lifecycle tests."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.database import Database
from app.document_vault import DocumentVaultError, decrypt_document, delete_document, store_document
from app.local_data import upgrade_database
from app.secrets import DOCUMENT_KEY
from conftest import FakeSecretStore


def vault(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", database_path=tmp_path / "data" / "pathaid.sqlite3")
    upgrade_database(settings)
    return Database(settings), FakeSecretStore()


def test_document_is_authenticated_ciphertext_and_requires_keychain_key(tmp_path):
    database, secrets = vault(tmp_path)
    plaintext = b"%PDF-1.7\nprivate resume content\n%%EOF"
    row = store_document(database, secrets, "resume", "resume.pdf", "application/pdf", plaintext)
    encrypted = (database.settings.data_dir / "documents" / row.encrypted_filename).read_bytes()

    assert plaintext not in encrypted
    assert row.content_hash not in encrypted.decode("latin1")
    metadata, restored = decrypt_document(database, secrets, "resume")
    assert metadata.original_name == "resume.pdf"
    assert restored == plaintext

    copied_without_key = FakeSecretStore({DOCUMENT_KEY: "A" * 43})
    with pytest.raises(DocumentVaultError, match="could not be decrypted"):
        decrypt_document(database, copied_without_key, "resume")


def test_replacement_removes_prior_ciphertext_and_delete_is_exact(tmp_path):
    database, secrets = vault(tmp_path)
    first = store_document(database, secrets, "transcript", "old.pdf", "application/pdf", b"%PDF-1.7\nold")
    first_path = database.settings.data_dir / "documents" / first.encrypted_filename
    second = store_document(database, secrets, "transcript", "new.pdf", "application/pdf", b"%PDF-1.7\nnew")
    second_path = database.settings.data_dir / "documents" / second.encrypted_filename

    assert not first_path.exists()
    assert second_path.exists()
    assert delete_document(database, "transcript") is True
    assert not second_path.exists()
    assert delete_document(database, "transcript") is False


@pytest.mark.parametrize(
    ("name", "media_type", "body"),
    [
        ("resume.txt", "text/plain", b"plain text"),
        ("resume.pdf", "application/pdf", b"not a pdf"),
        ("../", "application/pdf", b"%PDF-1.7"),
    ],
)
def test_vault_rejects_wrong_type_content_and_filename(tmp_path, name, media_type, body):
    database, secrets = vault(tmp_path)
    with pytest.raises(DocumentVaultError):
        store_document(database, secrets, "resume", name, media_type, body)
