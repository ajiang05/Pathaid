"""Add source-page presence state and material version fingerprints.

Revision ID: 0009_source_lifecycle
Revises: 0008_scheduled_discovery
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_source_lifecycle"
down_revision = "0008_scheduled_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Track current page presence without deleting immutable evidence."""

    op.create_table(
        "source_page_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_scope_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_url", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("missing_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("missed_scan_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('current', 'disappeared')", name="ck_source_page_state_status"),
        sa.CheckConstraint("missed_scan_count >= 0", name="ck_source_page_state_missed_scans"),
        sa.ForeignKeyConstraint(["source_scope_id"], ["source_scopes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_scope_id", "canonical_url", name="uq_source_page_state_url"),
    )
    for column in ("source_scope_id", "canonical_url", "status", "last_seen_at"):
        op.create_index(f"ix_source_page_states_{column}", "source_page_states", [column])
    with op.batch_alter_table("scholarship_versions") as batch:
        batch.add_column(sa.Column("material_fingerprint", sa.String(length=64), nullable=True))
        batch.create_index("ix_scholarship_versions_material_fingerprint", ["material_fingerprint"])


def downgrade() -> None:
    """Remove derived lifecycle state while retaining snapshots and versions."""

    with op.batch_alter_table("scholarship_versions") as batch:
        batch.drop_index("ix_scholarship_versions_material_fingerprint")
        batch.drop_column("material_fingerprint")
    for column in ("source_scope_id", "canonical_url", "status", "last_seen_at"):
        op.drop_index(f"ix_source_page_states_{column}", table_name="source_page_states")
    op.drop_table("source_page_states")
