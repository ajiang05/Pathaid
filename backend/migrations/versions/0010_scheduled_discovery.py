"""Add approved scheduled sources, scan history, and private candidates.

Revision ID: 0010_scheduled_discovery
Revises: 0009_recommendation_latency
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_scheduled_discovery"
down_revision = "0009_recommendation_latency"
branch_labels = None
depends_on = None


def upgrade():
    """Create scheduler state and link scheduled work to ingestion runs."""

    op.create_table(
        "scheduled_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("target_program_id", sa.String(36), sa.ForeignKey("programs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cadence_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("allowed_hostname", sa.String(253), nullable=False),
        sa.Column("allowed_path_prefix", sa.String(2048), nullable=False, server_default="/"),
        sa.Column("discovery_link_limit", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("respect_robots", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_scan_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_content_hash", sa.String(64), nullable=True),
        sa.Column("last_error_code", sa.String(80), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_type IN ('program_page', 'discovery_page')", name="ck_scheduled_source_type"),
        sa.CheckConstraint("cadence_hours >= 1", name="ck_scheduled_source_cadence"),
        sa.CheckConstraint("discovery_link_limit >= 0 AND discovery_link_limit <= 100", name="ck_scheduled_source_link_limit"),
    )
    op.create_index("ix_scheduled_sources_canonical_url", "scheduled_sources", ["canonical_url"], unique=True)
    op.create_index("ix_scheduled_sources_next_scan_at", "scheduled_sources", ["next_scan_at"])
    op.create_index("ix_scheduled_sources_enabled", "scheduled_sources", ["enabled"])
    op.create_index("ix_scheduled_sources_source_type", "scheduled_sources", ["source_type"])
    op.create_index("ix_scheduled_sources_target_program_id", "scheduled_sources", ["target_program_id"])
    op.create_table(
        "scheduled_scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("scheduled_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("content_changed", sa.Boolean(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("outcome IN ('queued', 'running', 'unchanged', 'changed', 'discovered', 'failed')", name="ck_scheduled_scan_outcome"),
        sa.UniqueConstraint("source_id", "window_start", name="uq_scheduled_scan_source_window"),
    )
    op.create_index("ix_scheduled_scans_source_id", "scheduled_scans", ["source_id"])
    op.create_index("ix_scheduled_scans_window_start", "scheduled_scans", ["window_start"])
    op.create_index("ix_scheduled_scans_outcome", "scheduled_scans", ["outcome"])
    op.create_table(
        "discovered_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("scheduled_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_scan_id", sa.String(36), sa.ForeignKey("scheduled_scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'awaiting_review', 'published', 'rejected', 'failed')",
            name="ck_discovered_candidate_status",
        ),
        sa.UniqueConstraint("source_id", "canonical_url", name="uq_candidate_source_url"),
    )
    op.create_index("ix_discovered_candidates_source_id", "discovered_candidates", ["source_id"])
    op.create_index("ix_discovered_candidates_first_scan_id", "discovered_candidates", ["first_scan_id"])
    op.create_index("ix_discovered_candidates_canonical_url", "discovered_candidates", ["canonical_url"])
    op.create_index("ix_discovered_candidates_status", "discovered_candidates", ["status"])

    # SQLite cannot alter check constraints in place, while recreating this
    # referenced table on PostgreSQL would temporarily drop its primary key.
    recreate = "always" if op.get_bind().dialect.name == "sqlite" else "never"
    with op.batch_alter_table("ingestion_runs", recreate=recreate) as batch:
        batch.drop_constraint("ck_ingestion_run_state", type_="check")
        batch.create_check_constraint(
            "ck_ingestion_run_state",
            "state IN ('queued', 'acquiring', 'extracting', 'validating', 'awaiting_review', 'unchanged', 'discovered', 'published', 'rejected', 'failed')",
        )
        batch.add_column(sa.Column("scheduled_source_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("scheduled_scan_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("discovered_candidate_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_ingestion_scheduled_source", "scheduled_sources", ["scheduled_source_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_ingestion_scheduled_scan", "scheduled_scans", ["scheduled_scan_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_ingestion_candidate", "discovered_candidates", ["discovered_candidate_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_ingestion_runs_scheduled_scan_id", ["scheduled_scan_id"], unique=True)
        batch.create_index("ix_ingestion_runs_discovered_candidate_id", ["discovered_candidate_id"])
        batch.create_index("ix_ingestion_runs_scheduled_source_id", ["scheduled_source_id"])


def downgrade():
    """Remove scheduled discovery state while preserving older ingestion data."""

    recreate = "always" if op.get_bind().dialect.name == "sqlite" else "never"
    with op.batch_alter_table("ingestion_runs", recreate=recreate) as batch:
        batch.drop_index("ix_ingestion_runs_discovered_candidate_id")
        batch.drop_index("ix_ingestion_runs_scheduled_scan_id")
        batch.drop_index("ix_ingestion_runs_scheduled_source_id")
        batch.drop_constraint("fk_ingestion_candidate", type_="foreignkey")
        batch.drop_constraint("fk_ingestion_scheduled_scan", type_="foreignkey")
        batch.drop_constraint("fk_ingestion_scheduled_source", type_="foreignkey")
        batch.drop_column("discovered_candidate_id")
        batch.drop_column("scheduled_scan_id")
        batch.drop_column("scheduled_source_id")
        batch.drop_constraint("ck_ingestion_run_state", type_="check")
        batch.create_check_constraint("ck_ingestion_run_state", "state IN ('queued', 'acquiring', 'extracting', 'validating', 'awaiting_review', 'published', 'rejected', 'failed')")
    op.drop_table("discovered_candidates")
    op.drop_table("scheduled_scans")
    op.drop_table("scheduled_sources")
