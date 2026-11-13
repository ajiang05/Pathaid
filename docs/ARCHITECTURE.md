# PathAid architecture

**Status:** Target architecture for the local-first redesign
**Last updated:** November 1, 2026

## 1. Architectural goals

PathAid runs for one user on one Mac. It automates scholarship discovery and
form preparation without hosting private student data or submitting an
application. The design prioritizes conservative matching, official evidence,
local privacy, recoverable background work, and explicit user control at the
application boundary.

## 2. System context

PathAid has four external boundaries:

- public scholarship pages and application portals;
- local Ollama/Qwen3 for structuring public requirements and separately
  controlled Gemini essay matching;
- Chrome, which hosts the application-copilot extension; and
- macOS Keychain, which protects local secrets.

Everything else runs locally. There is no account service, public catalog,
administrator, provider dashboard, or cloud database in the target MVP.

## 3. Runtime components

| Component | Responsibility | Trust boundary |
| --- | --- | --- |
| Next.js web app | Profile, discovery, details, saved list, sources, documents, settings | Local browser only |
| FastAPI service | Narrow local API and domain orchestration | Binds to `127.0.0.1` |
| SQLite | Profile, scholarships, source state, snapshots, jobs, mappings, statuses | Local app data directory |
| Scheduler/worker | Daily catch-up scheduling, acquisition, extraction, validation | Local process, durable jobs |
| Source adapters | Generic bounded directories, AcademicWorks, Kaleidoscope | Public approved URLs only |
| Local extraction | Qwen3 4B structured extraction through Ollama | Loopback only; public source text only |
| Matching engine | Pure deterministic Pass/Fail/Unknown evaluation and ranking | No model or network |
| Document vault | Encrypt/decrypt current résumé and transcript | Ciphertext on disk, key in Keychain |
| Essay service | Local essay bank and optional Gemini relevance analysis | Full text leaves device only when enabled |
| Chrome extension | Inspect, preview, fill, attach, and remember portal mappings | Active tab plus authenticated loopback API |
| macOS launcher | Start local services and trigger missed daily scan | Planned packaging boundary |

The backend may initially run the API, scheduler, and worker as separate local
processes during development. SQLite background writes must be short,
transactional, and serialized through durable job state; enable WAL mode and a
busy timeout. Do not hold a database transaction open during HTTP or model
calls.

The local API now starts a scheduler thread at launch. It creates one unique
daily catch-up job per due source, claims work through an expiring lease, and
commits acquisition, extracted model output, and activation separately.
Completed extraction artifacts are reused after restart, transient failures use
bounded backoff, and jobs for paused or policy-blocked sources are cancelled.

## 4. Data flow

### 4.1 Discovery

```text
approved source scope
  -> due schedule / launch catch-up
  -> robots + policy + scope checks
  -> bounded fetch and canonicalization
  -> content hash comparison
  -> local Ollama extraction only if changed
  -> record invalid local page and continue
  -> deterministic schema/evidence validation
  -> versioned scholarship record
  -> local deterministic matching
```

An unchanged normalized hash updates scan metadata but does not call a model.
Failures preserve the last valid record. Newly extracted data becomes active
only after deterministic validation; there is no human publication queue.

### 4.2 Manual lead

```text
user pastes listing URL/title
  -> store lead only
  -> user confirms candidate official sponsor URL
  -> acquire and validate official page
  -> retain immutable normalized evidence
  -> create scholarship record or mark unverifiable
```

BigFuture, Scholarship America, and Bold.org are lead sources, not initial
automatic crawling scopes. Aggregator prose cannot establish eligibility, and
an aggregator host cannot be confirmed as the official evidence URL.

### 4.3 Matching

```text
active scholarship version + local profile
  -> evaluate each hard requirement as pass/fail/unknown
  -> derive Strong/Possible/Not a match
  -> apply availability and section rules
  -> stable deterministic rank
```

Selection preferences are annotated separately. Gemini never receives the
profile or returns the eligibility label.

### 4.4 Application

