"""SQLAlchemy models for student accounts, sessions, and rate limiting."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    """Return a random, non-sequential public identifier for a student."""

    return str(uuid4())


class Student(Base):
    """An authenticated student and the profile they chose to save."""

    __tablename__ = "students"

    # UUID strings avoid exposing predictable account counts through IDs.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # The API normalizes email casing before storage; the unique constraint
    # prevents two accounts from sharing the same login identifier.
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    # Only a slow password hash is stored. The original password is discarded.
    password_hash: Mapped[str] = mapped_column(String(256))
    # Profile answers are optional and registry-driven, so JSON allows the set
    # of saved answers to grow without a database column for every question.
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    # Consent starts false and must be explicitly enabled by the student.
    ai_opt_in: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Deleting an account also deletes its ORM-managed login sessions.
    sessions: Mapped[list["StudentSession"]] = relationship(cascade="all, delete-orphan")


class StudentSession(Base):
    """A revocable login session linked to one student account."""

    __tablename__ = "student_sessions"

    # Tokens are sent to the browser, while only their hashes are stored here.
    # A database leak therefore does not directly reveal usable session tokens.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    # Sessions become invalid after this timestamp even if the browser still
    # has the corresponding cookie.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuthAttempt(Base):
    """A recent auth request used to enforce a shared database rate limit."""

    __tablename__ = "auth_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # This is a SHA-256 digest of the peer address, not the raw IP address.
    address: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
