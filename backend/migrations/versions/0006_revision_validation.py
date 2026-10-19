"""Track deterministic validation after administrator draft edits.

Revision ID: 0006_revision_validation
Revises: 0005_admin_sessions
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_revision_validation"
down_revision = "0005_admin_sessions"
branch_labels = None
depends_on = None


def upgrade():
    """Add review validation status and findings to catalog revisions."""

    with op.batch_alter_table("program_revisions") as batch:
        # Existing revisions require review again unless they were already
        # published through the earlier catalog boundary.
        batch.add_column(sa.Column("validation_status", sa.String(20), server_default="pending", nullable=False))
        batch.add_column(sa.Column("validation_findings", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch.create_index("ix_program_revisions_validation_status", ["validation_status"])
        batch.create_check_constraint(
            "ck_program_revision_validation_status",
            "validation_status IN ('pending', 'valid', 'invalid')",
        )
    op.execute("UPDATE program_revisions SET validation_status = 'valid' WHERE status = 'published'")


def downgrade():
    """Remove edit-time validation metadata."""

    with op.batch_alter_table("program_revisions") as batch:
        batch.drop_constraint("ck_program_revision_validation_status", type_="check")
        batch.drop_index("ix_program_revisions_validation_status")
        batch.drop_column("validation_findings")
        batch.drop_column("validation_status")
