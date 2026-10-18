"""Add aggregate latency to recommendation attempts.

Revision ID: 0009_recommendation_latency
Revises: 0008_recommendation_attempts
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_recommendation_latency"
down_revision = "0008_recommendation_attempts"
branch_labels = None
depends_on = None


def upgrade():
    """Record model request duration without storing student request content."""

    op.add_column("recommendation_attempts", sa.Column("latency_ms", sa.Integer(), nullable=True))


def downgrade():
    """Remove aggregate recommendation latency."""

    op.drop_column("recommendation_attempts", "latency_ms")
