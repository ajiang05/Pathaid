# Pathaid backend

The first feature provides student sign-up, login/logout, editable profiles, account deletion, and profile-field metadata. It has no frontend. Scholarship evaluation and recommendation generation are later features.

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
  ranked outcomes. Temporary answers are not persisted.

All profile fields remain optional. The account opt-in flag is stored but no student data is sent to OpenAI in this feature. Passwords are hashed with scrypt; session and CSRF tokens are stored as SHA-256 hashes. The rate limit uses the direct peer address and is shared through the database. Behind a reverse proxy, configure a trusted peer address policy before public deployment.

Run tests with `.venv/bin/pytest -q`.

Both pytest and Alembic are configured to treat `backend/` as the Python
package root, so the commands above work without setting `PYTHONPATH`.

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

`app.extraction.OpenAIExtractionAdapter` is the internal Feature 07 model
boundary. It sends a saved source snapshot to the Responses API using the
strict `ExtractedProgramDraft` schema. It does not accept student profiles and
cannot publish a revision. `app.extraction_validation.validate_extracted_draft`
then checks rule fields and operand types, exact evidence occurrence, snapshot
identity, coverage, deadlines, and application URLs before later orchestration
can place a proposal into admin review.

Set `OPENAI_API_KEY` only in the server or worker environment. The extraction
model defaults to `gpt-6-luna` and can be changed with
`PATHAID_EXTRACTION_MODEL`. Optional positive limits are
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
