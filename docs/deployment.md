# Pathaid deployment and recovery

This guide covers the implemented local deployment and the remaining hosted
release work. The Next.js student and administrator interface, API, worker,
scheduler, migrations, and PostgreSQL run in Compose. A public hosted demo and
hosted external-source verification have not yet been completed. A controlled
local cycle against an official scholarship page verified changed-content
review and unchanged-content model skipping.

## Local Docker setup

Requirements: Docker Engine with Docker Compose v2.

1. Copy the environment template and replace the local database password:

   ```sh
   cp .env.example .env
   ```

2. Generate the administrator password hash from an existing backend virtual
   environment. The password is read without echoing it:

   ```sh
   cd backend
   .venv/bin/python -c 'from app.main import password_hash; import getpass; print(password_hash(getpass.getpass("Admin password: ")))' 
   ```

3. Put the result in `PATHAID_ADMIN_PASSWORD_HASH` in the root `.env`, wrapped
   in single quotes so Compose treats the scrypt `$` separators literally, return
   to the repository root, and configure Gemini for extraction and optional
   recommendation assistance. Keep the actual key only in this uncommitted file:

   ```dotenv
   PATHAID_ADMIN_PASSWORD_HASH='scrypt$16384$8$1$...'
   GEMINI_API_KEY=replace-with-your-gemini-key
   PATHAID_EXTRACTION_PROVIDER=gemini
   PATHAID_EXTRACTION_MODEL=gemini-3.5-flash-lite
   PATHAID_RECOMMENDATION_PROVIDER=gemini
   PATHAID_RECOMMENDATION_MODEL=gemini-3.5-flash-lite
   ```

4. Start the private database, migration job, API, worker, and scheduler:

   ```sh
   docker compose up --build --detach
   docker compose ps
   ```

5. Check the API process and migrated database:

   ```sh
   curl --fail http://localhost:8000/health/live
   curl --fail http://localhost:8000/health/ready
   ```

Only the frontend and API bind host ports, and both bind to loopback. PostgreSQL,
the worker, and the scheduler remain on the private Compose network. Student matching and template
recommendations work without an AI provider key. An ingestion run that reaches
extraction without a key records an explicit configuration failure for admin
review.

Stop services without deleting the database with `docker compose down`.
Deleting the `postgres-data` volume permanently removes local application data.

## Single-server hosted topology

The production Compose overlay adds Caddy 2.11.4 as the only public service.
Caddy binds ports 80 and 443, obtains and renews the certificate for
`PATHAID_HOSTNAME`, adds conservative browser security headers, and proxies to
the private Next.js service. Next.js continues to proxy `/api` to FastAPI, so
student and administrator cookies remain same-origin. Proxy access logging is
not enabled because raw paths are unnecessary for the portfolio beta.

Before starting the hosted stack:

1. Point the hostname's DNS A/AAAA records to the server.
2. Copy `.env.example` to a server-only `.env` and replace every placeholder.
3. Set these production values, keeping the proxy CIDR equal to the Compose
   subnet:

   ```dotenv
   PATHAID_HOSTNAME=pathaid.example.com
   PATHAID_PUBLIC_ORIGIN=https://pathaid.example.com
   PATHAID_SECURE_COOKIES=true
   PATHAID_DOCKER_SUBNET=172.30.0.0/24
   PATHAID_TRUSTED_PROXY_CIDRS=172.30.0.0/24
   ```

4. Validate and start both Compose files:

   ```sh
   docker compose --project-name pathaid-production -f compose.yaml -f compose.production.yaml config --quiet
   docker compose --project-name pathaid-production -f compose.yaml -f compose.production.yaml up --build --detach
   docker compose --project-name pathaid-production -f compose.yaml -f compose.production.yaml ps
   ```

The API trusts `X-Forwarded-For` only when its direct peer belongs to
`PATHAID_TRUSTED_PROXY_CIDRS`. Direct deployments and malformed forwarding
chains fall back to the socket peer, preventing clients from choosing their
own authentication throttle identity. Do not use a public network in that
setting.

## Migrations

Compose runs `alembic upgrade head` as a one-shot dependency before starting
the API and worker. For an existing environment:

```sh
docker compose run --rm migrate
```

`/health/ready` returns HTTP 503 when the database cannot be reached or does
not have the migration expected by this application release. Apply migrations
before shifting traffic to a new API version.

## Reviewed catalog bundles

Catalog bundles contain official source text and reviewer identity. Store them
as controlled operational artifacts and inspect them before sharing. They do
not include student accounts, profiles, sessions, ingestion inputs, or drafts.

