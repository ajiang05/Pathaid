"""Authenticated local encryption for the current résumé and transcript."""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .database import Database
from .models import Document
from .secrets import SecretStore, SecretStoreError, get_or_create_document_key


MAGIC = b"PATHAID-DOC-1\0"
NONCE_SIZE = 12
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
DOCUMENT_TYPES = {"resume", "transcript"}


class DocumentVaultError(RuntimeError):
    """Value-free vault failure safe to show in the local interface."""


@dataclass(frozen=True)
class DocumentMetadata:
    document_type: str
    original_name: str
    media_type: str
    size_bytes: int
    content_hash: str
    updated_at: object


def _key(store: SecretStore) -> bytes:
    try:
        encoded = get_or_create_document_key(store)
        key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (SecretStoreError, ValueError) as error:
        raise DocumentVaultError("The document encryption key is unavailable.") from error
    if len(key) != 32:
        raise DocumentVaultError("The document encryption key is invalid.")
    return key


def _directory(root: Path) -> Path:
    directory = root / "documents"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    return directory


def _safe_name(value: str) -> str:
    name = Path(value).name.strip()
    if not name or name in {".", ".."} or len(name) > 240 or any(ord(character) < 32 for character in name):
        raise DocumentVaultError("The document filename is invalid.")
    return name


def store_document(
    database: Database,
    store: SecretStore,
    document_type: str,
    original_name: str,
    media_type: str,
    plaintext: bytes,
) -> Document:
    """Encrypt a validated PDF and atomically make it the current copy."""

    if document_type not in DOCUMENT_TYPES:
        raise DocumentVaultError("The document type is unsupported.")
    if media_type != "application/pdf" or not plaintext.startswith(b"%PDF-"):
        raise DocumentVaultError("PathAid accepts PDF documents only.")
    if not 1 <= len(plaintext) <= MAX_DOCUMENT_BYTES:
        raise DocumentVaultError("The document must be no larger than 20 MB.")
    name = _safe_name(original_name)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(_key(store)).encrypt(nonce, plaintext, document_type.encode("ascii"))
    directory = _directory(database.settings.data_dir)
    encrypted_filename = f"{document_type}-{uuid4()}.vault"
    final_path = directory / encrypted_filename
    with NamedTemporaryFile(prefix=".pathaid-document-", dir=directory, delete=False) as temporary:
        temporary.write(MAGIC + nonce + ciphertext)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    temporary_path.chmod(0o600)
    os.replace(temporary_path, final_path)
    previous_filename = None
    try:
        with database.sessions.begin() as db:
            row = db.get(Document, document_type)
            if row is None:
                row = Document(
                    document_type=document_type, original_name=name, media_type=media_type,
                    size_bytes=len(plaintext), content_hash=hashlib.sha256(plaintext).hexdigest(),
                    encrypted_filename=encrypted_filename,
                )
                db.add(row)
            else:
                previous_filename = row.encrypted_filename
                row.original_name = name
                row.media_type = media_type
                row.size_bytes = len(plaintext)
                row.content_hash = hashlib.sha256(plaintext).hexdigest()
                row.encrypted_filename = encrypted_filename
            db.flush()
            result = row
    except Exception:
        final_path.unlink(missing_ok=True)
        raise
    if previous_filename:
        (directory / previous_filename).unlink(missing_ok=True)
    return result


def decrypt_document(database: Database, store: SecretStore, document_type: str) -> tuple[DocumentMetadata, bytes]:
    """Authenticate and decrypt one current document entirely in memory."""

    with database.sessions() as db:
        row = db.get(Document, document_type)
        if row is None:
            raise DocumentVaultError("The requested document is not stored.")
        metadata = DocumentMetadata(
            row.document_type, row.original_name, row.media_type,
            row.size_bytes, row.content_hash, row.updated_at,
        )
        encrypted_filename = row.encrypted_filename
    path = _directory(database.settings.data_dir) / encrypted_filename
    try:
        payload = path.read_bytes()
        if not payload.startswith(MAGIC) or len(payload) <= len(MAGIC) + NONCE_SIZE:
            raise DocumentVaultError("The encrypted document is invalid.")
        offset = len(MAGIC)
        plaintext = AESGCM(_key(store)).decrypt(
            payload[offset:offset + NONCE_SIZE], payload[offset + NONCE_SIZE:],
            document_type.encode("ascii"),
        )
    except (OSError, InvalidTag) as error:
        raise DocumentVaultError("The document could not be decrypted.") from error
    if hashlib.sha256(plaintext).hexdigest() != metadata.content_hash:
        raise DocumentVaultError("The document integrity check failed.")
    return metadata, plaintext


def delete_document(database: Database, document_type: str) -> bool:
    """Delete current metadata and its exact managed ciphertext file."""

    with database.sessions.begin() as db:
        row = db.get(Document, document_type)
        if row is None:
            return False
        encrypted_filename = row.encrypted_filename
        db.delete(row)
    (_directory(database.settings.data_dir) / encrypted_filename).unlink(missing_ok=True)
    return True
