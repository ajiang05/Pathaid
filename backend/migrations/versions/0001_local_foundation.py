"""Create the single-user local foundation schema.

Revision ID: 0001_local_foundation
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_local_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create only non-secret singleton profile and application settings."""

    op.create_table(
        "local_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_local_profile_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(sa.text("INSERT INTO local_profile (id, schema_version, data) VALUES (1, 1, '{}')"))


def downgrade() -> None:
    """Remove the local foundation schema."""

    op.drop_table("app_settings")
    op.drop_table("local_profile")
