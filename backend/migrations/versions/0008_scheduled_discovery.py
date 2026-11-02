"""Add durable daily discovery jobs and resumable extraction artifacts.

Revision ID: 0008_scheduled_discovery
Revises: 0007_deterministic_activation
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_scheduled_discovery"
down_revision = "0007_deterministic_activation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create a lease-based queue with separately committed stage outputs."""

    op.create_table(
        "discovery_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_scope_id", sa.String(length=36), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_run_id", sa.String(length=36), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("trigger IN ('scheduled', 'manual')", name="ck_discovery_job_trigger"),
        sa.CheckConstraint("status IN ('queued', 'running', 'retry_wait', 'succeeded', 'failed', 'cancelled')", name="ck_discovery_job_status"),
        sa.CheckConstraint("stage IN ('acquisition', 'extraction', 'activation', 'complete')", name="ck_discovery_job_stage"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts >= 1", name="ck_discovery_job_attempts"),
        sa.ForeignKeyConstraint(["source_scope_id"], ["source_scopes.id"]),
        sa.ForeignKeyConstraint(["scan_run_id"], ["source_scan_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_scope_id", "trigger", "window_start", name="uq_discovery_job_window"),
    )
    for column in ("source_scope_id", "window_start", "status", "stage", "available_at", "lease_expires_at", "scan_run_id"):
        op.create_index(f"ix_discovery_jobs_{column}", "discovery_jobs", [column])
    op.create_table(
        "discovery_extraction_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("discovery_job_id", sa.String(length=36), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=True),
        sa.Column("extraction_model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("schema_version", sa.String(length=40), nullable=True),
        sa.Column("provider_request_id", sa.String(length=240), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('extracted', 'activated', 'validation_failed', 'skipped')", name="ck_discovery_artifact_status"),
        sa.ForeignKeyConstraint(["discovery_job_id"], ["discovery_jobs.id"]),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discovery_job_id", "source_snapshot_id", name="uq_discovery_artifact_snapshot"),
    )
    for column in ("discovery_job_id", "source_snapshot_id", "status"):
        op.create_index(f"ix_discovery_extraction_artifacts_{column}", "discovery_extraction_artifacts", [column])


def downgrade() -> None:
    """Remove queued work without touching source, snapshot, or scholarship history."""

    for column in ("discovery_job_id", "source_snapshot_id", "status"):
        op.drop_index(f"ix_discovery_extraction_artifacts_{column}", table_name="discovery_extraction_artifacts")
    op.drop_table("discovery_extraction_artifacts")
    for column in ("source_scope_id", "window_start", "status", "stage", "available_at", "lease_expires_at", "scan_run_id"):
        op.drop_index(f"ix_discovery_jobs_{column}", table_name="discovery_jobs")
    op.drop_table("discovery_jobs")