```text
Apply in web app
  -> save In progress
  -> open approved official URL
  -> user opens side panel
  -> extension reads supported visible fields
  -> local API returns mapped values
  -> preview ordinary/sensitive/ambiguous fields
  -> user clicks Fill application
  -> extension fills supported values
  -> user explicitly attaches each file
  -> user reviews, certifies, and submits
```

The extension never clicks a submit, signature, attestation, certification,
terms, CAPTCHA, or MFA control.

## 5. Source acquisition design

### 5.1 Source registry

Each approved source stores:

- source type and adapter;
- canonical host and allowed path prefix;
- school/sponsor ownership;
- user-confirmed timestamp;
- scan interval, pause state, last/next scan;
- maximum depth, page count, and request rate;
- robots/policy outcome; and
- last success, error, and content change.

Changing school marks old school-specific sources inactive; it does not delete
history. The new school's proposed directory requires one-time confirmation.
Boundary confirmation does not authorize scanning by itself. The user records a
separate source-policy assessment; unknown or blocked policies cannot scan, and
each assessment is append-only evidence. Clearing a prohibition leaves the
source paused until an explicit resume.

### 5.2 Network safety

Acquisition accepts public HTTP(S) text pages only. Validate every resolved
address and redirect; block loopback, private, link-local, metadata, multicast,
and unsupported schemes. Pin validated destinations for the request, reject
HTTPS downgrade, cap redirects, bytes, time, and normalized characters, and do
not send local secrets or cookies.

### 5.3 Bounded traversal

The generic adapter follows only links that:

- remain on the approved host and path prefix;
- are within one or two configured levels;
- look scholarship-related by URL, title, or link text;
- fit the strict per-scan page budget; and
- are allowed by robots and source policy.

No adapter logs in, bypasses CAPTCHA, or uses browser automation to evade a
site's access controls. An explicit rule against bots/scripts disables scanning
for that target.

## 6. Extraction boundary

Qwen3 receives the retained public source text, canonical URL, retrieval time,
and a constrained response schema through Ollama on loopback. It never receives
the student profile. Scholarship extraction never calls Gemini. Invalid,
refused, or oversized local pages are recorded individually and do not stop the
remaining source. Output must pass the strict Pydantic and deterministic
evidence boundary.

The validator checks:

- schema and enum correctness;
- field/rule operand types;
- exact evidence occurrence in the snapshot;
- date/cycle consistency;
- official/application URL safety;
- hard requirement versus selection preference classification; and
- completeness/unsupported claim findings.

If validation cannot safely represent a mandatory condition, the scholarship is
not eligible for Strong results. A prior valid version remains available until
it expires or its official page becomes unavailable.

Every extraction produces an append-only activation attempt. Valid output
creates an immutable `ScholarshipVersion` and advances the stable
`Scholarship.active_version_id` in the same SQLite transaction. Invalid output
stores deterministic findings but cannot change that pointer. Replaying the same
snapshot and structured draft is idempotent.

## 7. Core data model

| Entity | Purpose |
| --- | --- |
| `Profile` | Singleton student profile and schema version |
| `ProfileExperience` | Activities, work, volunteering, memberships, leadership |
| `SourceScope` | User-approved host/path and adapter configuration |
| `SourceSnapshot` | Immutable acquired content/hash/provenance |
| `SourcePageState` | Current/disappeared presence for a URL within one approved scope |
| `ScanRun` | Durable scheduled/manual scan and outcome |
| `Scholarship` | Stable sponsor/award identity |
| `ScholarshipVersion` | Cycle-specific validated facts plus a material-change fingerprint |
| `ExtractionActivationAttempt` | Append-only activated/unchanged/failed validation outcome |
| `DiscoveryJob` | Daily/manual window, stage, retry state, and worker lease |
| `DiscoveryExtractionArtifact` | Persisted provider result used by resumable activation |
| `Requirement` | Typed hard criterion with evidence |
| `SelectionPreference` | Non-eligibility factor with evidence |
| `SavedScholarship` | Not started/In progress/Already applied state |
| `SkippedScholarship` | Stable ID plus material fingerprint used to decide reappearance |
| `Essay` | Student-authored content, prompt, tags, themes, and word count |
| `EssayUse` | Prior scholarship reuse history for one essay |
| `Document` | Encrypted-file metadata, type, hash, and current flag |
| `PortalMapping` | User-corrected field mapping scoped by portal/form signature |
| `AppSetting` | Non-secret local settings and schema version |

