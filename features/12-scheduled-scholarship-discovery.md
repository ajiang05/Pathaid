# Scheduled scholarship discovery and refresh

Status: backend and administrator UI implemented; controlled external-source verification pending. Parent specification: [plan.md](../plan.md).

## Goal

Keep the scholarship catalog current with a daily automated scan instead of requiring an administrator to submit every ingestion run manually.

## MVP workflow

```text
Daily scheduler
  → select due approved sources and discovery pages
  → acquire each page within source-specific limits
  → compare its normalized content hash with the last successful scan
  → skip unchanged content and record freshness
  → extract and validate changed sources
  → create a review draft or candidate scholarship
  → administrator reviews material public changes
  → publish approved revision
  → later student evaluations immediately use the new revision
```

## Source registry

Each scheduled target stores its canonical URL, source type (`program_page` or `discovery_page`), enabled state, cadence, next scan time, allowed host/path scope, last attempt and success, content hash, error state, failure count, discovery limits, and configuration audit fields. Only an administrator can add, enable, pause, or change a source. Public users never supply scheduler URLs.

## Scheduling and coordination

- Run one scheduler process that periodically enqueues due scans. The default production cadence is once each morning in a configured timezone.
- Store schedules and scan records in PostgreSQL. In-process timers are not the source of truth.
- Claim due sources atomically so overlapping scheduler instances do not enqueue duplicate scans.
- Derive an idempotency key from the source, scheduled window, and purpose.
- Process at most one source per host in each scheduler cycle so sources are not contacted simultaneously.
- Reuse the existing worker for acquisition, extraction, validation, and draft creation.
- Recover from database state after a scheduler restart.

## Discovery and change detection

- A `program_page` checks one known scholarship page for changes.
- A `discovery_page` may yield candidate links from an approved index page.
- Follow only HTTP(S) links within the configured allowed host and path scope, to a depth of one.
- Canonicalize and deduplicate links and cap links, redirects, response size, and total scan work.
- Respect published robots directives and source terms. Record disallowed targets for administrator review.
- Compare normalized-text SHA-256 hashes. An unchanged page records freshness without a model call.
- A changed page retains a new immutable snapshot, then runs extraction and deterministic validation.
- Deadline, availability, eligibility, application URL, award amount, coverage, checklist, and evidence changes are material.
- Fetch failure or page removal never deletes or closes a published program automatically.

## Publication policy

- The scheduler may automatically record an unchanged-source freshness check.
- New scholarships and material changes require administrator approval in the MVP.
- AI extraction has no publication authority.
- Automatic publication of content changes is deferred until quality, classification, rollback, and monitoring meet a separately approved threshold.
- Publishing makes future student evaluations use the new revision automatically. The MVP does not persist or push background reevaluations for every student.

## Administrator interfaces

Protected APIs and screens support source listing, creation, editing, enable/pause, immediate scan, last/next scan, change status, failures, candidates, and links to ingestion runs or review drafts. Operations report overdue sources, success rate, changes, candidates, review backlog, and throttling without source bodies.

## Acceptance criteria

- A due source is enqueued once per scheduled window even with overlapping schedulers.
- An unchanged source updates freshness without a model call or draft.
- A changed source creates one traceable run and an unpublished validated draft.
- Discovery produces deduplicated private candidates only within allowed scope and limits.
- Robots-disallowed, private-network, unsafe-redirect, oversized, unsupported, and rate-limited targets are not crawled further.
- Failure of one source does not stop other due sources; repeated failures use bounded backoff and become visible.
- No new or materially changed scholarship becomes public without administrator approval.
- Tests use fake clocks, resolvers, transports, and model providers; CI makes no live crawl or paid model call.

## Exclusions

- Broad autonomous web crawling or search-engine scraping.
- Authenticated, paywalled, CAPTCHA-protected, or access-controlled sources.
- PDF, image, or document ingestion in the first automated version.
- Automatic public removal or closure after fetch failure.
- Student email, SMS, or push notifications.
- Automatic publication of new or materially changed scholarship content.

