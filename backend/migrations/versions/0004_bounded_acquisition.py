"""Add durable scan runs and immutable public-source snapshots.

Revision ID: 0004_bounded_acquisition
Revises: 0003_source_registry
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_bounded_acquisition"
down_revision = "0003_source_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create evidence history without modifying source approval boundaries."""

    op.create_table(
        "source_scan_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_scope_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pages_attempted", sa.Integer(), nullable=False),
        sa.Column("snapshots_created", sa.Integer(), nullable=False),
        sa.Column("unchanged_pages", sa.Integer(), nullable=False),
        sa.Column("traversal_truncated", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="ck_source_scan_run_status"),
        sa.CheckConstraint("pages_attempted >= 0", name="ck_source_scan_pages_attempted"),
        sa.CheckConstraint("snapshots_created >= 0", name="ck_source_scan_snapshots_created"),
        sa.CheckConstraint("unchanged_pages >= 0", name="ck_source_scan_unchanged_pages"),
        sa.ForeignKeyConstraint(["source_scope_id"], ["source_scopes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_scan_runs_source_scope_id", "source_scan_runs", ["source_scope_id"])
    op.create_index("ix_source_scan_runs_status", "source_scan_runs", ["status"])
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_scope_id", sa.String(length=36), nullable=False),
        sa.Column("scan_run_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_url", sa.String(length=2000), nullable=False),
        sa.Column("final_url", sa.String(length=2000), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("source_byte_count", sa.Integer(), nullable=False),
        sa.Column("redirect_count", sa.Integer(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.CheckConstraint("depth BETWEEN 0 AND 2", name="ck_source_snapshot_depth"),
        sa.CheckConstraint("source_byte_count >= 0", name="ck_source_snapshot_bytes"),
        sa.CheckConstraint("redirect_count >= 0", name="ck_source_snapshot_redirects"),
        sa.ForeignKeyConstraint(["scan_run_id"], ["source_scan_runs.id"]),
        sa.ForeignKeyConstraint(["source_scope_id"], ["source_scopes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_snapshots_acquired_at", "source_snapshots", ["acquired_at"])
    op.create_index("ix_source_snapshots_canonical_url", "source_snapshots", ["canonical_url"])
    op.create_index("ix_source_snapshots_content_hash", "source_snapshots", ["content_hash"])
    op.create_index("ix_source_snapshots_scan_run_id", "source_snapshots", ["scan_run_id"])
    op.create_index("ix_source_snapshots_source_scope_id", "source_snapshots", ["source_scope_id"])
    op.execute("""
        CREATE TRIGGER source_snapshots_no_update
        BEFORE UPDATE ON source_snapshots
        BEGIN SELECT RAISE(ABORT, 'source snapshots are immutable'); END
    """)
    op.execute("""
        CREATE TRIGGER source_snapshots_no_delete
        BEFORE DELETE ON source_snapshots
        BEGIN SELECT RAISE(ABORT, 'source snapshots are immutable'); END
    """)


def downgrade() -> None:
    """Remove acquired evidence while retaining approved source scopes."""

    op.execute("DROP TRIGGER IF EXISTS source_snapshots_no_delete")
    op.execute("DROP TRIGGER IF EXISTS source_snapshots_no_update")
    op.drop_index("ix_source_snapshots_source_scope_id", table_name="source_snapshots")
    op.drop_index("ix_source_snapshots_scan_run_id", table_name="source_snapshots")
    op.drop_index("ix_source_snapshots_content_hash", table_name="source_snapshots")
    op.drop_index("ix_source_snapshots_canonical_url", table_name="source_snapshots")
    op.drop_index("ix_source_snapshots_acquired_at", table_name="source_snapshots")
    op.drop_table("source_snapshots")
    op.drop_index("ix_source_scan_runs_status", table_name="source_scan_runs")
    op.drop_index("ix_source_scan_runs_source_scope_id", table_name="source_scan_runs")
    op.drop_table("source_scan_runs")
