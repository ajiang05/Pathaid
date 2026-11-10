"""Document management API tests keep plaintext out of SQLite."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.local_data import upgrade_database
from app.main import create_app
from conftest import FakeSecretStore


def test_document_upload_list_replace_and_delete(tmp_path):
    data_dir = tmp_path / "data"
    settings = Settings(data_dir=data_dir, database_path=data_dir / "pathaid.sqlite3")
    upgrade_database(settings)
    app = create_app(settings, FakeSecretStore())
    with TestClient(app) as client:
        uploaded = client.put(
            "/api/documents/resume",
            content=b"%PDF-1.7\nprivate resume marker",
            headers={"Content-Type": "application/pdf", "X-PathAid-Filename": "resume.pdf"},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["document_type"] == "resume"
        assert uploaded.json()["original_name"] == "resume.pdf"
        assert client.get("/api/documents").json()["items"] == [uploaded.json()]
        rejected = client.put(
            "/api/documents/transcript", content=b"plain text",
            headers={"Content-Type": "text/plain", "X-PathAid-Filename": "grades.txt"},
        )
        assert rejected.status_code == 422
        assert client.delete("/api/documents/resume").status_code == 204
        assert client.get("/api/documents").json() == {"items": []}

    assert b"private resume marker" not in settings.database_path.read_bytes()
