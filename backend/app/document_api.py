"""Loopback API for encrypted résumé and transcript management."""

from __future__ import annotations

from typing import Literal
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, Request, Response

from .database import Database
from .document_vault import DocumentVaultError, delete_document, store_document
from .models import Document
from .secrets import SecretStore


def _payload(row: Document) -> dict:
    return {
        "document_type": row.document_type,
        "original_name": row.original_name,
        "media_type": row.media_type,
        "size_bytes": row.size_bytes,
        "content_hash": row.content_hash,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def create_document_router(database: Database, secret_store: SecretStore) -> APIRouter:
    router = APIRouter(prefix="/api/documents", tags=["documents"])

    @router.get("")
    def documents() -> dict:
        with database.sessions() as db:
            rows = db.query(Document).order_by(Document.document_type).all()
            return {"items": [_payload(row) for row in rows]}

    @router.put("/{document_type}")
    async def upload_document(
        document_type: Literal["resume", "transcript"],
        request: Request,
        x_pathaid_filename: str = Header(min_length=1, max_length=240, alias="X-PathAid-Filename"),
    ) -> dict:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        body = await request.body()
        try:
            row = store_document(
                database, secret_store, document_type, unquote(x_pathaid_filename),
                content_type, body,
            )
        except DocumentVaultError as error:
            raise HTTPException(422, detail=str(error)) from error
        return _payload(row)

    @router.delete("/{document_type}", status_code=204)
    def remove_document(document_type: Literal["resume", "transcript"]) -> Response:
        delete_document(database, document_type)
        return Response(status_code=204)

    return router
