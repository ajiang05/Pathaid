# PathAid local-first redesign plan

**Status:** Phases 1–2 complete and verified; Phase 3 is next
**Last updated:** November 1, 2026

This file is the authoritative implementation sequence. Product scope is in
[docs/MVP.md](docs/MVP.md); implementation should not be inferred from the old
hosted code that remains in the repository.

## Status legend

- `[x]` completed and verified for the redesign
- `[~]` useful legacy code exists but needs redesign work
- `[ ]` not implemented for the redesign
- `[-]` intentionally removed from target scope

## Phase 0 — specification and inventory

- [x] Confirm single-user, macOS-first, local-only product direction.
- [x] Confirm conservative eligibility and application-copilot safety rules.
- [x] Define initial automatic and manual-lead source sets.
- [x] Rewrite product, MVP, architecture, setup, UX, and feature documentation.
- [x] Inventory legacy modules/tests as keep, adapt, replace, or delete.
- [x] Preserve useful scholarship/source URLs as unverified seed candidates.
- [-] Preserve the legacy PostgreSQL development records; they are disposable.

## Phase 1 — local platform foundation

- [x] Create a clean migration branch from current main.
- [x] Replace PostgreSQL runtime assumptions with local SQLite and WAL settings.
- [x] Design the new Alembic baseline for singleton local data.
- [x] Remove student/admin authentication, review/publication APIs, and Caddy.
- [x] Add app-data-directory resolution and non-secret local configuration.
- [x] Add macOS Keychain service for Gemini/install/document keys.
- [x] Bind FastAPI to loopback and add extension installation-token auth.
- [x] Prove upgrade, backup, restore, and reset on a fresh local database.

**Exit:** local API starts without PostgreSQL/auth/admin and passes foundation
security/migration tests.

## Phase 2 — private profile and deterministic matching

- [x] Adapt the existing field schema and pure eligibility engine.
- [x] Add separate current, permanent, and school locations.
- [x] Add structured activities, employment, service, memberships, leadership.
- [x] Add optional sensitive scholarship fields and unknown semantics.
- [x] Implement strict Strong/Possible/Not a match classification.
- [x] Define stable availability/deadline/freshness/relevance ordering.
- [x] Build the single-user Profile and Discover interfaces with no login or
  inline follow-up questionnaire.

**Exit:** saved fixture profiles produce reproducible explanations and ranks.

## Phase 3 — approved sources and automated discovery

- [~] Reuse safe acquisition, snapshots, hashing, and extraction adapters.
- [x] Implement source registry and school-directory confirmation.
- [x] Implement generic bounded-directory adapter.
- [x] Implement AcademicWorks/Blackbaud public-listing adapter.
- [x] Implement Kaleidoscope public-listing adapter.
- [x] Add manual lead intake and official sponsor verification.
- [x] Enforce robots, terms/policy, rate, path, depth, and page budgets.
- [x] Replace reviewer publication with deterministic activation after validation.
- [ ] Add daily scheduler plus launch-time catch-up.
- [ ] Add disappeared/expired source behavior and cycle change detection.

**Exit:** approved fixture sources discover, update, expire, and reactivate
scholarships without per-record human publication.

## Phase 4 — saved scholarships and minimal tracking

- [ ] Implement Not started, In progress, and Already applied views.
- [ ] Implement Save, Apply, and Skip this cycle.
- [ ] Persist a material-change fingerprint for skipped opportunities.
- [ ] Add separate automatically considered and verified sweepstakes sections.
- [ ] Remove award-outcome and general program-tracking concepts.

**Exit:** saved/status/skip behavior survives restart and follows cycle rules.

## Phase 5 — Chrome application copilot

- [ ] Create Manifest V3 extension with service worker and side panel.
- [ ] Add minimal permissions and authenticated loopback connection.
- [ ] Define adapter contract that cannot submit/certify/sign.
- [ ] Implement generic HTML form inspection, preview, and fill.
- [ ] Implement AcademicWorks/Blackbaud adapter.
- [ ] Implement Kaleidoscope adapter.
- [ ] Mark sensitive mappings and skip ambiguous fields.
- [ ] Learn corrected portal mappings.
- [ ] Parse source policy flags and disable prohibited automation.
- [ ] Connect Apply to official tab and side panel.

**Exit:** three supported real forms can be previewed and filled without any
submission/certification action.

## Phase 6 — documents, essays, and backup

- [ ] Build Keychain-backed encrypted vault for one résumé and transcript.
- [ ] Require one click for every attachment.
- [ ] Build local student-written essay bank and metadata.
- [ ] Add Gemini essay recommendation/mismatch analysis only.
- [ ] Disable AI analysis when official rules prohibit it.
- [ ] Add data-tier notice and explicit full-essay analysis configuration.
- [ ] Implement encrypted backup with documented exclusions.

**Exit:** encryption, attachment consent, AI policy, and backup-exclusion tests
pass.

## Phase 7 — local packaging and release verification

- [ ] Write one-command macOS bootstrap/start scripts.
- [ ] Load and connect the unpacked extension in developer mode.
- [ ] Add startup/catch-up scheduling suitable for a Mac that may sleep.
- [ ] Run backend, frontend, extension, adapter, and security suites in CI.
- [ ] Test from a fresh checkout and fresh app-data directory.
- [ ] Run real workflow smoke tests without automatic submission.
- [ ] Update README commands from transitional to final packaged commands.

**Exit:** the MVP release gates in `docs/MVP.md` all pass.

## Explicitly removed legacy work

- [-] student/admin account registration and login
- [-] administrator ingestion review and publication
- [-] public reviewed catalog and catalog transfer workflow
- [-] PostgreSQL/Caddy/hosted-beta deployment requirement
- [-] provider/reviewer roles and attestations
- [-] multi-user sessions, shared rate limits, and account deletion
- [-] broad assistance-program scope outside scholarships

## Change discipline

Each phase should be split into small commits with one coherent behavior,
migration, and tests. Do not combine dependency upgrades, schema replacement,
UI redesign, and feature logic in one commit. Before deleting a legacy module,
prove that its reusable behavior has either moved or is intentionally obsolete.
