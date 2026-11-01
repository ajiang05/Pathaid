# Legacy implementation inventory

**Completed:** November 1, 2026

This inventory records the Phase 0/1 disposition of the previous hosted
implementation. Git history remains the detailed archive.

## Retained and already reusable

- `eligibility.py` and its deterministic benchmark
- `discovery.py` ranking concepts, pending Phase 2 terminology changes
- `source_acquisition.py` network-safety boundary
- extraction provider, schema, validation, and benchmark modules
- profile field registry as input to the Phase 2 profile redesign
- offline quality-report foundation

## Replaced in Phase 1

- PostgreSQL engine/configuration with local SQLite, WAL, foreign keys, and busy
  timeout
- ten hosted migrations with one local singleton baseline
- account/admin/publication FastAPI application with a loopback local API
- `.env` secrets with a macOS Keychain service boundary
- hosted deployment health assumptions with local schema/config readiness
- Caddy/PostgreSQL Compose stack with optional local development Compose
- hosted/PostgreSQL CI with fresh-SQLite migration and foundation tests

## Removed as intentionally obsolete

- student and administrator authentication/session/rate-limit modules
- admin ingestion and revision review APIs
- draft approval/rejection and catalog publication modules
- public catalog seed/export and hosted catalog intake commands
- hosted recommendation endpoints tied to authenticated students
- PostgreSQL worker/scheduler orchestration coupled to review states
- Caddy, production Compose overlay, and hosted-beta verification gates
- corresponding legacy tests that asserted the removed product behavior

The safe acquisition, extraction, and deterministic logic are kept even where
their comments still use old review terminology; those contracts are adapted in
Phases 2 and 3 before re-entering the runtime.

## Seed URL disposition

The previous catalog intake included scholarships and unrelated grants/basic-
needs resources. Only scholarship URLs were copied to
`backend/data/source_seed_urls_v1.json`. They are unverified candidate inputs,
not automatically approved sources or active scholarship records. Phase 3 must
reacquire and verify each official page before use.
