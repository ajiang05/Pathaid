"""Database boundary for acquiring and persisting immutable source snapshots."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import SourceSnapshot
from .source_acquisition import (
    AcquisitionConfig,
    PastedSourceRequest,
    Resolver,
    SingleHopTransport,
    WebSourceRequest,
    acquire_web_source,
    prepare_pasted_source,
)


SourceRequest = WebSourceRequest | PastedSourceRequest


def acquire_and_persist_source(
    db: Session,
    request: SourceRequest,
    config: AcquisitionConfig = AcquisitionConfig(),
    *,
    resolver: Resolver | None = None,
    transport: SingleHopTransport | None = None,
) -> SourceSnapshot:
    """Acquire one source completely, then commit its immutable snapshot."""

    if isinstance(request, PastedSourceRequest):
        acquired = prepare_pasted_source(request, config)
    elif isinstance(request, WebSourceRequest):
        acquired = acquire_web_source(
            request,
            config,
            resolver=resolver,
            transport=transport,
        )
    else:
        raise TypeError("Unsupported source request type")

    snapshot = SourceSnapshot(
        source_url=acquired.original_url,
        final_url=acquired.final_url,
        acquisition_method=acquired.acquisition_method,
        media_type=acquired.media_type,
        source_byte_count=acquired.source_byte_count,
        redirect_count=acquired.redirect_count,
        content_hash=acquired.content_hash,
        source_text=acquired.normalized_text,
    )
    db.add(snapshot)
    try:
        db.commit()
    except Exception:
        # Leave the caller's session usable and ensure a failed database write
        # cannot be mistaken for a successfully persisted workflow stage.
        db.rollback()
        raise
    db.refresh(snapshot)
    return snapshot
