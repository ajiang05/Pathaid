"""Local settings, Keychain configuration, and encrypted backup download."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import mkstemp

from fastapi import APIRouter, HTTPException
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .config import Settings
from .local_data import LocalDataError, backup_database
from .secrets import DOCUMENT_KEY, EXTENSION_TOKEN, GEMINI_API_KEY, SecretStore, SecretStoreError


class GeminiKeyInput(BaseModel):
    """Secret request whose representation never includes the submitted key."""

    model_config = ConfigDict(extra="forbid")
    key: SecretStr = Field(min_length=8, max_length=500)


class BackupInput(BaseModel):
    """One-use passphrase for an encrypted download; it is never persisted."""

    model_config = ConfigDict(extra="forbid")
    passphrase: SecretStr = Field(min_length=12, max_length=1_024)


def create_settings_router(settings: Settings, secret_store: SecretStore) -> APIRouter:
    router = APIRouter(prefix="/api/settings", tags=["settings"])

    def secret_exists(name: str) -> bool:
        try:
            return bool(secret_store.get(name))
        except SecretStoreError:
            return False

    @router.get("/status")
    def status() -> dict:
        """Expose presence only; secret values and private paths stay hidden."""

        return {
            "gemini_configured": secret_exists(GEMINI_API_KEY),
            "extension_token_available": secret_exists(EXTENSION_TOKEN),
            "document_vault_key_available": secret_exists(DOCUMENT_KEY),
            "extension_configured": settings.extension_id is not None,
            "extension_id": settings.extension_id,
            "backup_format": "AES-256-GCM / scrypt / version 1",
            "backup_excludes": [
                "Gemini, installation, and document-encryption keys",
                "résumé and transcript ciphertext",
                "browser data and portal credentials",
                "cache and temporary files",
            ],
        }

    @router.put("/gemini-key")
    def save_gemini_key(payload: GeminiKeyInput) -> dict:
        try:
            secret_store.set(GEMINI_API_KEY, payload.key.get_secret_value().strip())
        except (SecretStoreError, ValueError) as error:
            raise HTTPException(503, detail="Gemini key could not be saved in macOS Keychain") from error
        return {"configured": True}

    @router.post("/backup")
    def download_backup(payload: BackupInput, background_tasks: BackgroundTasks):
        """Create a temporary encrypted archive and remove it after transfer."""

        settings.prepare_directories()
        descriptor, raw_path = mkstemp(prefix=".pathaid-download-", suffix=".pathaid-backup", dir=settings.data_dir)
        # mkstemp reserves a collision-free name. Close its descriptor before
        # backup_database atomically creates the archive at that exact path.
        os.close(descriptor)
        temporary = Path(raw_path)
        temporary.unlink(missing_ok=True)
        try:
            backup_database(
                settings.database_path, temporary,
                passphrase=payload.passphrase.get_secret_value(),
            )
        except LocalDataError as error:
            temporary.unlink(missing_ok=True)
            raise HTTPException(422, detail=str(error)) from error
        background_tasks.add_task(temporary.unlink, missing_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        return FileResponse(
            temporary, media_type="application/octet-stream",
            filename=f"pathaid-{timestamp}.pathaid-backup",
            background=background_tasks,
            headers={"Cache-Control": "no-store"},
        )

    return router
