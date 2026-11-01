"""Add authoritative institutions, bounded source scopes, and manual leads.

Revision ID: 0003_source_registry
Revises: 0002_private_profile
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_source_registry"
down_revision = "0002_private_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create registry records without authorizing any source by default."""

    op.create_table(
        "institutions",
        sa.Column("unit_id", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("website_url", sa.String(length=2000), nullable=True),
        sa.Column("source_year", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("unit_id"),
    )
    op.create_index("ix_institutions_name", "institutions", ["name"])
    op.create_index("ix_institutions_state", "institutions", ["state"])
    op.create_table(
        "source_scopes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("ownership", sa.String(length=20), nullable=False),
        sa.Column("adapter", sa.String(length=30), nullable=False),
        sa.Column("canonical_url", sa.String(length=2000), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("allowed_path_prefix", sa.String(length=1000), nullable=False),
        sa.Column("institution_unit_id", sa.String(length=12), nullable=True),
        sa.Column("school_revision", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_depth", sa.Integer(), nullable=False),
        sa.Column("page_budget", sa.Integer(), nullable=False),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("scan_interval_hours", sa.Integer(), nullable=False),
        sa.Column("policy_status", sa.String(length=20), nullable=False),
        sa.Column("policy_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_content_change_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ownership IN ('school', 'sponsor')", name="ck_source_scope_ownership"),
        sa.CheckConstraint("adapter IN ('generic', 'academicworks', 'kaleidoscope')", name="ck_source_scope_adapter"),
        sa.CheckConstraint("status IN ('proposed', 'active', 'paused', 'inactive', 'policy_blocked')", name="ck_source_scope_status"),
        sa.CheckConstraint("policy_status IN ('unknown', 'allowed', 'blocked')", name="ck_source_scope_policy"),
        sa.CheckConstraint("max_depth BETWEEN 0 AND 2", name="ck_source_scope_depth"),
        sa.CheckConstraint("page_budget BETWEEN 1 AND 100", name="ck_source_scope_page_budget"),
        sa.CheckConstraint("requests_per_minute BETWEEN 1 AND 60", name="ck_source_scope_rate"),
        sa.CheckConstraint("scan_interval_hours BETWEEN 6 AND 720", name="ck_source_scope_interval"),
        sa.ForeignKeyConstraint(["institution_unit_id"], ["institutions.unit_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname", "allowed_path_prefix", name="uq_source_scope_boundary"),
    )
    op.create_index("ix_source_scopes_hostname", "source_scopes", ["hostname"])
    op.create_index("ix_source_scopes_institution_unit_id", "source_scopes", ["institution_unit_id"])
    op.create_index("ix_source_scopes_next_scan_at", "source_scopes", ["next_scan_at"])
    op.create_index("ix_source_scopes_status", "source_scopes", ["status"])
    op.create_table(
        "manual_leads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("canonical_url", sa.String(length=2000), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("official_url", sa.String(length=2000), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('unverified', 'official_verified', 'unavailable', 'rejected')", name="ck_manual_lead_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_url", name="uq_manual_lead_url"),
    )
    op.create_index("ix_manual_leads_hostname", "manual_leads", ["hostname"])
    op.create_index("ix_manual_leads_status", "manual_leads", ["status"])


def downgrade() -> None:
    """Remove registry data while retaining the private profile."""

    op.drop_index("ix_manual_leads_status", table_name="manual_leads")
    op.drop_index("ix_manual_leads_hostname", table_name="manual_leads")
    op.drop_table("manual_leads")
    op.drop_index("ix_source_scopes_status", table_name="source_scopes")
    op.drop_index("ix_source_scopes_next_scan_at", table_name="source_scopes")
    op.drop_index("ix_source_scopes_institution_unit_id", table_name="source_scopes")
    op.drop_index("ix_source_scopes_hostname", table_name="source_scopes")
    op.drop_table("source_scopes")
    op.drop_index("ix_institutions_state", table_name="institutions")
    op.drop_index("ix_institutions_name", table_name="institutions")
    op.drop_table("institutions")
