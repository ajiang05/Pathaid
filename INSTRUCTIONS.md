# PathAid local setup and command guide

## Run PathAid locally

Open Terminal and run these commands from the repository:

```bash
cd /Users/aidanjiang/Documents/GitHub/Pathaid

# First-time setup, or after dependency/build changes:
scripts/pathaid bootstrap

# Start the backend, scheduler, and frontend:
scripts/pathaid start
```

Then open [http://127.0.0.1:3000](http://127.0.0.1:3000) in your browser.
Keep PathAid running while you use the website or Chrome extension. You do not
need to run separate FastAPI, Next.js, Alembic, or Docker commands.

For later sessions, you normally only need:

```bash
cd /Users/aidanjiang/Documents/GitHub/Pathaid
scripts/pathaid start
```

Check or stop the application with:

```bash
scripts/pathaid status
scripts/pathaid stop
```

If startup reports that port `3000` or `8000` is already in use, another
PathAid/Docker process is already running. Check it before starting a second
copy:

```bash
scripts/pathaid status
docker ps
```

PathAid provides a local macOS backend, private profile, automated discovery,
matching, saved workflow, document/essay library, and authenticated Chrome side
panel. Consult [plan.md](plan.md) for authoritative release status.

## Prerequisites

- macOS
- Git
- Python 3.14
- Node.js 22 and npm
- Google Chrome for the unpacked extension
- Ollama with the local `qwen3:4b` model

PostgreSQL, Caddy, administrator credentials, and a hosted domain are no longer
required.

## One-command bootstrap and launcher

From the repository root:

```bash
scripts/pathaid bootstrap
scripts/pathaid start
```

Bootstrap creates `backend/.venv`, installs locked project dependency ranges,
installs/builds the frontend, migrates SQLite, and creates installation/document
keys in macOS Keychain without printing them. Start binds both services to
loopback and immediately performs the scheduler's due-scan catch-up check.

Useful launcher commands:

```bash
scripts/pathaid status
scripts/pathaid stop
scripts/pathaid set-gemini-key
scripts/pathaid backup /absolute/path/pathaid.pathaid-backup
scripts/pathaid restore /absolute/path/pathaid.pathaid-backup
scripts/pathaid reset
```

By default, local data is placed under:

```text
~/Library/Application Support/PathAid/
```

## Load the Chrome extension

1. Open `chrome://extensions` in Chrome.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this repository's `extension/` folder.
4. Copy the extension ID shown by Chrome.
5. Save that exact ID so the API accepts only this extension, then restart:

```bash
scripts/pathaid configure-extension PASTE_THE_32_CHARACTER_EXTENSION_ID
scripts/pathaid stop
scripts/pathaid start
```

In another terminal, copy the installation token from Keychain directly to the
macOS clipboard. The command deliberately does not print the token:

```bash
scripts/pathaid copy-extension-token
```

Click the PathAid toolbar icon, paste the token into the side panel, and select
**Connect**. After pasting, replace the clipboard contents with something
non-sensitive. The token stays in Chrome's extension-local storage and is sent
only to `http://127.0.0.1:8000/api/extension/*`. If the extension ID changes,
restart the backend with the new ID; requests from any other origin fail closed.

## Gemini key

Scholarship extraction uses local Ollama by default. Install Ollama globally,
open the macOS application, and download the model from any directory:

```bash
ollama pull qwen3:4b
ollama list
```

Keep Ollama running during source extraction. PathAid connects only to
`http://127.0.0.1:11434`, disables model thinking, requests constrained JSON,
and validates every draft deterministically. `ollama_unavailable` means the
application is closed; `ollama_model_missing` means `qwen3:4b` is not installed.

### Optional Gemini essay analysis

Save or replace the personal Gemini key without putting it in `.env`:

```bash
scripts/pathaid set-gemini-key
```

The prompt hides input. The key is stored under the Keychain service
`com.pathaid.local`. It is used only for separately controlled essay analysis;
automated scholarship extraction always uses local Ollama.

## Import the U.S. institution directory

PathAid selects schools from the authoritative NCES IPEDS directory rather
than maintaining a hand-written school list. Download the latest **Directory
information (HD)** CSV ZIP from the [IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?gotoReportId=7),
extract its CSV, and import it with the matching collection year:

```bash
cd backend
.venv/bin/python -m app.local_admin import-institutions /absolute/path/HD2025.csv --year 2025
```

The import is local, repeatable, and does not require a paid API key. It stores
only institution identity, aliases, city/state, official website, dataset year,
and import time. A newer HD file safely updates matching Unit IDs.

## Run one confirmed source

The Sources screen queues **Scan now** for the running local scheduler. For a
one-cycle diagnostic while the API is stopped, use:

```bash
cd backend
.venv/bin/python -m app.local_admin scheduler-once
```

The scan checks `robots.txt`, exact host/path approval, depth, page budget, and
request rate. It follows only scholarship-related links and stores immutable
normalized snapshots. A failed scan records a safe error code and retains every
previous valid snapshot.

Before the first scan, confirm the boundary and record an automation-policy
review on **Sources**. Select **No explicit prohibition found** only after
reviewing the relevant official rules. If automation is explicitly prohibited,
record the official policy URL and exact text; PathAid clears queued work and
blocks the source. Clearing that decision leaves the source paused until you
explicitly resume it.

The FastAPI process starts the local scheduler automatically. On launch it
queues one catch-up window for each overdue active source, then checks for new
work once per minute while the app remains open. **Scan now** creates a durable
manual request that the same scheduler claims.

To run one scheduler cycle manually while debugging:

```bash
cd backend
.venv/bin/python -m app.local_admin scheduler-once
```

The command performs due acquisition, local Ollama extraction, deterministic
validation, and activation. A Gemini key is not required. Invalid local pages
are recorded individually while remaining pages continue. Completed stages
persist, so a later cycle resumes rather than repeating successful model work.

For AcademicWorks/Blackbaud, confirm the root path (`/`) because public listings
may move between `/opportunities` and `/?page=N`. The adapter still follows only
public listing pagination and numeric `/opportunities/{id}` detail pages; it
never follows sign-in, application, or external-opportunity routes.

For Kaleidoscope, register `https://apply.mykaleidoscope.com/` with the root
path (`/`) as a sponsor source. The adapter follows only public
`/program/{slug}` summaries from the marketplace. It never follows account,
login, application-form, asset, or off-host routes.

## Verify a manual lead

On **Sources**, save the individual BigFuture, Scholarship America, Bold.org,
or other lead URL. Find the scholarship's current sponsor page, paste that URL
under the saved lead, and select **Verify official page**. PathAid checks
`robots.txt`, rejects aggregator hosts as official evidence, fetches only that
page with same-host redirects, and stores a new immutable snapshot only when
the normalized content changes. Verification does not authorize a domain crawl.

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

Stop the API before restore. Create a versioned encrypted recovery backup. The
command prompts twice for a new passphrase of at least 12 characters:

```bash
cd backend
.venv/bin/python -m app.local_admin backup /absolute/path/pathaid-backup.pathaid-backup
```

The command refuses to overwrite an existing file. Restore prompts for that
passphrase, authenticates the archive, and validates it before replacing SQLite:

```bash
.venv/bin/python -m app.local_admin restore /absolute/path/pathaid-backup.pathaid-backup
.venv/bin/python -m app.local_admin status
```

The backup includes the profile, scholarship/source history, essay bank, saved
status, and portal mappings. It excludes macOS Keychain secrets, résumé and
transcript ciphertext, browser data, portal credentials, and caches. Losing the
backup passphrase makes the archive unrecoverable.

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
