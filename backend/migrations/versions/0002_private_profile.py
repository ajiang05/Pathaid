"""Add structured single-user profile experiences and school revision state.

Revision ID: 0002_private_profile
Revises: 0001_local_foundation
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_private_profile"
down_revision = "0001_local_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend the singleton profile without introducing accounts or owners."""

    with op.batch_alter_table("local_profile") as batch:
        batch.add_column(sa.Column("school_revision", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "profile_experiences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("organization", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("current", sa.Boolean(), nullable=False),
        sa.Column("hours", sa.Float(), nullable=True),
        sa.Column("leadership", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.CheckConstraint("profile_id = 1", name="ck_profile_experience_singleton_owner"),
        sa.CheckConstraint("kind IN ('activity', 'employment', 'volunteering', 'membership', 'leadership', 'honor')", name="ck_profile_experience_kind"),
        sa.CheckConstraint("hours IS NULL OR hours >= 0", name="ck_profile_experience_hours"),
        sa.ForeignKeyConstraint(["profile_id"], ["local_profile.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profile_experiences_profile_id", "profile_experiences", ["profile_id"])


def downgrade() -> None:
    """Return to the Phase 1 singleton container."""

    op.drop_index("ix_profile_experiences_profile_id", table_name="profile_experiences")
    op.drop_table("profile_experiences")
    with op.batch_alter_table("local_profile") as batch:
        batch.drop_column("school_revision")
