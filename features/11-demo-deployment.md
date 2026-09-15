# Reproducible local setup and hosted demo

Status: planned MVP feature; not yet implemented. Parent specification: [plan.md](../plan.md).

## Goal
Make the student flow and protected administration usable locally and in a small hosted portfolio demo.

## Scope and behavior
- Provide Docker Compose services for Next.js, FastAPI, the worker, and PostgreSQL, with migrations and an explicit seed command.
- Provide `.env.example`, secret configuration, setup, backup/restore, health/readiness, and deployment instructions.
- Student matching works with reviewed seed data and no AI key. Ingestion reports missing configuration clearly.
- Target $25/month total hosting/API usage; verify current service prices before provider selection or provisioning.
- Serve through HTTPS, restrict allowed origins, keep database/worker private, and omit request bodies from proxy/application logs.
- Track operational errors, failed ingestion runs, and source verification age.
- Document catalog coverage and manual maintenance. Link reproducible evaluation evidence and a short product walkthrough.

## Interfaces and dependencies
Packages all MVP features, with release checks from [evaluations](10-quality-evaluations.md). The root [plan](../plan.md) retains the 4–6 week milestone schedule.

## Acceptance criteria
- Documented local setup starts all required services and matching works without OpenAI access.
- Hosting readiness checks, database migrations, and backup/restore instructions are verified before launch.
- No credentials are committed; public users cannot reach admin mutations without authentication.
- Report deployment and paid/live evaluations as complete only after they actually run.

## Exclusions
Unapproved paid provisioning and claims of a hosted demo without a verified deployment.
