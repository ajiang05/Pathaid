"""Safe migration, backup, restore, and reset operations for local data."""

from __future__ import annotations

import os
import json
import struct
import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile

from alembic import command
from alembic.config import Config
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .config import Settings
from .secrets import MANAGED_SECRET_NAMES, SecretStore


EXPECTED_MIGRATION = "0013_essay_bank"
REQUIRED_TABLES = {
    "alembic_version", "app_settings", "local_profile", "profile_experiences",
    "institutions", "source_scopes", "manual_leads",
    "source_scan_runs", "source_snapshots", "manual_lead_snapshots",
    "source_policy_assessments",
    "scholarships", "scholarship_versions", "extraction_activation_attempts",
    "discovery_jobs", "discovery_extraction_artifacts",
    "source_page_states",
    "saved_scholarships", "skipped_scholarships", "portal_mappings", "documents",
    "essays", "essay_uses",
}


class LocalDataError(RuntimeError):
    """Raised when local data cannot be verified or changed safely."""


BACKUP_MAGIC = b"PATHAID-BACKUP\x00"
BACKUP_FORMAT_VERSION = 1
BACKUP_HEADER_LIMIT = 16_384
BACKUP_MAX_BYTES = 2 * 1024 * 1024 * 1024
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


def _alembic_config(settings: Settings) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{settings.database_path.as_posix()}")
    return config


def upgrade_database(settings: Settings) -> None:
    """Upgrade a fresh or existing local database to the current head."""

    settings.prepare_directories()
    previous_database = os.environ.get("PATHAID_DATABASE_PATH")
    previous_data_dir = os.environ.get("PATHAID_DATA_DIR")
    os.environ["PATHAID_DATABASE_PATH"] = str(settings.database_path)
    os.environ["PATHAID_DATA_DIR"] = str(settings.data_dir)
    try:
        command.upgrade(_alembic_config(settings), "head")
        settings.database_path.chmod(0o600)
    finally:
        if previous_database is None:
            os.environ.pop("PATHAID_DATABASE_PATH", None)
        else:
            os.environ["PATHAID_DATABASE_PATH"] = previous_database
        if previous_data_dir is None:
            os.environ.pop("PATHAID_DATA_DIR", None)
        else:
            os.environ["PATHAID_DATA_DIR"] = previous_data_dir


def validate_database(path: Path) -> None:
    """Require an intact database at the expected migration and schema."""

    if not path.is_file():
        raise LocalDataError("Database file does not exist")
    try:
        source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = source.execute("SELECT version_num FROM alembic_version").fetchone()[0] if "alembic_version" in tables else None
    except (sqlite3.Error, TypeError) as error:
        raise LocalDataError("Database could not be validated") from error
    finally:
        if "source" in locals():
            source.close()
    if integrity != "ok":
        raise LocalDataError("Database integrity check failed")
    if not REQUIRED_TABLES.issubset(tables) or version != EXPECTED_MIGRATION:
        raise LocalDataError("Database migration is not current")


