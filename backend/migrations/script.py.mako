"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
# down_revision links this migration to the previous schema version.
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    # Apply this schema change.
    ${upgrades if upgrades else "pass"}


def downgrade():
    # Reverse this schema change when a rollback is requested.
    ${downgrades if downgrades else "pass"}
