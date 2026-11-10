# Local runtime and packaging

PathAid's MVP is a local macOS application, not a hosted deployment. The local
runtime, scheduler, extension, document vault, encrypted backup, and developer
launcher described here are implemented. Remaining release evidence is tracked
in [../plan.md](../plan.md).

## Runtime topology

- FastAPI listens on `127.0.0.1` only.
- Next.js serves the local UI and proxies same-origin API requests.
- SQLite is the local system of record.
- A scheduler and worker process durable scan jobs.
- The Chrome extension connects to narrow loopback endpoints using an
  installation-specific token.
- macOS Keychain stores Gemini, extension-installation, and document-encryption
  secrets.

PostgreSQL, Caddy, TLS domains, public ingress, administrator credentials, and
cloud container deployment are not MVP dependencies.

## Local startup

```bash
scripts/pathaid bootstrap
scripts/pathaid start
```

The launcher implements this startup order:

1. Resolve the fixed PathAid app-data directory.
2. Load/create required Keychain entries.
3. Apply Alembic migrations to SQLite.
4. Start the loopback API and background worker.
5. Start the local web interface.
6. Enqueue at most one catch-up scan per overdue approved source.
7. Report health and the local interface URL.

A failed migration prevents API/worker startup. A missing Gemini key disables
AI-dependent extraction but does not prevent viewing existing data or matching.

## Persistence

SQLite, retained public snapshots, essays, and encrypted documents live in the
PathAid app-data directory. WAL and temporary files remain on the same local
filesystem. Stop processes cleanly before copying database files; normal backup
uses the application backup service rather than raw copying.

The current Docker PostgreSQL volume is legacy/disposable. It is not a required
migration source.

## Health and recovery

The local status command must distinguish:

- API process live;
- database migrated and writable;
- worker active or intentionally stopped;
- latest scheduled scan success/failure;
- Gemini configured/unconfigured;
- extension connected/disconnected; and
- document vault available/locked.

Interrupted jobs resume from the last committed stage. External calls occur
outside SQLite transactions. A corrupt/incompatible database is not silently
recreated; PathAid preserves it and reports recovery steps.

## Backup

Backups are encrypted, schema-versioned, and integrity checked. Include profile,
scholarships, source approvals/history, essay bank, saved/application status,
and portal mappings. Exclude résumé/transcript bytes, Gemini/install/document
keys, credentials, browser cookies, and caches.

Restore validates into a temporary database before replacing live state. A
backup never changes Keychain secrets or installs documents silently.

## Factory reset

Reset is explicitly destructive. It must display resolved PathAid-only targets,
require confirmation, stop local processes, remove SQLite/encrypted documents/
caches, and remove only PathAid Keychain items. It must not use a broad home or
workspace path as a recursive target.

## Development containers

Docker may remain as an optional reproducible development tool, but Compose is
not the product boundary and must not imply PostgreSQL or a hosted architecture.
The final macOS flow should not require Docker Desktop.

## Release verification

Before an MVP release:

- bootstrap a clean checkout and clean app-data directory;
- apply all SQLite migrations from zero;
- run backend, frontend, extension, adapter, security, and backup tests;
- connect the unpacked extension with minimal permissions;
- scan a user-approved source and verify unchanged-content behavior;
- preview/fill representative supported forms without submission; and
- verify that stopped/restarted services preserve data and recover jobs.

Signed macOS packaging, automatic updates, notarization, Chrome Web Store
publication, and consumer support are post-MVP projects.