def backup_database(source_path: Path, destination: Path, *, passphrase: str) -> Path:
    """Create a consistent, passphrase-encrypted, versioned SQLite backup."""

    validate_database(source_path)
    _validate_backup_passphrase(passphrase)
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise LocalDataError("Backup destination already exists")
    with NamedTemporaryFile(prefix=".pathaid-backup-", suffix=".sqlite3", dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    source = sqlite3.connect(str(source_path))
    target = sqlite3.connect(str(temporary_path))
    try:
        source.backup(target)
        target.close()
        validate_database(temporary_path)
        plaintext = temporary_path.read_bytes()
        salt = os.urandom(16)
        nonce = os.urandom(12)
        header = json.dumps({
            "format": "pathaid-encrypted-sqlite",
            "format_version": BACKUP_FORMAT_VERSION,
            "database_migration": EXPECTED_MIGRATION,
            "cipher": "AES-256-GCM",
            "kdf": {"name": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P, "salt": salt.hex()},
            "nonce": nonce.hex(),
            "excludes": [
                "macOS Keychain secrets", "document ciphertext", "browser data",
                "portal credentials", "cache files",
            ],
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        prefix = BACKUP_MAGIC + struct.pack(">I", len(header)) + header
        ciphertext = AESGCM(_derive_backup_key(passphrase, salt)).encrypt(nonce, plaintext, prefix)
        with destination.open("xb") as output:
            output.write(prefix)
            output.write(ciphertext)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        source.close()
        try:
            target.close()
        except Exception:
            pass
        temporary_path.unlink(missing_ok=True)
    destination.chmod(0o600)
    return destination


def restore_database(backup_path: Path, destination: Path, *, passphrase: str) -> None:
    """Authenticate, validate, and atomically restore an encrypted backup."""

    backup_path = backup_path.expanduser().resolve()
    destination = destination.expanduser().resolve()
    _validate_backup_passphrase(passphrase)
    if not backup_path.is_file():
        raise LocalDataError("Backup file does not exist")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with NamedTemporaryFile(prefix=".pathaid-decrypted-", suffix=".sqlite3", dir=destination.parent, delete=False) as decrypted:
        decrypted_path = Path(decrypted.name)
    with NamedTemporaryFile(prefix=".pathaid-restore-", suffix=".sqlite3", dir=destination.parent, delete=False) as replacement:
        replacement_path = Path(replacement.name)
    try:
        decrypted_path.write_bytes(_decrypt_backup(backup_path, passphrase))
        decrypted_path.chmod(0o600)
        validate_database(decrypted_path)
        source = sqlite3.connect(str(decrypted_path))
        target = sqlite3.connect(str(replacement_path))
        source.backup(target)
        target.close()
        source.close()
        validate_database(replacement_path)
        replacement_path.chmod(0o600)
        os.replace(replacement_path, destination)
        for suffix in ("-wal", "-shm"):
            Path(f"{destination}{suffix}").unlink(missing_ok=True)
    finally:
        for connection_name in ("source", "target"):
            connection = locals().get(connection_name)
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
        decrypted_path.unlink(missing_ok=True)
        replacement_path.unlink(missing_ok=True)


def backup_metadata(backup_path: Path) -> dict:
    """Read authenticated-independent format metadata without decrypting data."""

    _prefix, header, _ciphertext = _read_backup(backup_path.expanduser().resolve())
    return {
        "format": header["format"],
        "format_version": header["format_version"],
        "database_migration": header["database_migration"],
        "cipher": header["cipher"],
        "excludes": list(header["excludes"]),
    }


def _decrypt_backup(backup_path: Path, passphrase: str) -> bytes:
    prefix, header, ciphertext = _read_backup(backup_path)
    try:
        salt = bytes.fromhex(header["kdf"]["salt"])
        nonce = bytes.fromhex(header["nonce"])
        return AESGCM(_derive_backup_key(passphrase, salt)).decrypt(nonce, ciphertext, prefix)
    except InvalidTag as error:
        raise LocalDataError("Backup passphrase is incorrect or the backup was tampered with") from error
    except (KeyError, TypeError, ValueError) as error:
        raise LocalDataError("Backup header is invalid") from error


def _read_backup(path: Path) -> tuple[bytes, dict, bytes]:
    if not path.is_file():
        raise LocalDataError("Backup file does not exist")
    size = path.stat().st_size
    if size < len(BACKUP_MAGIC) + 4 + 16 or size > BACKUP_MAX_BYTES:
        raise LocalDataError("Backup file size is invalid")
    with path.open("rb") as source:
        magic = source.read(len(BACKUP_MAGIC))
        if magic != BACKUP_MAGIC:
            raise LocalDataError("Backup format is not recognized")
        raw_length = source.read(4)
        if len(raw_length) != 4:
            raise LocalDataError("Backup header is incomplete")
        header_length = struct.unpack(">I", raw_length)[0]
        if header_length < 2 or header_length > BACKUP_HEADER_LIMIT:
            raise LocalDataError("Backup header size is invalid")
        header_bytes = source.read(header_length)
        ciphertext = source.read()
    try:
        header = json.loads(header_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalDataError("Backup header is invalid") from error
    if (
        not isinstance(header, dict)
        or header.get("format") != "pathaid-encrypted-sqlite"
        or header.get("format_version") != BACKUP_FORMAT_VERSION
        or header.get("database_migration") != EXPECTED_MIGRATION
        or header.get("cipher") != "AES-256-GCM"
        or header.get("kdf", {}).get("name") != "scrypt"
        or header.get("kdf", {}).get("n") != SCRYPT_N
        or header.get("kdf", {}).get("r") != SCRYPT_R
        or header.get("kdf", {}).get("p") != SCRYPT_P
        or not isinstance(header.get("excludes"), list)
    ):
        raise LocalDataError("Backup version or schema is incompatible")
    prefix = BACKUP_MAGIC + raw_length + header_bytes
    return prefix, header, ciphertext


def _derive_backup_key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P).derive(passphrase.encode("utf-8"))


def _validate_backup_passphrase(passphrase: str) -> None:
    if len(passphrase) < 12:
        raise LocalDataError("Backup passphrase must be at least 12 characters")


def reset_local_data(settings: Settings, store: SecretStore, *, confirmed: bool) -> None:
    """Remove only resolved PathAid data and managed secrets after confirmation."""

    if not confirmed:
        raise LocalDataError("Reset requires explicit confirmation")
    data_dir = settings.data_dir.resolve()
    database = settings.database_path.resolve()
    if data_dir not in database.parents:
        raise LocalDataError("Refusing to reset a database outside the PathAid data directory")
    for suffix in ("", "-wal", "-shm"):
        Path(f"{database}{suffix}").unlink(missing_ok=True)
    document_dir = (data_dir / "documents").resolve()
    if document_dir.parent != data_dir:
        raise LocalDataError("Refusing to reset documents outside the PathAid data directory")
    if document_dir.is_dir():
        for encrypted_file in document_dir.glob("*.vault"):
            if encrypted_file.is_file() and encrypted_file.resolve().parent == document_dir:
                encrypted_file.unlink()
        try:
            document_dir.rmdir()
        except OSError:
            # Preserve any unexpected file rather than broadening deletion.
            pass
    for name in MANAGED_SECRET_NAMES:
        store.delete(name)