Do not store Gemini keys, document keys, portal passwords, browser cookies, or
MFA secrets in SQLite.

## 8. Matching semantics

Rules are pure data evaluated by a pure engine. Operators include typed equality,
membership, numeric/date range, boolean, location relationships, and structured
experience predicates. Every operator must define missing-data behavior.

- any hard Fail -> Not a match;
- no Fail plus any Unknown -> Possible;
- every hard requirement Pass -> Strong.

Availability gates visibility after eligibility: verified open results appear;
future cycles may appear only in an explicit upcoming section if added later;
closed, expired, unknown/unverifiable, and disappeared sources do not appear in
current matches. Stable IDs break ties so repeated runs are reproducible.

Presence is reconciled only after a complete bounded traversal. A truncated or
transiently failed scan preserves the last known state; a confirmed missing page
marks the stable scholarship inactive while retaining snapshots and immutable
versions. Reappearance restores the retained active version even when the page
bytes are unchanged. Deadline visibility is calculated at read time, including
the sponsor timezone for date-only deadlines. Material fingerprints include
cycle, deadline, availability, award, and eligibility semantics but exclude
marketing copy and evidence-capture metadata.

Extraction schema 1.1 explicitly classifies `separate_application`,
`automatically_considered`, or `sweepstakes`. Special classifications require
verbatim retained evidence, and sweepstakes additionally require a safe public
official-rules URL with evidence. Matching preserves deterministic order while
routing current results into distinct response sections. Automatically
considered records cannot receive a saved application status.

## 9. Extension architecture

The Manifest V3 extension uses:

- a service worker for commands and local connection state;
- a side panel for preview, warnings, and user actions;
- an on-demand content script injected only after user activation;
- `activeTab`, `scripting`, `sidePanel`, storage, and loopback host permission;
  and
- portal adapters behind a common field-inspection/fill interface.

An installation-specific high-entropy token authenticates requests to narrow
`/api/extension/*` endpoints. Validate the extension origin, token, scholarship
context, target portal origin, and request schema. Do not expose the general app
API through permissive CORS. Native messaging may replace loopback HTTP later.

Field mapping precedence is portal-specific learned mapping, safe normalized
label mapping, then known semantic attributes. Never infer a value when multiple
profile fields are plausible. Preview displays the source profile field and
marks sensitive values. Filling changes fields only; submission is impossible
through the adapter API.

The implemented foundation uses an unpacked MV3 service worker and side panel.
It requests only `activeTab`, `scripting`, `sidePanel`, `storage`, and the exact
`http://127.0.0.1:8000/*` host. The extension token is copied from Keychain to
Chrome without terminal output, stored only in extension-local storage, and
omitted from messages returned to the panel. No persistent content script is
registered; the current page probe runs only after explicit user activation and
returns only origin and form count.

Before inspection can advance, `/api/extension/context` validates the exact
public portal origin against the active application URL of an **In progress**
saved scholarship. No match is unsupported and multiple matches are ambiguous;
neither state releases profile data. The adapter interface exposes only
`matches`, `inspect`, and `map`. A central validator—not a portal adapter—builds
future fill plans from visible, supported, exact, explicitly approved mappings.
Attachments remain a separate explicit-action contract.

For generic forms, the on-demand isolated runtime records opaque references to
visible value-bearing controls and returns metadata without current field
values. The authenticated profile-values endpoint returns known fields only,
uses `Cache-Control: no-store`, and requires the same scholarship/origin
context. Exact mappings are previewed in the side panel, with sensitive values
marked; ambiguous and unknown mappings are excluded. Approved plans remain only
in service-worker memory, expire after 15 minutes, and are revalidated against
the active tab and backend context before value/input/change operations. The
runtime never clicks any element or submits a form.

