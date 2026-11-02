# Feature 05 — Eligibility, availability, and ranking

## Outcome

The same profile and scholarship version always produce the same transparent
match result and ordering without a network or AI call.

## Requirements

Each hard rule evaluates to Pass, Fail, or Unknown:

- Strong: all hard rules Pass.
- Possible: no Fail and one or more Unknown.
- Not a match: one or more Fail.

Selection preferences are displayed separately and never override hard rules.
Availability is evaluated after eligibility: only verified-current/open records
appear in current matches. Closed, expired, disappeared, and unverifiable
records remain historical and hidden. Automatically considered awards and
verified sweepstakes occupy separate sections.

Within a section, order by match class, availability, deadline (known soonest,
then unknown), source freshness, profile relevance, and stable scholarship ID.
Every nullable value has an explicit sort key.

## Acceptance criteria

- Truth-table tests cover AND/OR, numeric/date boundaries, membership, location,
  structured experience, and missing answers.
- A single failed mandatory rule always produces Not a match.
- An unknown mandatory rule never produces Strong.
- Selection factors cannot change eligibility.
- Identical inputs yield byte-stable ordered IDs across runs.
- Automatically considered awards expose no Apply action or application status.
- Sweepstakes enter their own section only after deterministic official-rules
  URL and evidence validation.
