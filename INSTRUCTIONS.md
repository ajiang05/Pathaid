# PathAid local setup and command guide

Phase 1 provides the local macOS backend foundation. Scholarship profile,
discovery, saved-list, and extension UI behavior arrive in later phases; consult
[plan.md](plan.md) for implementation status.

## Prerequisites

- macOS
- Git
- Python 3.14
- Node.js/npm for the existing frontend development build
- Google Chrome for the future unpacked extension

PostgreSQL, Caddy, administrator credentials, and a hosted domain are no longer
required.

## Backend setup

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m app.local_admin init
```

`init` creates the local SQLite schema and stores the extension-installation and
future document-encryption keys in macOS Keychain. It does not print either key.
By default, local data is placed under:

```text
~/Library/Application Support/PathAid/
```

## Gemini key

Save or replace the personal Gemini key without putting it in `.env`:

```bash
cd backend
.venv/bin/python -m app.local_admin set-gemini-key
```

The prompt hides input. The key is stored under the Keychain service
`com.pathaid.local`. Extraction is not connected to the new runtime until the
discovery phase, but the secret boundary is ready.

## Start the local API

Apply migrations and bind FastAPI to loopback only:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app
```

Check it from another terminal:

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8000/api/local/status
```

`ready` confirms the SQLite schema, migration version, WAL mode, and foreign-key
enforcement. The native entrypoint hardcodes `127.0.0.1`; set
`PATHAID_API_PORT` to use a different port if 8000 is occupied.

## Tests and schema verification

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/alembic heads
.venv/bin/alembic check
.venv/bin/python -m app.quality_report
```

The suite uses temporary databases and in-memory secret stores; it never changes
your Keychain or real local database.

## Backup and restore

Stop the API before restore. Create a consistent Phase 1 SQLite backup:

```bash
cd backend
.venv/bin/python -m app.local_admin backup /absolute/path/pathaid-backup.sqlite3
```

The command refuses to overwrite an existing file. Restore a validated backup:

```bash
.venv/bin/python -m app.local_admin restore /absolute/path/pathaid-backup.sqlite3
.venv/bin/python -m app.local_admin status
```

Phase 1 backups are database recovery snapshots. Encrypted user backups and
document exclusions are implemented in Phase 6; do not place real sensitive
profile data in this transitional runtime.

## Reset local data

Reset is destructive and deliberately requires `--yes`:

```bash
cd backend
.venv/bin/python -m app.local_admin reset --yes
```

It removes only the resolved PathAid SQLite/WAL files and the three managed
Keychain entries (Gemini, extension token, document key). It refuses to reset a
database outside the PathAid data directory and does not delete unrelated files.

## Optional Docker development stack

Docker Compose now runs SQLite migration, FastAPI, and the existing frontend.
It has no PostgreSQL or Caddy service:

```bash
docker compose up --build --detach
docker compose ps
docker compose logs --follow api
docker compose down
```

If an older stack already uses ports 8000 or 3000, choose unused host ports:

```bash
PATHAID_API_PORT=8766 PATHAID_WEB_PORT=3100 docker compose up --build --detach
```

The container is an optional development convenience, not the target macOS
secret-storage runtime. Keychain-dependent endpoints are expected to remain
unavailable inside the Linux container.

## Non-secret overrides

Copy `.env.example` only when you need development path/origin overrides. Never
put Gemini, extension, document, portal, or browser credentials in it.

## Documentation

- [Product requirements](docs/PRD.md)
- [MVP scope](docs/MVP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Legacy inventory](docs/LEGACY_INVENTORY.md)
- [Implementation plan](plan.md)
