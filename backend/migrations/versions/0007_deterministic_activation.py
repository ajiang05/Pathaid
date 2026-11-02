"""Add deterministic scholarship activation and immutable version history.

Revision ID: 0007_deterministic_activation
Revises: 0006_source_policy_assessments
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_deterministic_activation"
down_revision = "0006_source_policy_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create local active records without a reviewer/publication queue."""

    op.create_table(
        "scholarships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=False),
        sa.Column("active_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_scholarship_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url", name="uq_scholarship_source_url"),
    )
    op.create_index("ix_scholarships_source_url", "scholarships", ["source_url"])
    op.create_index("ix_scholarships_active_version_id", "scholarships", ["active_version_id"])
    op.create_index("ix_scholarships_status", "scholarships", ["status"])
    op.create_table(
        "scholarship_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scholarship_id", sa.String(length=36), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("draft_hash", sa.String(length=64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("validation_findings", sa.JSON(), nullable=False),
        sa.Column("extraction_model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("provider_request_id", sa.String(length=240), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scholarship_id"], ["scholarships.id"]),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scholarship_id", "source_snapshot_id", "draft_hash", name="uq_scholarship_version_input"),
    )
    for column in ("scholarship_id", "source_snapshot_id", "draft_hash", "activated_at"):
        op.create_index(f"ix_scholarship_versions_{column}", "scholarship_versions", [column])
    op.create_table(
        "extraction_activation_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("scholarship_id", sa.String(length=36), nullable=True),
        sa.Column("activated_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("extraction_model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('activated', 'unchanged', 'validation_failed')", name="ck_extraction_activation_status"),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["source_snapshots.id"]),
        sa.ForeignKeyConstraint(["scholarship_id"], ["scholarships.id"]),
        sa.ForeignKeyConstraint(["activated_version_id"], ["scholarship_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("source_snapshot_id", "scholarship_id", "activated_version_id", "status", "attempted_at"):
        op.create_index(f"ix_extraction_activation_attempts_{column}", "extraction_activation_attempts", [column])
    for table in ("scholarship_versions", "extraction_activation_attempts"):
        op.execute(f"""
            CREATE TRIGGER {table}_no_update
            BEFORE UPDATE ON {table}
            BEGIN SELECT RAISE(ABORT, '{table} are immutable'); END
        """)
        op.execute(f"""
            CREATE TRIGGER {table}_no_delete
            BEFORE DELETE ON {table}
            BEGIN SELECT RAISE(ABORT, '{table} are immutable'); END
        """)


def downgrade() -> None:
    """Remove activation state while preserving retained source snapshots."""

    for table in ("extraction_activation_attempts", "scholarship_versions"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_delete")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_update")
    for column in ("source_snapshot_id", "scholarship_id", "activated_version_id", "status", "attempted_at"):
        op.drop_index(f"ix_extraction_activation_attempts_{column}", table_name="extraction_activation_attempts")
    op.drop_table("extraction_activation_attempts")
    for column in ("scholarship_id", "source_snapshot_id", "draft_hash", "activated_at"):
        op.drop_index(f"ix_scholarship_versions_{column}", table_name="scholarship_versions")
    op.drop_table("scholarship_versions")
    op.drop_index("ix_scholarships_status", table_name="scholarships")
    op.drop_index("ix_scholarships_active_version_id", table_name="scholarships")
    op.drop_index("ix_scholarships_source_url", table_name="scholarships")
    op.drop_table("scholarships")
