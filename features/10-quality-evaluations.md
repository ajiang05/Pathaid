# Reproducible eligibility and extraction evaluations

Status: backend offline evaluations, one live Gemini intake, and frontend end-to-end/accessibility checks completed locally; formal live-model metrics, hosted checks, and usability sessions remain pending. Parent specification: [plan.md](../plan.md).

## Implementation status
- A versioned dataset contains 100 explicitly labeled synthetic profiles across all rule operators, numeric boundaries, missing answers, nested AND/OR logic, incomplete coverage, unsupported conditions, possible exceptions, and GPA scale handling.
- CI requires all 100 expected eligibility outcomes to pass and prints the dataset version, numerator, denominator, accuracy, and failures.
- The versioned 10-case extraction dataset validates 28 field labels, 10 claim labels, and exact evidence occurrence. Its metric harness reports field accuracy, criterion precision/recall, unsupported-claim rate, and evidence fidelity with explicit denominators when supplied a saved prediction artifact.
- Existing offline suites cover ranking, authentication/privacy, source safety, model refusal and malformed output, bounded retries, restart recovery, duplicate ingestion, review, rejection, and atomic publication with deterministic provider stubs.
- PostgreSQL migrations and model drift are checked in GitHub Actions without an AI provider key.
- Live Gemini-backed launch intake and a controlled official-source scheduler run have been completed. The scheduler run exposed and verified fixes for profile-vocabulary prompting, stale-cycle handling, and terminal scan outcomes. Formal aggregate live extraction metrics, deployed observability checks, and five student usability sessions remain pending.
- Desktop and mobile Playwright journeys, route-level axe checks, frontend lint, and the production build pass locally. The five-session protocol is documented in [the usability session record](../docs/USABILITY_SESSIONS.md); no human outcomes have been recorded yet.
- A local runtime privacy canary verified that synthetic credentials and profile values do not appear in API container logs and that account deletion removes the database record. Hosted log-collector redaction remains pending.

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
- Test scheduled discovery with fake clocks, resolvers, transports, and model providers.
- Document actual measurements and commands; do not claim retrieval metrics or agent capabilities absent from v1.

## Interfaces and dependencies
Covers all MVP features. GitHub Actions runs backend tests, frontend type/build checks, PostgreSQL migration checks, and representative browser tests.

## Acceptance criteria
- A fresh checkout can run the documented offline checks without an API key.
- All 100 expected eligibility cases pass and benchmark results report denominators and dataset versions.
- Ranking and account/privacy tests pass, sensitive questions appear only for relevant candidates, and five student usability sessions are documented with recurring issues resolved.
- Public documentation clearly distinguishes measured results from planned targets.
- Scheduled tests cover window deduplication, unchanged skips, host batching, scoped link limits, robots denial, and protected source management.

## Exclusions
Invented benchmark numbers and live paid API calls on every CI run.
