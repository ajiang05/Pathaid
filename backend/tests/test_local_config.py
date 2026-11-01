"""Tests for local paths, SQLite pragmas, and the singleton schema."""

from __future__ import annotations

import sqlite3
import stat

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import Settings, default_data_dir
from app.database import Database
from app.local_data import upgrade_database
from app.models import LocalProfile
from app.__main__ import main as run_local_api


def settings_for(tmp_path, **overrides) -> Settings:
    data_dir = tmp_path / "PathAid Data"
    values = {"data_dir": data_dir, "database_path": data_dir / "pathaid.sqlite3"}
    values.update(overrides)
    return Settings(**values)


def test_default_macos_path_and_explicit_override(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.sys.platform", "darwin")
    monkeypatch.setattr("app.config.Path.home", classmethod(lambda _cls: tmp_path))
    monkeypatch.delenv("PATHAID_DATA_DIR", raising=False)
    assert default_data_dir() == (tmp_path / "Library" / "Application Support" / "PathAid").resolve()

    override = tmp_path / "explicit"
    monkeypatch.setenv("PATHAID_DATA_DIR", str(override))
    assert default_data_dir() == override.resolve()


def test_settings_reject_nonpositive_busy_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("PATHAID_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PATHAID_SQLITE_BUSY_TIMEOUT_MS", "0")
    with pytest.raises(ValueError, match="must be positive"):
        Settings.from_env()


def test_settings_reject_remote_web_origin_and_invalid_extension_id(tmp_path):
    with pytest.raises(ValueError, match="local HTTP origin"):
        Settings(data_dir=tmp_path, database_path=tmp_path / "db.sqlite3", web_origin="https://remote.example")
    with pytest.raises(ValueError, match="Chrome extension ID"):
        Settings(data_dir=tmp_path, database_path=tmp_path / "db.sqlite3", extension_id="not-valid")


def test_legacy_database_url_cannot_select_postgres(monkeypatch, tmp_path):
    monkeypatch.setenv("PATHAID_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql://should-not-be-used")
    settings = Settings.from_env()
    assert settings.database_path == tmp_path.resolve() / "pathaid.sqlite3"


def test_native_entrypoint_hardcodes_loopback(monkeypatch):
    observed = {}
    monkeypatch.setattr("app.__main__.uvicorn.run", lambda target, **options: observed.update(target=target, **options))
    monkeypatch.setenv("PATHAID_API_PORT", "8123")
    run_local_api()
    assert observed == {
        "target": "app.main:app",
        "host": "127.0.0.1",
        "port": 8123,
        "access_log": False,
    }


def test_fresh_upgrade_is_idempotent_and_creates_one_profile(tmp_path):
    settings = settings_for(tmp_path)
    upgrade_database(settings)
    upgrade_database(settings)

    database = Database(settings)
    with database.sessions() as session:
        profile = session.get(LocalProfile, 1)
        assert profile is not None
        assert profile.data == {}
        assert profile.schema_version == 1
        session.add(LocalProfile(id=2, data={}))
        with pytest.raises(IntegrityError):
            session.commit()
    database.close()


def test_sqlite_connections_enforce_foundation_pragmas(tmp_path):
    settings = settings_for(tmp_path, sqlite_busy_timeout_ms=7_500)
    upgrade_database(settings)
    database = Database(settings)
    with database.engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert str(connection.scalar(text("PRAGMA journal_mode"))).casefold() == "wal"
        assert connection.scalar(text("PRAGMA busy_timeout")) == 7_500
    database.close()

    raw = sqlite3.connect(settings.database_path)
    assert raw.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    raw.close()
    assert stat.S_IMODE(settings.database_path.stat().st_mode) == 0o600
