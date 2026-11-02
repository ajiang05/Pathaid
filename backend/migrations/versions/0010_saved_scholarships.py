"""Add minimal saved and cycle-level skipped scholarship state.

Revision ID: 0010_saved_scholarships
Revises: 0009_source_lifecycle
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_saved_scholarships"
down_revision = "0009_source_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Persist only the application states needed by the local workflow."""

    op.create_table(
        "saved_scholarships",
        sa.Column("scholarship_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'already_applied')",
            name="ck_saved_scholarship_status",
        ),
        sa.ForeignKeyConstraint(["scholarship_id"], ["scholarships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scholarship_id"),
    )
    op.create_index("ix_saved_scholarships_status", "saved_scholarships", ["status"])
    op.create_index("ix_saved_scholarships_updated_at", "saved_scholarships", ["updated_at"])
    op.create_table(
        "skipped_scholarships",
        sa.Column("scholarship_id", sa.String(length=36), nullable=False),
        sa.Column("material_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("skipped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scholarship_id"], ["scholarships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scholarship_id"),
    )
    op.create_index(
        "ix_skipped_scholarships_material_fingerprint",
        "skipped_scholarships",
        ["material_fingerprint"],
    )


def downgrade() -> None:
    """Remove tracker preferences without touching scholarship evidence."""

    op.drop_index("ix_skipped_scholarships_material_fingerprint", table_name="skipped_scholarships")
    op.drop_table("skipped_scholarships")
    op.drop_index("ix_saved_scholarships_updated_at", table_name="saved_scholarships")
    op.drop_index("ix_saved_scholarships_status", table_name="saved_scholarships")
    op.drop_table("saved_scholarships")
