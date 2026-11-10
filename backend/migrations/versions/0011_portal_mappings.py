"""Add student-corrected portal field mappings.

Revision ID: 0011_portal_mappings
Revises: 0010_saved_scholarships
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_portal_mappings"
down_revision = "0010_saved_scholarships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store corrections without retaining values entered in portal forms."""

    op.create_table(
        "portal_mappings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portal_origin", sa.String(length=500), nullable=False),
        sa.Column("form_signature", sa.String(length=64), nullable=False),
        sa.Column("field_signature", sa.String(length=64), nullable=False),
        sa.Column("profile_field", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portal_origin", "form_signature", "field_signature",
            name="uq_portal_mapping_field",
        ),
    )
    op.create_index("ix_portal_mappings_portal_origin", "portal_mappings", ["portal_origin"])
    op.create_index("ix_portal_mappings_form_signature", "portal_mappings", ["form_signature"])


def downgrade() -> None:
    """Remove learned mappings without changing profile or scholarship data."""

    op.drop_index("ix_portal_mappings_form_signature", table_name="portal_mappings")
    op.drop_index("ix_portal_mappings_portal_origin", table_name="portal_mappings")
    op.drop_table("portal_mappings")
