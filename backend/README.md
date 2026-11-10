# PathAid local backend

Phase 1 replaces the hosted account/admin platform with a single-user local
FastAPI foundation:

- SQLite with WAL, foreign keys, busy timeout, and one Alembic baseline;
- singleton local profile container and non-secret settings table;
- macOS Keychain boundary for Gemini, extension, and document secrets;
- loopback-only native startup and strict Host/CORS policy;
- exact Chrome extension origin plus installation-token authentication;
- safe database upgrade, integrity check, backup, restore, and reset commands;
  and
- no account, admin-review, publication, PostgreSQL, or Caddy runtime.

Reusable eligibility, extraction, discovery, and source-acquisition modules are
retained for later phases but are not exposed through the Phase 1 API.

## Setup and run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m app.local_admin init
python -m app
```

The native entrypoint always binds to `127.0.0.1`.

## Verify

```bash
.venv/bin/pytest -q
.venv/bin/alembic heads
.venv/bin/alembic check
.venv/bin/python -m app.quality_report
```

## Local operations

```bash
.venv/bin/python -m app.local_admin status
.venv/bin/python -m app.local_admin set-gemini-key
.venv/bin/python -m app.local_admin backup /absolute/path/backup.pathaid-backup
.venv/bin/python -m app.local_admin restore /absolute/path/backup.pathaid-backup
.venv/bin/python -m app.local_admin reset --yes
```

See [the full setup guide](../INSTRUCTIONS.md), [architecture](../docs/ARCHITECTURE.md),
and [implementation plan](../plan.md).
