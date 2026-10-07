"""SQLAlchemy models for student accounts and the reviewed program catalog."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Table, Text, Column, func
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


class AdminSession(Base):
    """Revocable session for the single deployment-configured administrator."""

    __tablename__ = "admin_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_email: Mapped[str] = mapped_column(String(254), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdminAuthAttempt(Base):
    """Privacy-reduced admin login attempt used for database-backed throttling."""

    __tablename__ = "admin_auth_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


# A revision can cite several source snapshots, and a snapshot can support
# several revisions. The join table preserves that many-to-many relationship.
revision_sources = Table(
    "revision_sources",
    Base.metadata,
    Column("revision_id", ForeignKey("program_revisions.id", ondelete="CASCADE"), primary_key=True),
    Column("source_snapshot_id", ForeignKey("source_snapshots.id", ondelete="RESTRICT"), primary_key=True),
)


class Program(Base):
    """Stable identity for an opportunity across all of its revisions."""

    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # This stores the approved revision selected for public reads. The revision
    # itself owns the foreign key back to this program, avoiding a circular
    # database dependency while publication code validates ownership.
    current_published_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revisions: Mapped[list["ProgramRevision"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        foreign_keys="ProgramRevision.program_id",
    )


class SourceSnapshot(Base):
    """Immutable source text and provenance captured before extraction."""

    __tablename__ = "source_snapshots"
    __table_args__ = (
        CheckConstraint("acquisition_method IN ('webpage', 'pasted_text')", name="ck_source_acquisition_method"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # source_url is the administrator-submitted address; final_url records the
    # destination after validated redirects. Older snapshots may lack the new
    # provenance fields added after the initial catalog migration.
    source_url: Mapped[str] = mapped_column(String(2048))
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    acquisition_method: Mapped[str] = mapped_column(String(20))
    media_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_byte_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redirect_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_text: Mapped[str] = mapped_column(Text)
    revisions: Mapped[list["ProgramRevision"]] = relationship(secondary=revision_sources, back_populates="sources")


class ProgramRevision(Base):
    """A draft, published, or rejected version of a program's reviewed data."""

    __tablename__ = "program_revisions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'rejected')", name="ck_program_revision_status"),
        CheckConstraint("application_availability IN ('open', 'closed', 'unknown')", name="ck_application_availability"),
        CheckConstraint("validation_status IN ('pending', 'valid', 'invalid')", name="ck_program_revision_validation_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    # Admin edits reset validation before deterministic checks are rerun.
    validation_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    validation_findings: Mapped[list] = mapped_column(JSON, default=list)
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    categories: Mapped[list] = mapped_column(JSON)
    # Coverage records supported institutions, states, and national reach. It
    # remains reviewed catalog data rather than an inferred student attribute.
    coverage: Mapped[dict] = mapped_column(JSON)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    eligibility_tree: Mapped[dict] = mapped_column(JSON)
    coverage_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    award_cycle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_timezone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    application_availability: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    assistance_amount: Mapped[str | None] = mapped_column(String(240), nullable=True)
    selection_factors: Mapped[list] = mapped_column(JSON, default=list)
    # Ambiguous source statements remain visible to reviewers instead of being
    # discarded or silently converted into machine-answerable requirements.
    unresolved_conditions: Mapped[list] = mapped_column(JSON, default=list)
    provider_url: Mapped[str] = mapped_column(String(2048))
    application_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    program: Mapped[Program] = relationship(back_populates="revisions", foreign_keys=[program_id])
    sources: Mapped[list[SourceSnapshot]] = relationship(secondary=revision_sources, back_populates="revisions")
    review_events: Mapped[list["ReviewEvent"]] = relationship(back_populates="revision", cascade="all, delete-orphan")


class ReviewEvent(Base):
    """Append-only record of a human review decision for one revision."""

    __tablename__ = "review_events"
    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected')", name="ck_review_event_decision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(ForeignKey("program_revisions.id", ondelete="CASCADE"), index=True)
    reviewer: Mapped[str] = mapped_column(String(254))
    decision: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revision: Mapped[ProgramRevision] = relationship(back_populates="review_events")


class IngestionRun(Base):
    """Durable state for one source-to-review workflow execution."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'acquiring', 'extracting', 'validating', "
            "'awaiting_review', 'published', 'rejected', 'failed')",
            name="ck_ingestion_run_state",
        ),
        CheckConstraint("source_method IN ('webpage', 'pasted_text')", name="ck_ingestion_source_method"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    target_program_id: Mapped[str | None] = mapped_column(ForeignKey("programs.id", ondelete="SET NULL"), nullable=True, index=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    source_method: Mapped[str] = mapped_column(String(20))
    # Pasted source text must survive a worker restart before acquisition. It
    # remains in the database and is never copied into operational logs.
    input_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("source_snapshots.id", ondelete="SET NULL"), nullable=True, index=True)
    draft_revision_id: Mapped[str | None] = mapped_column(ForeignKey("program_revisions.id", ondelete="SET NULL"), nullable=True, index=True)
    extracted_draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_findings: Mapped[list] = mapped_column(JSON, default=list)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stage_attempts: Mapped[list["IngestionStageAttempt"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="IngestionStageAttempt.started_at"
    )


class IngestionStageAttempt(Base):
    """Append-only timing and safe outcome for one workflow stage attempt."""

    __tablename__ = "ingestion_stage_attempts"
    __table_args__ = (
        CheckConstraint("stage IN ('acquiring', 'extracting', 'validating')", name="ck_ingestion_attempt_stage"),
        CheckConstraint("outcome IN ('running', 'succeeded', 'retry_scheduled', 'failed')", name="ck_ingestion_attempt_outcome"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(20))
    attempt_number: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(24), default="running")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run: Mapped[IngestionRun] = relationship(back_populates="stage_attempts")
