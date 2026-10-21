# Pathaid backend

[![Backend CI](https://github.com/ajiang05/Pathaid/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/ajiang05/Pathaid/actions/workflows/backend-ci.yml)

The backend provides student accounts and profiles, a reviewed versioned catalog,
deterministic discovery and eligibility, source-backed application results, optional
grounded scholarship recommendation assistance, and protected ingestion and review
workflows. It also schedules approved scholarship sources, skips unchanged content,
and creates private candidate work from bounded discovery pages. Responsive student
and administrator interfaces consume these APIs.

Container startup, reviewed catalog transfer, backup, recovery, and production
security instructions are in [`docs/deployment.md`](../docs/deployment.md).

## Local setup

From `backend/`:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./pathaid.db
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Use PostgreSQL in deployed environments by setting `DATABASE_URL` to a `postgresql+psycopg://` URL. Set `PATHAID_PUBLIC_ORIGIN` to the frontend origin and `PATHAID_SECURE_COOKIES=true` under HTTPS. The API does not enable cross-origin browser requests; a same-origin proxy should expose `/api` to the frontend.

## API

- `GET /api/profile-fields` returns field metadata.
- `GET /api/programs` lists current published program revisions. Repeat the
  `categories` query parameter to filter by one or more assistance categories.
- `GET /api/programs/{id}` returns one current published revision with source
  provenance but without the retained source body.
- `POST /api/auth/signup` and `POST /api/auth/login` accept `{ "email": "...", "password": "..." }`, set an HttpOnly session cookie, and return a CSRF token.
- `GET /api/auth/session` returns a fresh CSRF token after page reload.
- `POST /api/auth/logout` requires the `X-CSRF-Token` header.
- `GET /api/profile`, `PATCH /api/profile`, and `DELETE /api/profile` access only the signed-in account. PATCH accepts `{ "fields": { ... }, "ai_opt_in": false }`; send `null` for a field to remove its saved answer. PATCH and DELETE require `X-CSRF-Token`.
- `POST /api/evaluate` combines the signed-in student's saved profile with
  temporary `answers`, evaluates published candidates, and returns deterministically
  ranked, source-backed outcomes with verification states, checklists, selection
  factors, and a template explanation. Temporary answers are not persisted.
- `POST /api/programs/{id}/recommendation-explanation` accepts an exact published
  `revision_id` and optional temporary `answers`. It always returns a grounded
  template and uses optional model assistance only after the student opts in.
- `GET /health/live` reports process liveness. `GET /health/ready` checks the
  database and required migration without returning connection details.
- `GET /api/admin/operations/summary` returns authenticated aggregate failure,
  latency, and source-verification signals without private request content.
- `/api/admin/scheduled-sources*` manages approved program and discovery pages;
  `/api/admin/scheduled-scans` and `/api/admin/discovered-candidates` expose
  privacy-safe scan and candidate status.

All profile fields remain optional. Recommendation assistance sends only saved or
temporary fields referenced by the evaluated rule; it never sends account identity,
credentials, or unrelated profile fields. Passwords are hashed with scrypt; session
and CSRF tokens are stored as SHA-256 hashes. The rate limit uses shared database
records. Behind a reverse proxy, configure a trusted peer address policy before
public deployment.

Recommendation explanations support OpenAI and Gemini. Select one with
`PATHAID_RECOMMENDATION_PROVIDER`, provide its server-side `OPENAI_API_KEY` or
`GEMINI_API_KEY`, and set `PATHAID_RECOMMENDATION_MODEL`,
`PATHAID_RECOMMENDATION_TIMEOUT_SECONDS`,
`PATHAID_RECOMMENDATION_MAX_OUTPUT_TOKENS`, and
`PATHAID_RECOMMENDATION_ATTEMPTS_PER_HOUR`. The default limit is ten attempts per
student per hour. The server renders final prose from reviewed reasons, so model
output cannot change an eligibility label or introduce an amount, deadline, or
requirement. Usage records contain aggregate outcomes and token counts only.

Run tests with `.venv/bin/pytest -q`.

Run the versioned offline quality report with:

```sh
.venv/bin/python -m app.quality_report
```

Validate the launch catalog's official-source intake manifest without accessing
the network or publishing anything:

```sh
.venv/bin/python -m app.catalog_intake validate
```

After configuring the database and optional extraction credentials, explicitly
queue one live smoke-test candidate with `.venv/bin/python -m app.catalog_intake
queue --entry gates-scholarship`, or queue all candidates by omitting `--entry`.
The command is idempotent. It creates ingestion runs only; each resulting draft still
requires source comparison and explicit administrator approval. The manifest is
`data/catalog_intake_v1.json` and is not a reviewed seed bundle.

The current deterministic measurement is 100/100 expected eligibility outcomes
on dataset version 1.0.0. The extraction dataset contains 10 cases, 28 field
labels, and 10 claim labels. Offline CI validates the dataset and metric harness
without claiming model accuracy. To calculate extraction field accuracy,
criterion precision/recall, unsupported-claim rate, and evidence fidelity from a
separately budgeted run, provide a versioned JSON artifact containing
`dataset_version` and a `predictions` object keyed by case ID:

```sh
.venv/bin/python -m app.quality_report \
  --extraction-predictions path/to/saved-predictions.json
```

Frontend browser checks pass locally. Production accessibility checks and five
student usability sessions remain pending.

Both pytest and Alembic are configured to treat `backend/` as the Python
package root, so the commands above work without setting `PYTHONPATH`.

GitHub Actions runs the same backend suite against PostgreSQL on every backend
push and pull request. It requires a single Alembic head, upgrades a fresh
database, checks that SQLAlchemy metadata matches the migrations, and then
runs the offline tests without an AI provider API key.

## Source acquisition

`app.source_service.acquire_and_persist_source` is the internal entry point for
Feature 06. It accepts either `WebSourceRequest` or `PastedSourceRequest`,
normalizes the source, calculates its SHA-256 hash, and saves an immutable
`SourceSnapshot`. It is intentionally not exposed as a public API route; the
protected ingestion orchestrator will call it after admin authentication exists.

Web acquisition permits public HTTP(S) text pages only. It validates and pins
every DNS destination, validates every redirect, rejects HTTPS downgrades, and
uses these defaults:

- 5 redirects
- 10 seconds for the complete acquisition
- 2 MB downloaded content
- 500,000 normalized text characters

The test suite injects fake resolvers and transports and never retrieves live
websites. Pasted text is labeled `pasted_text` and is not checked against the
live source URL.

## Requirement extraction

`app.extraction` provides the internal Feature 07 model boundary. The selected
OpenAI or Gemini adapter sends a saved source snapshot to its structured-output
API using the strict `ExtractedProgramDraft` schema. It does not accept student
profiles and cannot publish a revision. `app.extraction_validation.validate_extracted_draft`
then checks rule fields and operand types, exact evidence occurrence, snapshot
identity, coverage, deadlines, and application URLs before later orchestration
can place a proposal into admin review.

Set model keys only in the server or worker environment. Extraction supports
`PATHAID_EXTRACTION_PROVIDER=openai` and `gemini`; the matching key is
`OPENAI_API_KEY` or `GEMINI_API_KEY`. Configure the provider's model with
`PATHAID_EXTRACTION_MODEL`. Gemini uses the same strict schema, exact-evidence
validation, retry limits, and human approval boundary as OpenAI. Optional positive limits are
`PATHAID_EXTRACTION_TIMEOUT_SECONDS`,
`PATHAID_EXTRACTION_MAX_OUTPUT_TOKENS`, and
`PATHAID_EXTRACTION_MAX_SOURCE_CHARACTERS`. A missing key produces an explicit
configuration error; ordinary backend tests do not need a key or make model
calls.

The fixed synthetic dataset is `data/extraction_benchmark_v1.json`. Its 10
manually labeled cases cover scholarship GPA and scale boundaries, mandatory
criteria versus selection preferences, major and class-year restrictions,
closed cycles, missing deadlines, and unsupported conditions. The offline
suite validates the dataset and metric harness; live model measurements are a
separate budgeted command and have not been claimed.

## Ingestion worker

Feature 08 persists each workflow and its stage attempts in the database. A
run advances through acquisition, extraction, validation, and creation of an
unpublished catalog revision. Each successful stage is committed before the
next one begins, so a restarted worker reuses its source snapshot and stored
extraction instead of repeating completed external work.

Process at most one due stage from `backend/`:

```sh
.venv/bin/python -m app.worker --once
```

Omit `--once` for continuous polling. The default deployment uses one worker.
Database leases fence concurrent workers and allow recovery after expiration.
Transient acquisition or provider errors receive at most three attempts with
5- and 10-second delays. Unsafe input, refusal, missing credentials, and
invalid drafts stop for administrator action.

`PATHAID_WORKER_POLL_SECONDS`, `PATHAID_WORKER_LEASE_SECONDS`, and
`PATHAID_INGESTION_RETRY_BASE_SECONDS` control worker timing.
`PATHAID_INGESTION_MAX_ATTEMPTS` may lower the attempt limit but cannot exceed
three. The workflow currently stops at `awaiting_review`; protected review and
publication APIs then require the deployment-configured administrator.

## Scheduled scholarship discovery

Run one due scheduling batch from `backend/`:

```sh
.venv/bin/python -m app.scheduled_discovery --once
```

Without `--once`, the scheduler polls durable PostgreSQL schedules. It selects
at most one due source per host per cycle, creates one run per source/window,
checks safely acquired robots rules, and uses normalized content hashes to avoid
model calls for unchanged pages. Approved discovery pages may create private
candidate runs only for canonical links inside their configured host/path scope
and link limit. New and changed content still requires administrator approval.

Configure polling, batch size, and the identifiable robots user agent with
`PATHAID_SCHEDULER_POLL_SECONDS`, `PATHAID_SCHEDULER_BATCH_SIZE`, and
`PATHAID_SCHEDULER_USER_AGENT`.

## Administrator review

Feature 09 uses one administrator identity supplied through deployment
secrets. Generate an encoded password hash from `backend/` without saving the
plain password:

```sh
.venv/bin/python -c 'from app.main import password_hash; import getpass; print(password_hash(getpass.getpass("Admin password: ")))'
```

Set the result as `PATHAID_ADMIN_PASSWORD_HASH` and set the login identifier as
`PATHAID_ADMIN_EMAIL`. There is no administrator registration endpoint.
Administrator sessions use a separate HttpOnly cookie, rotate CSRF tokens,
expire after four hours, and are throttled by direct peer address.

Protected backend endpoints support:

- administrator login, session refresh, and logout;
- ingestion submission, listing, detail inspection, and manual retry;
- retained source text, extraction metadata, validation findings, and stage history;
- draft editing with deterministic rule and exact-evidence revalidation;
- revision history and copy-on-edit replacement drafts;
- explicit approval or rejection with an append-only review decision; and
- atomic publication of a valid revision without exposing drafts publicly.

Approval requires source-accuracy attestation and an explicit completeness
decision. A revision marked incomplete can publish only when its unsupported or
unresolved requirements remain recorded for conservative eligibility results.
The protected admin frontend is intentionally deferred until its source and
draft comparison screens have a wireframe.
