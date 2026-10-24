# Reproducible local setup and hosted demo

Status: complete local Compose stack implemented; reviewed catalog, external observability integration, paid hosting, and hosted verification remain pending. Parent specification: [plan.md](../plan.md).

## Implementation status
- A non-root production backend image runs the API, worker, or migration command. Docker Compose keeps PostgreSQL and the worker private and starts the API only after a successful migration.
- Liveness and migration-aware readiness endpoints support container and hosting checks.
- Versioned export/import tooling transfers only current publications with preserved approval events and exact retained evidence; it never creates review events.
- Structured API events contain route templates, status, and latency without paths, query strings, bodies, credentials, profile values, prompts, or source text. Protected aggregate operations data covers failed ingestion, recommendation outcomes/latency, and oldest publication verification.
- Environment templates and operations documentation cover secrets, local startup, migrations, reviewed catalog transfer, PostgreSQL backup/restore, and production security requirements.
- CI builds the production image, validates Compose, applies PostgreSQL migrations, checks model drift, runs tests, and reports offline quality measurements.
- The Next.js service is implemented and runs in local Compose. No hosting provider has been selected or provisioned, no real seed bundle has been approved, and deployed backup/telemetry checks have not been claimed.

## Goal
Make the student flow and protected administration usable locally and in a small hosted portfolio demo.

## Scope and behavior
- Provide Docker Compose services for Next.js, FastAPI, the worker, scheduler, and PostgreSQL, with migrations and an explicit seed command. All local services are implemented.
- Provide `.env.example`, secret configuration, setup, backup/restore, health/readiness, and deployment instructions.
- Student sign-up, saved profiles, and matching work with reviewed seed data and no AI key. Recommendation explanations fall back to templates; ingestion reports missing configuration clearly.
- Target $25/month total hosting/API usage; verify current service prices before provider selection or provisioning.
- Serve through HTTPS, restrict allowed origins, keep database/worker private, and omit request bodies from proxy/application logs.
- Integrate an observability tool for frontend/API errors, request latency, recommendation model latency and failures, failed ingestion runs, scan outcomes, overdue sources, review backlog, and source verification age. Redact traces and aggregate metrics; exclude credentials, student profile values, prompts containing student data, and source text.
- Document catalog coverage, automated cadence, and remaining human review. Link reproducible evaluation evidence and a short product walkthrough.

## Interfaces and dependencies
Packages all MVP features, with release checks from [evaluations](10-quality-evaluations.md). The root [plan](../plan.md) retains the 4–6 week milestone schedule.

## Acceptance criteria
- Documented local setup starts all required services; student authentication, profile editing, matching, and template explanations work without AI provider access.
- Hosting readiness checks, database migrations, and backup/restore instructions are verified before launch.
- No credentials are committed; public users cannot reach admin mutations without authentication.
- Observability reports service and model failures without exposing private student data.
- Report deployment and paid/live evaluations as complete only after they actually run.
- Verify one scheduled window with fake or controlled sources before enabling external daily scans.

## Exclusions
Unapproved paid provisioning and claims of a hosted demo without a verified deployment.
