"""SQLite engine and request-scoped session setup for local PathAid."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings


class Base(DeclarativeBase):
    """Base class inherited by local SQLAlchemy models."""


def sqlite_url(path: Path) -> str:
    """Return an absolute pysqlite URL for a local database file."""

    return f"sqlite+pysqlite:///{path.as_posix()}"


def make_engine(settings: Settings) -> Engine:
    """Create the only supported runtime engine and configure safe pragmas."""

    engine = create_engine(
        sqlite_url(settings.database_path),
        connect_args={"check_same_thread": False, "timeout": settings.sqlite_busy_timeout_ms / 1000},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
        try:
            settings.database_path.chmod(0o600)
        except OSError:
            pass

    return engine


class Database:
    """Own an engine and session factory without import-time global databases."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = make_engine(settings)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def session(self) -> Iterator[Session]:
        """Yield one request session and always close it."""

        with self.sessions() as db:
            yield db

    def close(self) -> None:
        """Release pooled file handles before restore or reset."""

        self.engine.dispose()
