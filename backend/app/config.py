"""Local-only runtime configuration and application data paths."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


EXTENSION_ID_PATTERN = re.compile(r"^[a-p]{32}$")


def default_data_dir() -> Path:
    """Return the platform-appropriate per-user PathAid data directory."""

    override = os.environ.get("PATHAID_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "PathAid").resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (root / "pathaid").resolve()


@dataclass(frozen=True)
class Settings:
    """Non-secret settings; secrets are retrieved through ``SecretStore``."""

    data_dir: Path
    database_path: Path
    web_origin: str = "http://127.0.0.1:3000"
    extension_id: str | None = None
    keychain_service: str = "com.pathaid.local"
    sqlite_busy_timeout_ms: int = 5_000

    def __post_init__(self) -> None:
        parsed_origin = urlsplit(self.web_origin)
        if parsed_origin.scheme != "http" or parsed_origin.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("PATHAID_WEB_ORIGIN must be a local HTTP origin")
        if self.extension_id is not None and not EXTENSION_ID_PATTERN.fullmatch(self.extension_id):
            raise ValueError("PATHAID_EXTENSION_ID must be a 32-character Chrome extension ID")
        if self.sqlite_busy_timeout_ms < 1:
            raise ValueError("PATHAID_SQLITE_BUSY_TIMEOUT_MS must be positive")

    @property
    def extension_origin(self) -> str | None:
        """Return the exact Chrome extension origin when configured."""

        return f"chrome-extension://{self.extension_id}" if self.extension_id else None

    @classmethod
    def from_env(cls) -> "Settings":
        """Load local settings without accepting a remote database URL."""

        data_dir = default_data_dir()
        database_value = os.environ.get("PATHAID_DATABASE_PATH")
        database_path = Path(database_value).expanduser().resolve() if database_value else data_dir / "pathaid.sqlite3"
        timeout = int(os.environ.get("PATHAID_SQLITE_BUSY_TIMEOUT_MS", "5000"))
        return cls(
            data_dir=data_dir,
            database_path=database_path,
            web_origin=os.environ.get("PATHAID_WEB_ORIGIN", "http://127.0.0.1:3000").rstrip("/"),
            extension_id=os.environ.get("PATHAID_EXTENSION_ID") or None,
            keychain_service=os.environ.get("PATHAID_KEYCHAIN_SERVICE", "com.pathaid.local"),
            sqlite_busy_timeout_ms=timeout,
        )

    def prepare_directories(self) -> None:
        """Create private local directories needed by the foundation."""

        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.data_dir.chmod(0o700)
        except OSError:
            pass
