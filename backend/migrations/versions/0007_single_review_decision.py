"""Enforce one terminal review decision for each immutable revision.

Revision ID: 0007_single_review_decision
Revises: 0006_revision_validation
"""

from alembic import op


revision = "0007_single_review_decision"
down_revision = "0006_revision_validation"
branch_labels = None
depends_on = None


def upgrade():
    """Prevent concurrent approval or rejection from recording two decisions."""

    with op.batch_alter_table("review_events") as batch:
        batch.create_unique_constraint("uq_review_event_revision", ["revision_id"])


def downgrade():
    """Remove the single-decision database invariant."""

    with op.batch_alter_table("review_events") as batch:
        batch.drop_constraint("uq_review_event_revision", type_="unique")
