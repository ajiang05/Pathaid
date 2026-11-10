"""Canary tests proving sensitive operations do not emit values to logs."""

from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.document_vault import store_document
from app.extraction import ExtractionError, GeminiExtractionAdapter, GeminiExtractionConfig
from app.local_data import upgrade_database
from app.main import create_app
from app.secrets import EXTENSION_TOKEN
from conftest import FakeSecretStore


def test_profile_extension_extraction_and_document_canaries_never_enter_logs(tmp_path, caplog):
    caplog.set_level("DEBUG")
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data, database_path=data / "pathaid.sqlite3",
        extension_id="abcdefghijklmnopabcdefghijklmnop",
    )
    upgrade_database(settings)
    extension_canary = "EXTENSION-LOG-CANARY"
    profile_canary = "PROFILE-LOG-CANARY"
    document_canary = b"%PDF-1.7\nDOCUMENT-LOG-CANARY"
    provider_canary = "PROVIDER-LOG-CANARY"
    secrets = FakeSecretStore({EXTENSION_TOKEN: extension_canary})
    app = create_app(settings, secrets)

    with TestClient(app) as client:
        invalid = client.patch("/api/profile", json={"fields": {"email": profile_canary}})
        assert invalid.status_code == 422
        denied = client.get(
            "/api/extension/ping",
            headers={"Origin": settings.extension_origin, "X-PathAid-Token": f"wrong-{extension_canary}"},
        )
        assert denied.status_code == 401
    store_document(
        app.state.database, secrets, "resume", "resume.pdf", "application/pdf", document_canary,
    )

    class FailingModels:
        def generate_content(self, **_kwargs):
            raise RuntimeError(provider_canary)

    adapter = GeminiExtractionAdapter(
        GeminiExtractionConfig(api_key="GEMINI-LOG-CANARY", model="fixture"),
        client=SimpleNamespace(models=FailingModels()),
    )
    snapshot = SimpleNamespace(
        id="snapshot", source_url="https://example.org/scholarship",
        source_text="Public scholarship source.", acquired_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )
    with pytest.raises(ExtractionError):
        adapter.extract(snapshot)

    logged = caplog.text
    for canary in (
        extension_canary, profile_canary, document_canary.decode(), provider_canary, "GEMINI-LOG-CANARY",
    ):
        assert canary not in logged
