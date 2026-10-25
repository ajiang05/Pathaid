# Pathaid setup and command guide

This is the practical setup and operations guide for local development. Run
commands from the repository root unless a section says otherwise. The system
design is illustrated in [the architecture diagrams](docs/ARCHITECTURE_DIAGRAM.md).

## Prerequisites

- Docker Desktop with Docker Compose v2
- Git
- Node.js and npm when running the frontend outside Docker
- Python 3.14 when running the backend outside Docker
- A Gemini key only for live extraction or optional AI-assisted explanations

Never commit `.env`, database dumps, API keys, plain-text passwords, session
cookies, or exported catalog bundles containing retained source text.

## Recommended setup: Docker Compose

Docker runs PostgreSQL, migrations, FastAPI, the ingestion worker, the daily
scheduler, and Next.js together. You do not activate the Python virtual
environment for this approach.

1. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` and replace at least these values:

   ```dotenv
   POSTGRES_DB=pathaid
   POSTGRES_USER=pathaid
   POSTGRES_PASSWORD=choose-a-long-random-local-password
   PATHAID_ADMIN_EMAIL=your-admin-email@example.com
   PATHAID_ADMIN_PASSWORD_HASH='scrypt$...'
   PATHAID_PUBLIC_ORIGIN=http://localhost:3000
   PATHAID_SECURE_COOKIES=false
   ```

3. If using Gemini, also set:

   ```dotenv
   GEMINI_API_KEY=your-key
   PATHAID_EXTRACTION_PROVIDER=gemini
   PATHAID_EXTRACTION_MODEL=gemini-3.5-flash-lite
   PATHAID_RECOMMENDATION_PROVIDER=gemini
   PATHAID_RECOMMENDATION_MODEL=gemini-3.5-flash-lite
   ```

4. Start or rebuild the complete stack:

   ```bash
   docker compose up --build --detach
   docker compose ps
   ```

5. Open the application:

   - Student interface: <http://localhost:3000>
   - Administrator login: <http://localhost:3000/admin/login>
   - API liveness: <http://localhost:8000/health/live>
   - API readiness: <http://localhost:8000/health/ready>

`{"status":"live"}` means the API process is running. `{"status":"ready"}`
also confirms that PostgreSQL is reachable and migrated.

## Administrator password setup or reset

The password hash is stored in `.env`; the plain password is not. From the
repository root:

```bash
cd backend
.venv/bin/python -c 'from app.main import password_hash; import getpass; print(password_hash(getpass.getpass("New admin password: ")))'
```

When the prompt appears, type the password and press Enter. Nothing is shown
while you type. Copy the entire output, including the `scrypt$` prefix, into the
root `.env` file and keep single quotes around it:

```dotenv
PATHAID_ADMIN_PASSWORD_HASH='scrypt$16384$8$1$...'
```

Then reload the API configuration:

```bash
cd ..
docker compose up --detach --force-recreate api
```

Log in with `PATHAID_ADMIN_EMAIL` and the plain password you typed—not the
`scrypt$...` value. `KeyboardInterrupt` at the password prompt means the command
was cancelled, usually with Ctrl+C; run it again.

## Everyday Docker commands

```bash
# Show service state
docker compose ps

# Follow all logs or one service
docker compose logs --follow
docker compose logs --follow api
docker compose logs --follow worker
docker compose logs --follow scheduler

# Restart one service
docker compose restart api

# Rebuild after code or dependency changes
docker compose up --build --detach

# Stop containers but preserve PostgreSQL data
docker compose down
```

Do not add `--volumes` to `docker compose down` unless you intentionally want
to delete the local database.

## Database migrations

Alembic applies ordered, version-controlled schema changes. Compose normally
runs it automatically before the API and worker start.

```bash
# Apply pending migrations through Docker
docker compose run --rm migrate

# Show the migration stored in PostgreSQL
docker compose exec database sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT * FROM alembic_version;"'
```

For native backend development from `backend/`:

```bash
.venv/bin/alembic upgrade head
```

Create migrations only for deliberate model/schema changes, review them before
running them, and never edit an already deployed migration.

## Backend development without Docker

Use the virtual environment inside `backend/`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./pathaid.db
alembic upgrade head
uvicorn app.main:app --reload
```

The prompt prefix `(.venv)` means the environment is active. If port 8000 is
already in use, the Docker API may already be running. Either use Docker and
skip `uvicorn`, stop it with `docker compose stop api`, or choose another port:

