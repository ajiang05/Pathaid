"""Add protected administrator sessions and login throttling.

Revision ID: 0005_admin_sessions
Revises: 0004_ingestion_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_admin_sessions"
down_revision = "0004_ingestion_runs"
branch_labels = None
depends_on = None


def upgrade():
    """Create revocable admin sessions without storing administrator secrets."""

    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("admin_email", sa.String(254), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_sessions_admin_email", "admin_sessions", ["admin_email"])
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])

    op.create_table(
        "admin_auth_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Store a digest of the direct peer address rather than the raw value.
        sa.Column("address", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_auth_attempts_address", "admin_auth_attempts", ["address"])
    op.create_index("ix_admin_auth_attempts_created_at", "admin_auth_attempts", ["created_at"])


def downgrade():
    """Remove administrator authentication state."""

    op.drop_table("admin_auth_attempts")
    op.drop_table("admin_sessions")