Export only current publications that already retain one approval event:

```sh
docker compose exec api python -m app.catalog_seed export /tmp/reviewed-catalog.json
docker compose cp api:/tmp/reviewed-catalog.json ./reviewed-catalog.json
```

Import into another migrated deployment:

```sh
docker compose cp ./reviewed-catalog.json api:/tmp/reviewed-catalog.json
docker compose exec api python -m app.catalog_seed import /tmp/reviewed-catalog.json
```

Import is atomic and idempotent. It rejects ID conflicts, unapproved records,
invalid rules, and evidence excerpts absent from the retained source. No seed
command generates an approval event. The initial 10–20 real programs still
require official-source curation and manual administrator approval.

## PostgreSQL backup and restore

Database backups contain credentials, student profiles, retained source text,
and administrator review history. Encrypt them at rest, limit access, and do
not commit them.

Create a compressed backup on the host:

```sh
docker compose exec -T database sh -c \
  'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
  > pathaid.dump
```

Restore into an empty database during a maintenance window:

```sh
docker compose stop api worker
docker compose exec -T database sh -c \
  'dropdb --username "$POSTGRES_USER" --maintenance-db postgres --if-exists "$POSTGRES_DB"'
docker compose exec -T database sh -c \
  'createdb --username "$POSTGRES_USER" --maintenance-db postgres "$POSTGRES_DB"'
docker compose exec -T database sh -c \
  'pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --clean --if-exists' \
  < pathaid.dump
docker compose run --rm migrate
docker compose start api worker
curl --fail http://localhost:8000/health/ready
```

Practice restore on a separate database before relying on a backup for launch.

## Logging and operational signals

Uvicorn access logs are disabled in the production image. The API emits one
structured `api_request` event containing only the HTTP method, route template,
status, and latency. It does not emit raw paths, query strings, headers, cookies,
request bodies, response bodies, profile values, prompts, or retained sources.

An authenticated administrator can read aggregate signals at
`GET /api/admin/operations/summary`. The response contains failed ingestion
count, recommendation attempt/failure counts and average latency for the last
24 hours, and the oldest publication verification timestamp. Recommendation
records contain aggregate token counts and latency without prompts or generated
explanations.

The operations summary includes scheduled scan success/failure, overdue
sources, changed sources, candidates, and review backlog. Logs must not contain
discovered page bodies or link lists.

## Daily scheduler

The scheduler runs as a private service from the backend image. PostgreSQL
will store source definitions, next due times, scheduled-window claims, hashes,
and outcomes so a restart does not lose the schedule. It creates idempotent work
for the existing ingestion worker and never publishes content directly.

Before external scheduling is enabled:

- configure each source's first morning due time, cadence, scheduler cycle interval, and link budget;
- register only reviewed pages with explicit host/path scope;
- validate robots behavior and source terms;
- run a controlled scheduled window using fake or owned sources;
- verify unchanged pages make no model call;
- verify material changes remain private until approval; and
- alert on overdue sources, repeated failures, and review backlog.

Forward structured application output to the selected hosting platform's log
collector only after its request capture and retention settings are reviewed.

## Production security checklist

- Terminate TLS at Caddy (or an equivalent managed proxy) and set `PATHAID_SECURE_COOKIES=true`.
- Set `PATHAID_PUBLIC_ORIGIN` to the exact HTTPS frontend origin.
- Route browser `/api` traffic through the same origin; the API does not enable
  broad cross-origin access.
- Keep PostgreSQL, the worker, scheduler, and API on private networks or loopback with no public ports.
- Store database, administrator, AI provider, and telemetry credentials in the
  hosting provider's secret store.
- Disable proxy request-body capture and redact cookies and authorization
  headers.
- Rotate secrets after suspected disclosure and revoke database sessions when
  rotating administrator credentials.
- Verify a backup restore, migrations, health checks, and protected admin
  endpoints before launch.

## Pending release work

- Choose hosting only after checking current prices against the $25/month cap.
- Select and configure the hosted same-origin TLS edge for the implemented Next.js and API services.
- Repeat the locally verified external-source scheduled window in the hosted environment and verify its alerts before launch.
- Curate and manually approve 10–20 official programs before exporting seed data.
- Verify HTTPS, private networking, PostgreSQL concurrency, telemetry redaction,
  and backup restoration in the selected deployed environment.
- Complete browser checks and five observed student usability sessions.

Do not describe the hosted demo, live model measurements, or human catalog
review as complete until those actions have actually occurred.
