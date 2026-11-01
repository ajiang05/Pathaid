"""Start PathAid on loopback; use ``python -m app`` for native operation."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Run the local API without accepting a configurable network interface."""

    port = int(os.environ.get("PATHAID_API_PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PATHAID_API_PORT must be between 1 and 65535")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, access_log=False)


if __name__ == "__main__":
    main()
