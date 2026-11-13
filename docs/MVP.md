# PathAid MVP definition

**Status:** Approved target scope
**Last updated:** November 1, 2026

## Outcome

On one Mac, one student can discover current scholarships from approved public
sources, receive conservative eligibility results from a private local profile,
save or skip opportunities, and use a Chrome side panel to preview and fill a
supported application. The student explicitly attaches files, reviews the whole
application, and submits it personally.

The legacy hosted/admin system is outside this MVP. Useful acquisition,
extraction, validation, and matching code may be adapted, but PostgreSQL,
accounts, administrator review, and publication leave the target runtime.

## Included

### Local platform

- macOS-first, single-user installation
- loopback-only FastAPI service and local Next.js interface
- SQLite with Alembic migrations
- installation token for extension requests
- Gemini key and document key protected by macOS Keychain

### Profile and matching

- comprehensive optional profile with separate home/current/school locations
- academics, activities, work, service, memberships, and leadership
- optional sensitive eligibility fields
- strict Pass/Fail/Unknown requirement evaluation
- Strong/Possible/Not a match outcomes and deterministic ordering
- selection preferences separate from hard eligibility

### Discovery and records

- confirmed school directories and approved sponsor source scopes
- AcademicWorks/Blackbaud, Kaleidoscope, and bounded-directory adapters
- manual lead URLs for BigFuture, Scholarship America, and Bold.org
- official sponsor verification before showing aggregator leads
- daily and launch-time catch-up scans
- robots, terms, rate, depth, path, and page-budget enforcement
- snapshots/change detection and unchanged-content AI skipping
- current U.S. undergraduate-oriented college scholarships
- separate automatically considered and verified sweepstakes sections

### Saved and application workflow

- visible states: Not started, In progress, Already applied
- Save, Apply, and Skip this cycle
- return after material cycle/deadline/award/eligibility/opening change only
- Apply opens the official page, updates status, and opens the side panel

### Application copilot

- unpacked Manifest V3 Chrome extension
- user-activated side panel
- generic HTML, AcademicWorks/Blackbaud, and Kaleidoscope adapters
- one preview and one Fill application action, including sensitive fields
- ambiguous/unknown values skipped and corrected mappings remembered
- no submission, signature, certification, terms acceptance, CAPTCHA/MFA bypass,
  or credential storage
- filling disabled when official rules prohibit automation

### Documents, essays, and backup

- one encrypted résumé and one encrypted transcript
- one explicit click for every file attachment
- student-written essay bank with Gemini recommendation/mismatch analysis
- no AI generation or rewriting
- AI analysis warning/block when rules prohibit it
- encrypted backup of profile, scholarships, essays, sources, mappings, and status
- documents, API keys, encryption keys, and credentials excluded from backup

## Excluded

- automatic submission or unattended applications
- grants and non-scholarship aid
- award outcome tracking
- hosted/multi-user service, accounts, admin review, or publication
- automatic crawling of BigFuture, Scholarship America, or Bold.org
- search-engine crawling
- high-school-only and graduate-only targeting
- AI-written essays
- tax, immigration, banking, or identity-document storage
- multiple document variants
- Submittable, cross-origin iframe, or universal portal support
- consumer installer, Web Store listing, Windows, or Linux

## Required screens

1. **Home:** scan status, profile readiness, and alerts.
2. **Profile:** all matching fields and school-source onboarding.
3. **Discover:** Strong/Possible results plus distinct automatic/sweepstakes
   sections; no follow-up questionnaire.
4. **Scholarship detail:** evidence, requirements, preferences, materials, rules,
   and Save/Skip/Apply.
5. **Saved:** Not started, In progress, and Already applied filters.
6. **Sources:** approvals, lead URLs, scan history, pause/resume, and scan now.
7. **Documents:** résumé/transcript vault and essay bank.
8. **Settings:** Gemini, backup/reset, privacy, and extension connection status.
9. **Extension side panel:** compatibility, preview, fill, files, and warnings.

## Release gates

### Functional

- Confirmed school source scans safely and changed pages re-extract.
- Unchanged content skips model extraction.
- Aggregator lead cannot appear without official verification.
- Match-class and unknown-boundary fixtures pass.
- Apply opens the right URL and sets In progress.
- Skip resets only after a material change.
- Supported form previews/fills without submitting.
- Automatic-consideration and sweepstakes states are unambiguous.

### Safety

- API is loopback-only and extension token is required.
- Secrets never enter source control, database, or logs.
- Profile data is absent from extraction requests.
- automation/AI prohibition fixtures block the corresponding action.
- certifications and submit controls are never activated.
- each document attachment requires user action.
- backups contain none of the excluded data.

### Quality

- backend tests pass on SQLite;
- source adapters pass saved-fixture contract tests;
- frontend lint/build and core Playwright journeys pass;
- extension tests plus three supported real-form smoke tests pass; and
- setup succeeds from a clean macOS checkout.

## Definition of done

The MVP is done only when the workflow works without legacy accounts, admin
review, publication, PostgreSQL, or hosted infrastructure. Implementation status
is authoritative in [../plan.md](../plan.md), not inferred from this scope.
