"""Add durable ingestion workflow records and unresolved draft conditions.

Revision ID: 0004_ingestion_runs
Revises: 0003_source_provenance
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_ingestion_runs"
down_revision = "0003_source_provenance"
branch_labels = None
depends_on = None


def upgrade():
    """Create run/attempt history and retain ambiguous draft conditions."""

    with op.batch_alter_table("program_revisions") as batch:
        # The server default upgrades existing databases without inventing
        # unresolved statements for already stored revisions.
        batch.add_column(sa.Column("unresolved_conditions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("parent_run_id", sa.String(36), sa.ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_program_id", sa.String(36), sa.ForeignKey("programs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("source_method", sa.String(20), nullable=False),
        sa.Column("input_source_text", sa.Text(), nullable=True),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(120), nullable=True),
        sa.Column("lease_token", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_snapshot_id", sa.String(36), sa.ForeignKey("source_snapshots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("draft_revision_id", sa.String(36), sa.ForeignKey("program_revisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("extracted_draft", sa.JSON(), nullable=True),
        sa.Column("validation_findings", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=True),
        sa.Column("schema_version", sa.String(40), nullable=True),
        sa.Column("provider_request_id", sa.String(160), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("state IN ('queued', 'acquiring', 'extracting', 'validating', 'awaiting_review', 'published', 'rejected', 'failed')", name="ck_ingestion_run_state"),
        sa.CheckConstraint("source_method IN ('webpage', 'pasted_text')", name="ck_ingestion_source_method"),
    )
    op.create_index("ix_ingestion_runs_idempotency_key", "ingestion_runs", ["idempotency_key"], unique=True)
    for column in ("parent_run_id", "target_program_id", "state", "next_attempt_at", "lease_expires_at", "source_snapshot_id", "draft_revision_id"):
        op.create_index(f"ix_ingestion_runs_{column}", "ingestion_runs", [column])

    op.create_table(
        "ingestion_stage_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint("stage IN ('acquiring', 'extracting', 'validating')", name="ck_ingestion_attempt_stage"),
        sa.CheckConstraint("outcome IN ('running', 'succeeded', 'retry_scheduled', 'failed')", name="ck_ingestion_attempt_outcome"),
    )
    op.create_index("ix_ingestion_stage_attempts_run_id", "ingestion_stage_attempts", ["run_id"])


def downgrade():
    """Remove orchestration records and the unresolved-condition field."""

    op.drop_table("ingestion_stage_attempts")
    op.drop_table("ingestion_runs")
    with op.batch_alter_table("program_revisions") as batch:
        batch.drop_column("unresolved_conditions")
