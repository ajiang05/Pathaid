"""Add immutable official evidence for manual lead verification.

Revision ID: 0005_manual_lead_verification
Revises: 0004_bounded_acquisition
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_manual_lead_verification"
down_revision = "0004_bounded_acquisition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Track verification timing and retain each changed official page."""

    with op.batch_alter_table("manual_leads") as batch:
        batch.add_column(sa.Column("official_hostname", sa.String(length=253), nullable=True))
        batch.add_column(sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "manual_lead_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("manual_lead_id", sa.String(length=36), nullable=False),
        sa.Column("official_url", sa.String(length=2000), nullable=False),
        sa.Column("final_url", sa.String(length=2000), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("source_byte_count", sa.Integer(), nullable=False),
        sa.Column("redirect_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("source_byte_count >= 0", name="ck_manual_lead_snapshot_bytes"),
        sa.CheckConstraint("redirect_count >= 0", name="ck_manual_lead_snapshot_redirects"),
        sa.ForeignKeyConstraint(["manual_lead_id"], ["manual_leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manual_lead_snapshots_manual_lead_id", "manual_lead_snapshots", ["manual_lead_id"])
    op.create_index("ix_manual_lead_snapshots_official_url", "manual_lead_snapshots", ["official_url"])
    op.create_index("ix_manual_lead_snapshots_acquired_at", "manual_lead_snapshots", ["acquired_at"])
    op.create_index("ix_manual_lead_snapshots_content_hash", "manual_lead_snapshots", ["content_hash"])
    # Evidence rows are append-only so later processing can cite what was
    # actually retrieved instead of silently rewriting historical content.
    op.execute("""
        CREATE TRIGGER manual_lead_snapshots_no_update
        BEFORE UPDATE ON manual_lead_snapshots
        BEGIN SELECT RAISE(ABORT, 'manual lead snapshots are immutable'); END
    """)
    op.execute("""
        CREATE TRIGGER manual_lead_snapshots_no_delete
        BEFORE DELETE ON manual_lead_snapshots
        BEGIN SELECT RAISE(ABORT, 'manual lead snapshots are immutable'); END
    """)


def downgrade() -> None:
    """Remove official evidence while retaining the original saved leads."""

    op.execute("DROP TRIGGER IF EXISTS manual_lead_snapshots_no_delete")
    op.execute("DROP TRIGGER IF EXISTS manual_lead_snapshots_no_update")
    op.drop_index("ix_manual_lead_snapshots_content_hash", table_name="manual_lead_snapshots")
    op.drop_index("ix_manual_lead_snapshots_acquired_at", table_name="manual_lead_snapshots")
    op.drop_index("ix_manual_lead_snapshots_official_url", table_name="manual_lead_snapshots")
    op.drop_index("ix_manual_lead_snapshots_manual_lead_id", table_name="manual_lead_snapshots")
    op.drop_table("manual_lead_snapshots")
    with op.batch_alter_table("manual_leads") as batch:
        batch.drop_column("verified_at")
        batch.drop_column("last_attempt_at")
        batch.drop_column("official_hostname")
