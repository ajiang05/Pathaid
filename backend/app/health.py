"""Liveness and database readiness checks for containers and load balancers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db


router = APIRouter(tags=["operations"])
EXPECTED_MIGRATION = "0010_scheduled_discovery"
REQUIRED_TABLES = {
    "alembic_version",
    "students",
    "programs",
    "program_revisions",
    "source_snapshots",
    "ingestion_runs",
    "recommendation_attempts",
    "scheduled_sources",
    "scheduled_scans",
    "discovered_candidates",
}


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Confirm that the API process can serve requests."""

    return {"status": "live"}


@router.get("/health/ready")
def readiness(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    """Confirm database access and the minimum migrated schema without leaking details."""

    try:
        db.execute(text("SELECT 1"))
        available = set(inspect(db.get_bind()).get_table_names())
        version = db.scalar(text("SELECT version_num FROM alembic_version")) if "alembic_version" in available else None
    except SQLAlchemyError:
        response.status_code = 503
        return {"status": "not_ready", "reason": "database_unavailable"}
    if not REQUIRED_TABLES.issubset(available):
        response.status_code = 503
        return {"status": "not_ready", "reason": "database_migration_required"}
    if version != EXPECTED_MIGRATION:
        response.status_code = 503
        return {"status": "not_ready", "reason": "database_migration_required"}
    return {"status": "ready"}
