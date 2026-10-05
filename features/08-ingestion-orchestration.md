# Durable AI ingestion orchestration

Status: durable run and attempt persistence, idempotent submission, leased stage claiming, bounded retries, restart recovery, offline worker, validation, and unpublished draft creation implemented; protected admin APIs, review/publication transitions, and deployed PostgreSQL verification remain pending. Parent specification: [plan.md](../plan.md).

The internal workflow intentionally stops at `awaiting_review`. Feature 09 owns administrator authentication, editing, rejection, approval, and the transitions to `published` or `rejected`.

## Goal
Coordinate source acquisition, AI extraction, validation, retries, and review as a recoverable workflow.

## Scope and behavior
- Persist states: queued → acquiring → extracting → validating → awaiting_review; terminal states are published, rejected, or failed.
- Run a lightweight Python worker backed by PostgreSQL records, with one worker by default.
- Claim jobs atomically with leases. Recover expired leases after restarts without concurrent processing or duplicate publication.
- Deduplicate repeated submissions with idempotency keys and reuse persisted successful stages when later stages fail.
- Limit automatic transient-failure attempts to three with exponential backoff. Unsafe URLs, invalid drafts, and configuration/authentication errors require administrator action.
- Link manual retries to prior attempts and retain diagnostics.
- Bound source sizes, model output tokens, timeouts, and per-run resource usage. Do not implement unbounded model loops.
- Record stages, timing, attempts, validation errors, and model/prompt/schema versions without student answers or secrets.
- Draft edits require validation again; successful validation still requires explicit review before publication.

## Interfaces and dependencies
Protected admin APIs create, inspect, and retry ingestion runs. Coordinate [acquisition](06-source-acquisition.md), [extraction](07-ai-requirement-extraction.md), and [publication](09-admin-review-and-publication.md).

## Acceptance criteria
- Retries stop at the configured limit, and manual retry retains history.
- Restart and duplicate-submission tests do not lose successful stages or publish duplicate revisions.
- Failure leaves the current published program intact.
- Run history explains stage failures and actual model usage.

## Exclusions
Redis/Celery and a model-directed agent harness. V1 supports an AI workflow orchestration claim. Agent-selected tools, tool budgets, and agent traces remain a future milestone, not a completed resume claim.
