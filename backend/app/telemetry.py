"""Privacy-safe structured events for API and model operations."""

from __future__ import annotations

import json
import logging
import time

from fastapi import Request


LOGGER = logging.getLogger("pathaid.operations")


async def record_request_metrics(request: Request, call_next):
    """Log route templates, status, and latency without values from the request."""

    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        # A route template such as /api/programs/{program_id} is safe to
        # aggregate. Never fall back to the raw path because it may contain an
        # account, program, or revision identifier.
        route_template = getattr(route, "path", "unmatched")
        event = {
            "event": "api_request",
            "method": request.method,
            "route": route_template,
            "status": status,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
        LOGGER.info(json.dumps(event, separators=(",", ":"), sort_keys=True))
