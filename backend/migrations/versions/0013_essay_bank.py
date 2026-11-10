"""Add the local student-written essay bank.

Revision ID: 0013_essay_bank
Revises: 0012_document_vault
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_essay_bank"
down_revision = "0012_document_vault"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create editable essays and append-only prior-use history."""

    op.create_table(
        "essays",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("original_prompt", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("themes", sa.JSON(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("written_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("word_count > 0", name="ck_essay_word_count"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_essays_title", "essays", ["title"])
    op.create_index("ix_essays_updated_at", "essays", ["updated_at"])
    op.create_table(
        "essay_uses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("essay_id", sa.String(length=36), nullable=False),
        sa.Column("scholarship_id", sa.String(length=36), nullable=True),
        sa.Column("scholarship_name", sa.String(length=240), nullable=False),
        sa.Column("destination_prompt", sa.Text(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scholarship_id"], ["scholarships.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_essay_uses_essay_id", "essay_uses", ["essay_id"])
    op.create_index("ix_essay_uses_scholarship_id", "essay_uses", ["scholarship_id"])
    op.create_index("ix_essay_uses_used_at", "essay_uses", ["used_at"])


def downgrade() -> None:
    """Remove essay history before its parent essay records."""

    op.drop_table("essay_uses")
    op.drop_table("essays")
