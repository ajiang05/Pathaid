"""Add immutable source automation-policy assessments.

Revision ID: 0006_source_policy_assessments
Revises: 0005_manual_lead_verification
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_source_policy_assessments"
down_revision = "0005_manual_lead_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Retain policy decisions separately from the current source state."""

    op.create_table(
        "source_policy_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_scope_id", sa.String(length=36), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("evidence_url", sa.String(length=2000), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome IN ('allowed', 'blocked')", name="ck_source_policy_assessment_outcome"),
        sa.ForeignKeyConstraint(["source_scope_id"], ["source_scopes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_policy_assessments_source_scope_id", "source_policy_assessments", ["source_scope_id"])
    op.create_index("ix_source_policy_assessments_outcome", "source_policy_assessments", ["outcome"])
    op.create_index("ix_source_policy_assessments_checked_at", "source_policy_assessments", ["checked_at"])
    op.execute("""
        CREATE TRIGGER source_policy_assessments_no_update
        BEFORE UPDATE ON source_policy_assessments
        BEGIN SELECT RAISE(ABORT, 'source policy assessments are immutable'); END
    """)
    op.execute("""
        CREATE TRIGGER source_policy_assessments_no_delete
        BEFORE DELETE ON source_policy_assessments
        BEGIN SELECT RAISE(ABORT, 'source policy assessments are immutable'); END
    """)


def downgrade() -> None:
    """Remove policy history without changing registered source scopes."""

    op.execute("DROP TRIGGER IF EXISTS source_policy_assessments_no_delete")
    op.execute("DROP TRIGGER IF EXISTS source_policy_assessments_no_update")
    op.drop_index("ix_source_policy_assessments_checked_at", table_name="source_policy_assessments")
    op.drop_index("ix_source_policy_assessments_outcome", table_name="source_policy_assessments")
    op.drop_index("ix_source_policy_assessments_source_scope_id", table_name="source_policy_assessments")
    op.drop_table("source_policy_assessments")
