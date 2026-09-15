# Reproducible eligibility and extraction evaluations

Status: planned MVP feature; not yet implemented. Parent specification: [plan.md](../plan.md).

## Goal
Measure correctness and demonstrate the AI and backend work with reproducible evidence.

## Scope and behavior
- Maintain 100 synthetic profiles with independently labeled eligibility outcomes; require all expected outcomes to pass.
- Maintain at least 10 versioned source excerpts with manually labeled fields, criteria, and evidence spans, including scholarships and ambiguous/unsupported conditions.
- Report extraction field accuracy, criterion precision/recall, unsupported-claim rate, and evidence fidelity with explicit denominators.
- Include scholarship GPA/scale boundaries, eligibility versus selection, major/class-year restrictions, closed cycles, and missing deadline information.
- Test workflow retries/restarts, refusal, malformed output, missing key, duplicate submissions, publication, and rejection.
- Test backend authorization, CSRF, unsafe fetches, invalid profiles, migrations, published-only reads, and profile privacy.
- Exercise student intake/follow-up/results and admin ingestion/review/publication in browser tests.
- Use a deterministic model stub in CI. Live AI benchmarks are separately invoked and budgeted.
- Document actual measurements and commands; do not claim retrieval metrics or agent capabilities absent from v1.

## Interfaces and dependencies
Covers all MVP features. GitHub Actions runs backend tests, frontend type/build checks, PostgreSQL migration checks, and representative browser tests.

## Acceptance criteria
- A fresh checkout can run the documented offline checks without an API key.
- All 100 expected eligibility cases pass and benchmark results report denominators and dataset versions.
- Public documentation clearly distinguishes measured results from planned targets.

## Exclusions
Invented benchmark numbers and live paid API calls on every CI run.
