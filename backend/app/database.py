"""Database connection and request-scoped SQLAlchemy session setup."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Base class inherited by every SQLAlchemy database model."""

    pass


def make_engine():
    """Create an engine for PostgreSQL in deployment or SQLite locally."""

    # DATABASE_URL keeps credentials and environment-specific connection
    # details out of source control. SQLite makes initial local setup easier.
    url = os.environ.get("DATABASE_URL", "sqlite:///./pathaid.db")
    # SQLite normally restricts a connection to its creating thread. FastAPI
    # may execute a request in another thread, so local SQLite disables that
    # restriction. PostgreSQL does not use this option.
    options = {"check_same_thread": False} if url.startswith("sqlite:") else {}
    return create_engine(url, connect_args=options)


engine = make_engine()
# expire_on_commit=False lets endpoint code serialize saved objects after a
# commit without SQLAlchemy immediately fetching all their values again.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    """Give one database session to a request and close it afterward."""

    # FastAPI treats this generator as a dependency. Code before yield runs
    # before the endpoint, and the context manager closes the session after it.
    with SessionLocal() as db:
        yield db