AcademicWorks/Blackbaud uses the same isolated runtime and central fill-plan
validator. Its dedicated mapper recognizes only a narrow set of exact common
Award Management questions and applies explicit yes/no translations for fields
such as full-time enrollment. Since each institution defines its own General
Application, custom questions and essays remain untouched unless a later learned
mapping has been reviewed by the student.

Kaleidoscope uses the same contract and runtime with a separate exact-question
mapper. It deliberately distinguishes the saved current college from a sponsor's
future or first-choice college question and refuses to infer the latter.

Reviewed mapping corrections persist in `PortalMapping`, scoped by canonical
portal origin, a SHA-256 form-metadata signature, and a SHA-256 field-metadata
signature. Signatures contain control type, normalized label/name/autocomplete,
required state, and stable order, but no current form answer or profile value.
The extension retrieves and updates them only after repeating the authenticated
In-progress scholarship/origin check. A changed form shape does not inherit an
older mapping.

Extraction schema 1.2 records distinct automation and AI-assistance policy
flags. A blocked flag must quote retained evidence and pass deterministic
explicit-prohibition matching. The extension context checks the active immutable
version before inspection; a blocked automation policy returns only a safe
reason and releases no profile values or learned mappings.

Apply integration uses `externally_connectable` only for the two fixed local web
origins. The web page sends a scholarship ID, never a destination URL. The
extension creates an owned blank tab and opens the panel, while an authenticated
backend preparation endpoint changes the saved state to In progress and returns
the retained official URL for navigation. This prevents the local page from
turning the extension into an arbitrary URL opener.

## 10. Documents, essays, and secrets

Generate a random document-encryption key and store it through macOS Keychain.
Keep encrypted document bytes in the app data directory. Decrypt only for an
explicit attachment action and clean temporary plaintext promptly. One current
résumé and transcript are supported.

The implemented vault uses AES-256-GCM with a random nonce for every managed
copy. SQLite stores only non-secret metadata; ciphertext files live in the
private `documents/` app-data directory and are excluded from SQLite backup.
The extension requests plaintext over its authenticated loopback boundary only
after a dedicated attachment click, transfers it directly to one exact inspected
PDF file control, clears its worker byte buffer, and never writes a plaintext
temporary file. Student essays remain SQLite text. For an exact essay-file
control, the side panel requires the user to choose one essay and click Attach;
the loopback API then releases a plain-text copy for that request only.

Essays remain local except when the user enables Gemini analysis, acknowledges
the configured tier's data-handling notice, and rules allow it. Local metadata
matching always runs first. The provider schema permits only ranking rationale
and mismatch references; it cannot return replacement prose. Provider failure
falls back to the local result without blocking the application workflow.

## 11. Backup and reset

Backups are encrypted and versioned. Include profile, scholarship/source data,
essay bank, saved status, and portal mappings. Exclude document bytes, Gemini
key, document key, portal credentials, and browser data. Restore into a temporary
database, validate version/integrity, and replace only after success.

A factory reset is destructive and requires explicit confirmation. It removes
the SQLite database and encrypted document files and deletes PathAid Keychain
items. Development data from the legacy PostgreSQL database is disposable;
useful source URLs may be converted into reviewed seed records.

## 12. Deployment model

MVP development may use separate native processes or Docker for reproducibility,
but the product runtime is local and does not require PostgreSQL, Caddy, or a
hosted server. The eventual macOS launcher starts the API/web/worker, opens the
web interface, and runs one catch-up scheduling check.

All schema changes use Alembic. CI runs migrations against fresh SQLite, backend
tests without live model calls, frontend checks, extension checks, and fixture
contracts for each adapter.

## 13. Legacy migration

Reuse after review:

- safe source acquisition and immutable snapshots;
- local Ollama provider abstraction and strict extraction validation;
- deterministic eligibility/ranking concepts;
- durable job/lease concepts, simplified for local SQLite;
- health checks, tests, and accessible UI primitives.

Remove or replace:

- student/admin authentication and CSRF session flows;
- reviewer attestations, draft approval, and publication revisions;
- PostgreSQL-only coordination, Caddy, and hosted deployment;
- public catalog export/import and launch-review gates;
- multi-user rate limits and account deletion flows.

The migration order and implementation status live in [../plan.md](../plan.md).
