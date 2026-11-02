# Feature 07 — Scheduled discovery and change detection

## Outcome

Approved sources refresh daily when the Mac is available, and missed work catches
up at the next PathAid launch.

## Requirements

- Persist schedules, scan runs, stage state, bounded retries, and errors.
- On startup, enqueue at most one catch-up window per due source.
- Enforce one active run per source/window and conservative per-host pacing.
- Commit acquisition, comparison, extraction, validation, and activation stages
  separately so restart resumes completed work.
- Do not hold SQLite transactions during network or Gemini calls.
- Use short leases/idempotency to recover interrupted local workers.
- An unchanged page updates freshness and finishes without Gemini.
- A disappeared official page becomes unavailable and leaves history intact.
- Infer disappearance only after a complete traversal; a page-budget-truncated
  scan cannot deactivate an unobserved scholarship.
- Expire open scholarships at their deadline, using the sponsor timezone for a
  date-only deadline.
- Fingerprint cycle, deadline, availability, award, and eligibility semantics
  so later tracking can distinguish a material new cycle from cosmetic edits.

## Acceptance criteria

- Repeated startup cannot duplicate a scheduled window.
- Interrupted runs resume without repeating completed external work.
- Transient failures retry within limits; unsafe/permanent failures stop.
- Paused and policy-blocked scopes never enqueue.
- SQLite concurrency tests show no long-lived write locks.
- Persisted extraction artifacts let activation resume without repeating a
  completed Gemini request.
- A returning byte-identical page reactivates its retained validated version
  without duplicating its snapshot or calling Gemini.
- Cosmetic source/evidence changes preserve the material fingerprint; cycle,
  deadline, availability, award, or eligibility changes replace it.