```bash
uvicorn app.main:app --reload --port 8001
```

## Frontend development without Docker

Start the backend first, then use another terminal:

```bash
cd frontend
npm install
npm run dev
```

If Docker already runs the frontend on port 3000, stop it first:

```bash
docker compose stop frontend
```

## Tests and quality checks

```bash
# Backend tests and offline quality report
cd backend
.venv/bin/pytest -q
.venv/bin/python -m app.quality_report

# Frontend lint, production build, browser, and accessibility checks
cd ../frontend
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The test configuration adds `backend/` to Python's import path, so
`PYTHONPATH=.` should not be necessary.

## Ingestion and scheduled discovery

With Docker, the worker and scheduler run continuously. Usually you should let
those services work normally. To step through work manually, stop the relevant
continuous service first, run one temporary process, and start it again:

```bash
docker compose stop worker
docker compose run --rm worker python -m app.worker --once
docker compose start worker

docker compose stop scheduler
docker compose run --rm scheduler python -m app.scheduled_discovery --once
docker compose start scheduler
```

The worker acquires official content, asks Gemini for a structured proposal,
validates it, and stops at private administrator review. It never publishes
automatically. An unchanged scheduled page skips Gemini.

Validate or queue the versioned launch intake from `backend/`:

```bash
.venv/bin/python -m app.catalog_intake validate
.venv/bin/python -m app.catalog_intake queue --entry gates-scholarship
.venv/bin/python -m app.catalog_intake queue
```

The queue command is idempotent and does not approve anything.

## Reviewing and publishing catalog drafts

1. Start the stack and sign in at <http://localhost:3000/admin/login>.
2. Open **Ingestion** and filter to **Awaiting review**.
3. Open a draft and compare every field and evidence excerpt with the retained
   official source.
4. Correct the draft and save it to rerun deterministic validation.
5. Check the source-accuracy attestation only after personally verifying it.
6. Mark coverage complete only when no unsupported or unresolved requirement
   remains; otherwise publish conservatively with incomplete coverage.
7. Approve or reject the revision.

The current launch-candidate decisions and replacement revision IDs are in
[the catalog review record](docs/CATALOG_REVIEW.md). AI output and validation
do not substitute for the administrator's attestation.

After reviewed programs are published, export the portable catalog bundle:

```bash
docker compose exec api python -m app.catalog_seed export /tmp/reviewed-catalog.json
docker compose cp api:/tmp/reviewed-catalog.json ./reviewed-catalog.json
```

The bundle contains retained source text and reviewer identity. Keep it private
and do not commit it without an explicit repository policy.

## PostgreSQL backup

Create a custom-format backup from the repository root:

```bash
docker compose exec -T database sh -c \
  'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
  > pathaid.dump
```

The dump contains accounts, password hashes, profiles, source text, and review
history. Encrypt it, restrict access, and never commit it. Restore procedures
and production safety checks are in [the deployment guide](docs/deployment.md).

## Git workflow

Before committing:

```bash
git status --short
git diff --check
```

Stage only related files and use a focused commit message:

```bash
git add path/to/related-file
git commit -m "type(scope): describe the change"
git push -u origin your-branch-name
```

Common types are `feat`, `fix`, `test`, `docs`, and `chore`. Avoid combining
unrelated changes merely to make one large commit.

## Troubleshooting

### Compose reports missing PostgreSQL variables

Run Compose from the repository root and confirm that `.env` exists there with
nonempty `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` values.

### `Address already in use`

Another process already owns the port—commonly the Docker API on 8000 or
frontend on 3000. Check `docker compose ps`; do not run a duplicate native
server unless you stop the corresponding container or choose another port.

### `ModuleNotFoundError: No module named 'app'`

Run backend commands from `backend/` using its virtual environment, for example:

```bash
cd backend
.venv/bin/pytest -q
```

### Docker changes do not appear

Docker images contain copied source code. Rebuild the affected services:

```bash
docker compose up --build --detach
```

### Admin login still rejects the new password

Confirm that the complete hash is single-quoted in the root `.env`, the login
email exactly matches `PATHAID_ADMIN_EMAIL`, and the API was force-recreated.
Never enter the hash itself in the browser password field.

### Check service health and recent errors

```bash
docker compose ps
docker compose logs --tail 100 api
docker compose logs --tail 100 worker
docker compose logs --tail 100 scheduler
```

For production TLS, networking, backup restoration, and catalog transfer, use
[the deployment guide](docs/deployment.md).
