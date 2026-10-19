"""Create student accounts, profiles, sessions, and auth attempts."""

from alembic import op
import sqlalchemy as sa

revision = "0001_student_accounts"
# This is the first migration, so it has no earlier revision.
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create the database objects needed by the student account feature."""
    # A student's editable profile is stored as JSON because its optional
    # fields come from the typed profile-field registry and will evolve.
    op.create_table(
        "students",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("ai_opt_in", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Email is the login identifier and must be unique across accounts.
    op.create_index("ix_students_email", "students", ["email"], unique=True)

    # Only hashes of session and CSRF tokens are stored. Deleting a student
    # cascades to their sessions so account deletion also signs them out.
    op.create_table(
        "student_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_student_sessions_student_id", "student_sessions", ["student_id"])
    # This index supports finding and eventually cleaning up expired sessions.
    op.create_index("ix_student_sessions_expires_at", "student_sessions", ["expires_at"])

    # Authentication attempts support the shared login/sign-up rate limit.
    # The address is hashed by the application before it reaches this table.
    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("address", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auth_attempts_address", "auth_attempts", ["address"])
    op.create_index("ix_auth_attempts_created_at", "auth_attempts", ["created_at"])


def downgrade():
    """Remove this feature's tables in reverse dependency order."""
    # Sessions reference students, so dependent tables must be removed first.
    op.drop_table("auth_attempts")
    op.drop_table("student_sessions")
    op.drop_table("students")
