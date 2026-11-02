"""Safe migration, backup, restore, and reset operations for local data."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile

from alembic import command
from alembic.config import Config

from .config import Settings
from .secrets import MANAGED_SECRET_NAMES, SecretStore


EXPECTED_MIGRATION = "0007_deterministic_activation"
REQUIRED_TABLES = {
    "alembic_version", "app_settings", "local_profile", "profile_experiences",
    "institutions", "source_scopes", "manual_leads",
    "source_scan_runs", "source_snapshots", "manual_lead_snapshots",
    "source_policy_assessments",
    "scholarships", "scholarship_versions", "extraction_activation_attempts",
}


class LocalDataError(RuntimeError):
    """Raised when local data cannot be verified or changed safely."""


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


def backup_database(source_path: Path, destination: Path) -> Path:
    """Create a consistent SQLite backup without copying WAL files directly."""

    validate_database(source_path)
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise LocalDataError("Backup destination already exists")
    source = sqlite3.connect(str(source_path))
    target = sqlite3.connect(str(destination))
    try:
        source.backup(target)
    except Exception:
        target.close()
        destination.unlink(missing_ok=True)
        raise
    finally:
        source.close()
        if "target" in locals():
            target.close()
    destination.chmod(0o600)
    validate_database(destination)
    return destination


def restore_database(backup_path: Path, destination: Path) -> None:
    """Validate and atomically restore a backup over a stopped database."""

    backup_path = backup_path.expanduser().resolve()
    destination = destination.expanduser().resolve()
    validate_database(backup_path)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with NamedTemporaryFile(prefix=".pathaid-restore-", suffix=".sqlite3", dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    source = sqlite3.connect(str(backup_path))
    target = sqlite3.connect(str(temporary_path))
    try:
        source.backup(target)
        target.close()
        validate_database(temporary_path)
        temporary_path.chmod(0o600)
        os.replace(temporary_path, destination)
        for suffix in ("-wal", "-shm"):
            Path(f"{destination}{suffix}").unlink(missing_ok=True)
    finally:
        source.close()
        try:
            target.close()
        except Exception:
            pass
        temporary_path.unlink(missing_ok=True)


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
    for name in MANAGED_SECRET_NAMES:
        store.delete(name)
