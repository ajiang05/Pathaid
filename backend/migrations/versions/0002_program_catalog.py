"""Create the versioned program catalog and source provenance tables.

Revision ID: 0002_program_catalog
Revises: 0001_student_accounts
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_program_catalog"
down_revision = "0001_student_accounts"
branch_labels = None
depends_on = None


def upgrade():
    """Add stable programs, immutable revisions, sources, and review history."""

    op.create_table(
        "programs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("current_published_revision_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_programs_slug", "programs", ["slug"], unique=True)
    op.create_index("ix_programs_current_published_revision_id", "programs", ["current_published_revision_id"])

    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("acquisition_method", sa.String(20), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.CheckConstraint("acquisition_method IN ('webpage', 'pasted_text')", name="ck_source_acquisition_method"),
    )
    op.create_index("ix_source_snapshots_content_hash", "source_snapshots", ["content_hash"])

    op.create_table(
        "program_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("coverage", sa.JSON(), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("eligibility_tree", sa.JSON(), nullable=False),
        sa.Column("coverage_complete", sa.Boolean(), nullable=False),
        sa.Column("award_cycle", sa.String(120), nullable=True),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_timezone", sa.String(80), nullable=True),
        sa.Column("application_availability", sa.String(20), nullable=False),
        sa.Column("assistance_amount", sa.String(240), nullable=True),
        sa.Column("selection_factors", sa.JSON(), nullable=False),
        sa.Column("provider_url", sa.String(2048), nullable=False),
        sa.Column("application_url", sa.String(2048), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'rejected')", name="ck_program_revision_status"),
        sa.CheckConstraint("application_availability IN ('open', 'closed', 'unknown')", name="ck_application_availability"),
    )
    op.create_index("ix_program_revisions_program_id", "program_revisions", ["program_id"])
    op.create_index("ix_program_revisions_status", "program_revisions", ["status"])
    op.create_index("ix_program_revisions_application_availability", "program_revisions", ["application_availability"])

    op.create_table(
        "revision_sources",
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("program_revisions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_snapshot_id", sa.String(36), sa.ForeignKey("source_snapshots.id", ondelete="RESTRICT"), primary_key=True),
    )

    op.create_table(
        "review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("program_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer", sa.String(254), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_review_event_decision"),
    )
    op.create_index("ix_review_events_revision_id", "review_events", ["revision_id"])


def downgrade():
    """Remove catalog tables in reverse dependency order."""

    op.drop_table("review_events")
    op.drop_table("revision_sources")
    op.drop_table("program_revisions")
    op.drop_table("source_snapshots")
    op.drop_table("programs")
