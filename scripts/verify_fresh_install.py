"""Exercise the local foundation from an empty temporary app-data directory."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.local_data import backup_database, restore_database, upgrade_database, validate_database  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class MemorySecrets:
    """Fresh-install verifier boundary that never touches a developer Keychain."""

    def __init__(self):
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def main() -> int:
    with TemporaryDirectory(prefix="pathaid-fresh-install-") as temporary:
        root = Path(temporary)
        data = root / "app-data"
        settings = Settings(data_dir=data, database_path=data / "pathaid.sqlite3")

        # A genuinely empty directory must migrate to the current schema, and
        # rerunning migration must be safe for normal restarts.
        upgrade_database(settings)
        upgrade_database(settings)
        validate_database(settings.database_path)

        with sqlite3.connect(settings.database_path) as connection:
            connection.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)",
                ("fresh_install_marker", "preserved"),
            )

        app = create_app(settings, MemorySecrets())
        with TestClient(app) as client:
            assert client.get("/health/live").json() == {"status": "live"}
            assert client.get("/health/ready").json() == {"status": "ready"}

        archive = root / "fresh.pathaid-backup"
        restored = root / "restored" / "pathaid.sqlite3"
        backup_database(settings.database_path, archive, passphrase="fresh install verification")
        restore_database(archive, restored, passphrase="fresh install verification")
        validate_database(restored)
        with sqlite3.connect(restored) as connection:
            value = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", ("fresh_install_marker",)
            ).fetchone()[0]
        assert value == "preserved"
        assert not (restored.parent / "documents").exists()

    print("Fresh app-data migration, restart, health, backup, and restore checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
