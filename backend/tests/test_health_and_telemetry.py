"""Deployment health and privacy-safe request telemetry tests."""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def health_client():
    """Provide a database whose migration marker can be controlled by tests."""

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_liveness_does_not_depend_on_database_readiness(health_client):
    """A process can be live while migrations still prevent traffic."""

    client, _ = health_client
    assert client.get("/health/live").json() == {"status": "live"}
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "database_migration_required"}


def test_readiness_requires_database_and_migration_marker(health_client):
    """A migrated schema returns only a small readiness response."""

    client, engine = health_client
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0009_recommendation_latency')"))
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_request_event_uses_route_template_without_identifiers_or_query_values(health_client, caplog):
    """Operational logs must not contain raw paths, query strings, or bodies."""

    client, _ = health_client
    private_identifier = "private-program-identifier"
    private_query = "private-query-value"
    with caplog.at_level(logging.INFO, logger="pathaid.operations"):
        client.get(f"/api/programs/{private_identifier}?search={private_query}")
    events = "\n".join(record.message for record in caplog.records if record.name == "pathaid.operations")
    assert '"route":"/api/programs/{program_id}"' in events
    assert private_identifier not in events
    assert private_query not in events
