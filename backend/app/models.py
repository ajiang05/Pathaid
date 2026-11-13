"""Minimal local foundation models for one PathAid installation."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class LocalProfile(Base):
    """Singleton private profile and its structured matching inputs."""

    __tablename__ = "local_profile"
    __table_args__ = (CheckConstraint("id = 1", name="ck_local_profile_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    school_revision: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    experiences: Mapped[list["ProfileExperience"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfileExperience.position"
    )


class ProfileExperience(Base):
    """One structured activity, job, service role, membership, or honor."""

    __tablename__ = "profile_experiences"
    __table_args__ = (
        CheckConstraint("profile_id = 1", name="ck_profile_experience_singleton_owner"),
        CheckConstraint("kind IN ('activity', 'employment', 'volunteering', 'membership', 'leadership', 'honor')", name="ck_profile_experience_kind"),
        CheckConstraint("hours IS NULL OR hours >= 0", name="ck_profile_experience_hours"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("local_profile.id", ondelete="CASCADE"), default=1, index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    organization: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    current: Mapped[bool] = mapped_column(Boolean, default=False)
    hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    leadership: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    profile: Mapped[LocalProfile] = relationship(back_populates="experiences")


class AppSetting(Base):
    """Non-secret local settings; keys and credentials never belong here."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Institution(Base):
    """One authoritative NCES IPEDS institution available for local selection."""

    __tablename__ = "institutions"

    unit_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(2), index=True)
    website_url: Mapped[str | None] = mapped_column(String(2_000), nullable=True)
    source_year: Mapped[int] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceScope(Base):
    """User-approved crawl boundary or unconfirmed directory proposal."""

    __tablename__ = "source_scopes"
    __table_args__ = (
        CheckConstraint("ownership IN ('school', 'sponsor')", name="ck_source_scope_ownership"),
        CheckConstraint("adapter IN ('generic', 'academicworks', 'kaleidoscope')", name="ck_source_scope_adapter"),
        CheckConstraint("status IN ('proposed', 'active', 'paused', 'inactive', 'policy_blocked')", name="ck_source_scope_status"),
        CheckConstraint("policy_status IN ('unknown', 'allowed', 'blocked')", name="ck_source_scope_policy"),
        CheckConstraint("max_depth BETWEEN 0 AND 2", name="ck_source_scope_depth"),
        CheckConstraint("page_budget BETWEEN 1 AND 100", name="ck_source_scope_page_budget"),
        CheckConstraint("requests_per_minute BETWEEN 1 AND 60", name="ck_source_scope_rate"),
        CheckConstraint("scan_interval_hours BETWEEN 6 AND 720", name="ck_source_scope_interval"),
        UniqueConstraint("hostname", "allowed_path_prefix", name="uq_source_scope_boundary"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(240))
    ownership: Mapped[str] = mapped_column(String(20))
    adapter: Mapped[str] = mapped_column(String(30))
    canonical_url: Mapped[str] = mapped_column(String(2_000))
    hostname: Mapped[str] = mapped_column(String(253), index=True)
    allowed_path_prefix: Mapped[str] = mapped_column(String(1_000))
    institution_unit_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.unit_id"), nullable=True, index=True)
    school_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposed", index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_depth: Mapped[int] = mapped_column(Integer, default=1)
    page_budget: Mapped[int] = mapped_column(Integer, default=25)
    requests_per_minute: Mapped[int] = mapped_column(Integer, default=10)
    scan_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    policy_status: Mapped[str] = mapped_column(String(20), default="unknown")
    policy_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_content_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scan_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SourcePolicyAssessment(Base):
    """Immutable user-reviewed evidence about source automation policy."""

    __tablename__ = "source_policy_assessments"
    __table_args__ = (
        CheckConstraint("outcome IN ('allowed', 'blocked')", name="ck_source_policy_assessment_outcome"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_scope_id: Mapped[str] = mapped_column(ForeignKey("source_scopes.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    evidence_url: Mapped[str | None] = mapped_column(String(2_000), nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ManualLead(Base):
    """One untrusted URL lead that grants no crawl scope around it."""

    __tablename__ = "manual_leads"
    __table_args__ = (
        CheckConstraint("status IN ('unverified', 'official_verified', 'unavailable', 'rejected')", name="ck_manual_lead_status"),
        UniqueConstraint("canonical_url", name="uq_manual_lead_url"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    canonical_url: Mapped[str] = mapped_column(String(2_000))
    hostname: Mapped[str] = mapped_column(String(253), index=True)
    status: Mapped[str] = mapped_column(String(30), default="unverified", index=True)
    official_url: Mapped[str | None] = mapped_column(String(2_000), nullable=True)
    official_hostname: Mapped[str | None] = mapped_column(String(253), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ManualLeadSnapshot(Base):
    """Immutable official-page evidence used to verify one manual lead."""

    __tablename__ = "manual_lead_snapshots"
    __table_args__ = (
        CheckConstraint("source_byte_count >= 0", name="ck_manual_lead_snapshot_bytes"),
        CheckConstraint("redirect_count >= 0", name="ck_manual_lead_snapshot_redirects"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    manual_lead_id: Mapped[str] = mapped_column(ForeignKey("manual_leads.id"), index=True)
    official_url: Mapped[str] = mapped_column(String(2_000), index=True)
    final_url: Mapped[str] = mapped_column(String(2_000))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    media_type: Mapped[str] = mapped_column(String(100))
    normalized_text: Mapped[str] = mapped_column(Text)
    source_byte_count: Mapped[int] = mapped_column(Integer)
    redirect_count: Mapped[int] = mapped_column(Integer)


class SourceScanRun(Base):
    """Durable outcome and bounded counters for one source traversal."""

    __tablename__ = "source_scan_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="ck_source_scan_run_status"),
        CheckConstraint("pages_attempted >= 0", name="ck_source_scan_pages_attempted"),
        CheckConstraint("snapshots_created >= 0", name="ck_source_scan_snapshots_created"),
        CheckConstraint("unchanged_pages >= 0", name="ck_source_scan_unchanged_pages"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_scope_id: Mapped[str] = mapped_column(ForeignKey("source_scopes.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pages_attempted: Mapped[int] = mapped_column(Integer, default=0)
    snapshots_created: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_pages: Mapped[int] = mapped_column(Integer, default=0)
    traversal_truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class SourceSnapshot(Base):
    """Immutable normalized evidence retained from one successful page fetch."""

    __tablename__ = "source_snapshots"
    __table_args__ = (
        CheckConstraint("depth BETWEEN 0 AND 2", name="ck_source_snapshot_depth"),
        CheckConstraint("source_byte_count >= 0", name="ck_source_snapshot_bytes"),
        CheckConstraint("redirect_count >= 0", name="ck_source_snapshot_redirects"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_scope_id: Mapped[str] = mapped_column(ForeignKey("source_scopes.id"), index=True)
    scan_run_id: Mapped[str] = mapped_column(ForeignKey("source_scan_runs.id"), index=True)
    canonical_url: Mapped[str] = mapped_column(String(2_000), index=True)
    final_url: Mapped[str] = mapped_column(String(2_000))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    media_type: Mapped[str] = mapped_column(String(100))
    normalized_text: Mapped[str] = mapped_column(Text)
    source_byte_count: Mapped[int] = mapped_column(Integer)
    redirect_count: Mapped[int] = mapped_column(Integer)
    depth: Mapped[int] = mapped_column(Integer)


class SourcePageState(Base):
    """Mutable current-presence state backed by immutable snapshot history."""

    __tablename__ = "source_page_states"
    __table_args__ = (
        CheckConstraint("status IN ('current', 'disappeared')", name="ck_source_page_state_status"),
        CheckConstraint("missed_scan_count >= 0", name="ck_source_page_state_missed_scans"),
        UniqueConstraint("source_scope_id", "canonical_url", name="uq_source_page_state_url"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_scope_id: Mapped[str] = mapped_column(ForeignKey("source_scopes.id"), index=True)
    canonical_url: Mapped[str] = mapped_column(String(2_000), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    missed_scan_count: Mapped[int] = mapped_column(Integer, default=0)


class Scholarship(Base):
    """Stable scholarship identity whose active pointer may advance safely."""

    __tablename__ = "scholarships"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="ck_scholarship_status"),
        UniqueConstraint("source_url", name="uq_scholarship_source_url"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_url: Mapped[str] = mapped_column(String(2_000), index=True)
    # This is intentionally not a database foreign key: scholarship_versions
    # already points back here, and avoiding a circular FK keeps SQLite backup,
    # migration, and deletion behavior predictable.
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ScholarshipVersion(Base):
    """Immutable validated scholarship facts tied to retained source evidence."""

    __tablename__ = "scholarship_versions"
    __table_args__ = (
        UniqueConstraint("scholarship_id", "source_snapshot_id", "draft_hash", name="uq_scholarship_version_input"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scholarship_id: Mapped[str] = mapped_column(ForeignKey("scholarships.id"), index=True)
    source_snapshot_id: Mapped[str] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    draft_hash: Mapped[str] = mapped_column(String(64), index=True)
    material_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSON)
    validation_findings: Mapped[list] = mapped_column(JSON, default=list)
    extraction_model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[str] = mapped_column(String(40))
    provider_request_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SavedScholarship(Base):
    """Minimal local application state for one stable scholarship identity."""

    __tablename__ = "saved_scholarships"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'already_applied')",
            name="ck_saved_scholarship_status",
        ),
    )

    scholarship_id: Mapped[str] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(30), default="not_started", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )


class SkippedScholarship(Base):
    """Cycle-level dismissal that stops applying after a material change."""

    __tablename__ = "skipped_scholarships"

    scholarship_id: Mapped[str] = mapped_column(
        ForeignKey("scholarships.id", ondelete="CASCADE"), primary_key=True
    )
    material_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    skipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PortalMapping(Base):
    """Student-corrected field mapping scoped to one portal form shape."""

    __tablename__ = "portal_mappings"
    __table_args__ = (
        UniqueConstraint(
            "portal_origin", "form_signature", "field_signature",
            name="uq_portal_mapping_field",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    portal_origin: Mapped[str] = mapped_column(String(500), index=True)
    form_signature: Mapped[str] = mapped_column(String(64), index=True)
    field_signature: Mapped[str] = mapped_column(String(64))
    profile_field: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Document(Base):
    """Non-secret metadata for one current encrypted managed document."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("document_type IN ('resume', 'transcript')", name="ck_document_type"),
        CheckConstraint("size_bytes > 0", name="ck_document_size"),
    )

    document_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    original_name: Mapped[str] = mapped_column(String(240))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    encrypted_filename: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Essay(Base):
    """Student-authored essay text and local recommendation metadata."""

    __tablename__ = "essays"
    __table_args__ = (
        CheckConstraint("word_count > 0", name="ck_essay_word_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    original_prompt: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    themes: Mapped[list] = mapped_column(JSON, default=list)
    word_count: Mapped[int] = mapped_column(Integer)
    written_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
    uses: Mapped[list["EssayUse"]] = relationship(
        back_populates="essay", cascade="all, delete-orphan", order_by="EssayUse.used_at"
    )


class EssayUse(Base):
    """History that records where the student chose to reuse an essay."""

    __tablename__ = "essay_uses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    essay_id: Mapped[str] = mapped_column(ForeignKey("essays.id", ondelete="CASCADE"), index=True)
    scholarship_id: Mapped[str | None] = mapped_column(
        ForeignKey("scholarships.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scholarship_name: Mapped[str] = mapped_column(String(240))
    destination_prompt: Mapped[str] = mapped_column(Text)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    essay: Mapped[Essay] = relationship(back_populates="uses")


class ExtractionActivationAttempt(Base):
    """Append-only result of validating one provider extraction response."""

    __tablename__ = "extraction_activation_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('activated', 'unchanged', 'validation_failed')", name="ck_extraction_activation_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_snapshot_id: Mapped[str] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    scholarship_id: Mapped[str | None] = mapped_column(ForeignKey("scholarships.id"), nullable=True, index=True)
    activated_version_id: Mapped[str | None] = mapped_column(ForeignKey("scholarship_versions.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    draft: Mapped[dict] = mapped_column(JSON)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    extraction_model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[str] = mapped_column(String(40))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DiscoveryJob(Base):
    """Durable scheduled source refresh claimed through a short worker lease."""

    __tablename__ = "discovery_jobs"
    __table_args__ = (
        CheckConstraint("trigger IN ('scheduled', 'manual')", name="ck_discovery_job_trigger"),
        CheckConstraint("status IN ('queued', 'running', 'retry_wait', 'succeeded', 'failed', 'cancelled')", name="ck_discovery_job_status"),
        CheckConstraint("stage IN ('acquisition', 'extraction', 'activation', 'complete')", name="ck_discovery_job_stage"),
        CheckConstraint("attempt_count >= 0 AND max_attempts >= 1", name="ck_discovery_job_attempts"),
        UniqueConstraint("source_scope_id", "trigger", "window_start", name="uq_discovery_job_window"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_scope_id: Mapped[str] = mapped_column(ForeignKey("source_scopes.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(20))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    stage: Mapped[str] = mapped_column(String(20), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scan_run_id: Mapped[str | None] = mapped_column(ForeignKey("source_scan_runs.id"), nullable=True, index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DiscoveryExtractionArtifact(Base):
    """Persisted local extraction outcome so retries resume per page."""

    __tablename__ = "discovery_extraction_artifacts"
    __table_args__ = (
        CheckConstraint("status IN ('extracted', 'activated', 'validation_failed', 'skipped')", name="ck_discovery_artifact_status"),
        UniqueConstraint("discovery_job_id", "source_snapshot_id", name="uq_discovery_artifact_snapshot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    discovery_job_id: Mapped[str] = mapped_column(ForeignKey("discovery_jobs.id"), index=True)
    source_snapshot_id: Mapped[str] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
