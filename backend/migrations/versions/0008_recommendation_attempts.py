"""Add privacy-reduced recommendation model usage records.

Revision ID: 0008_recommendation_attempts
Revises: 0007_single_review_decision
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_recommendation_attempts"
down_revision = "0007_single_review_decision"
branch_labels = None
depends_on = None


def upgrade():
    """Create bounded usage records without storing student values or prose."""

    op.create_table(
        "recommendation_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("program_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendation_attempts_student_id", "recommendation_attempts", ["student_id"])
    op.create_index("ix_recommendation_attempts_revision_id", "recommendation_attempts", ["revision_id"])
    op.create_index("ix_recommendation_attempts_created_at", "recommendation_attempts", ["created_at"])


def downgrade():
    """Remove recommendation usage records."""

    op.drop_table("recommendation_attempts")
