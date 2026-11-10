"""Add encrypted document metadata.

Revision ID: 0012_document_vault
Revises: 0011_portal_mappings
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_document_vault"
down_revision = "0011_portal_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store metadata only; encrypted bytes remain outside SQLite."""

    op.create_table(
        "documents",
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("original_name", sa.String(length=240), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("encrypted_filename", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("document_type IN ('resume', 'transcript')", name="ck_document_type"),
        sa.CheckConstraint("size_bytes > 0", name="ck_document_size"),
        sa.PrimaryKeyConstraint("document_type"),
        sa.UniqueConstraint("encrypted_filename"),
    )


def downgrade() -> None:
    """Remove metadata; operators must separately remove ciphertext files."""

    op.drop_table("documents")
