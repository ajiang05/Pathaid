"""Add detailed acquisition provenance to source snapshots.

Revision ID: 0003_source_provenance
Revises: 0002_program_catalog
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_source_provenance"
down_revision = "0002_program_catalog"
branch_labels = None
depends_on = None


def upgrade():
    """Add redirect destination, media type, and bounded-size metadata."""

    # Columns remain nullable so databases containing snapshots from migration
    # 0002 can upgrade without inventing provenance that was never recorded.
    with op.batch_alter_table("source_snapshots") as batch:
        batch.add_column(sa.Column("final_url", sa.String(2048), nullable=True))
        batch.add_column(sa.Column("media_type", sa.String(120), nullable=True))
        batch.add_column(sa.Column("source_byte_count", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("redirect_count", sa.Integer(), nullable=True))


def downgrade():
    """Remove acquisition fields while preserving the original snapshot data."""

    with op.batch_alter_table("source_snapshots") as batch:
        batch.drop_column("redirect_count")
        batch.drop_column("source_byte_count")
        batch.drop_column("media_type")
        batch.drop_column("final_url")
