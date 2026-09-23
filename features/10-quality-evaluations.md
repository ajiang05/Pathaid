# Reproducible eligibility and extraction evaluations

Status: planned MVP feature; not yet implemented. Parent specification: [plan.md](../plan.md).

## Goal
Measure correctness and demonstrate the AI and backend work with reproducible evidence.

## Scope and behavior
- Maintain 100 synthetic profiles with independently labeled eligibility outcomes; require all expected outcomes to pass.
- Maintain at least 10 versioned source excerpts with manually labeled fields, criteria, and evidence spans, including scholarships and ambiguous/unsupported conditions.
- Report extraction field accuracy, criterion precision/recall, unsupported-claim rate, and evidence fidelity with explicit denominators.
- Include scholarship GPA/scale boundaries, eligibility versus selection, major/class-year restrictions, closed cycles, and missing deadline information.
- Test deterministic ranking across eligibility groups, known and unknown deadlines, institutional and geographic relevance, program-name ties, and closed opportunities.
- Test workflow retries/restarts, refusal, malformed output, missing key, duplicate submissions, publication, and rejection.
- Test student sign-up/login/logout, profile ownership, editing and deletion, AI opt-in, minimum model payloads, unsupported-claim rejection, and fallback. Test admin authorization, CSRF, unsafe fetches, invalid profiles, migrations, published-only reads, and absence of profile values in logs.
- Verify observability reports frontend/API and model failures without student profile values, credentials, prompts, or source text.
- Exercise sign-up, short profile intake, personalized home page, profile editing, progressive sensitive questions, ranked results, follow-up reevaluation, and admin ingestion/review/publication in browser tests across mobile and desktop layouts. Compare frontend screens with the Google Stitch prototype.
- Observe five students signing up, completing and editing a profile, interpreting recommendations and eligibility results, using a checklist, and reaching an official application page. Record findings and address recurring usability problems before release.
- Use a deterministic model stub in CI. Live AI benchmarks are separately invoked and budgeted.
- Document actual measurements and commands; do not claim retrieval metrics or agent capabilities absent from v1.

## Interfaces and dependencies
Covers all MVP features. GitHub Actions runs backend tests, frontend type/build checks, PostgreSQL migration checks, and representative browser tests.

## Acceptance criteria
- A fresh checkout can run the documented offline checks without an API key.
- All 100 expected eligibility cases pass and benchmark results report denominators and dataset versions.
- Ranking and account/privacy tests pass, sensitive questions appear only for relevant candidates, and five student usability sessions are documented with recurring issues resolved.
- Public documentation clearly distinguishes measured results from planned targets.

## Exclusions
Invented benchmark numbers and live paid API calls on every CI run.
