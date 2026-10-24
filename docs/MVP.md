# Pathaid MVP Specification

## 0. Document control

| Field | Value |
|---|---|
| Product | Pathaid — Scholarships, Financial Aid, and Benefits Navigator |
| Version | 0.1 |
| Status | In progress |
| Owner | Aidan Jiang |
| Last updated | 2026-10-19 |
| Target launch | TBD — after frontend, reviewed catalog, deployment, and usability gates pass |
| Related documents | [Plan](../plan.md), [PRD](PRD.md), [architecture](ARCHITECTURE.md), [frontend design](FRONTEND_DESIGN.md), [features](../features/README.md), [deployment](deployment.md) |

This document defines the minimum portfolio release. **Implemented** statements
are supported by repository code and tests. **Pending** statements are release
requirements and must not be presented as completed.

## 1. Executive summary

**Pitch:** Pathaid helps US college students find reviewed scholarships and
basic-needs resources, understand whether they appear eligible to apply, and
continue through a source-backed application checklist.

**Problem:** Aid opportunities are spread across university, government, and
provider websites. Students must compare unclear requirements, application
cycles, and submission materials, and may confuse eligibility to apply with the
likelihood of receiving an award.

**MVP solution:** Students create an account and reusable profile, select
assistance categories, and receive deterministically ranked results from a small
automatically refreshed, human-reviewed catalog. Approved sources are scanned each morning; unchanged pages are skipped and new or changed scholarships become private review items. Each result explains the eligibility outcome,
unknowns, verification state, official evidence, and next application steps.
Administrators maintain the catalog through a protected, human-reviewed AI
ingestion workflow.

**Core user outcome:** An authenticated student finds a relevant reviewed
resource, understands why it appears eligible, ineligible, or unresolved, and
reaches the official provider or application page with a verified checklist.

**Validation question:** Can students correctly interpret Pathaid's eligibility
language and take an appropriate next step without assuming that Pathaid
guarantees an award or provider approval?

**Release decision:** Launch only after the complete student journey works on
mobile and desktop, 10–20 real programs are manually reviewed, five student
usability sessions are documented, recurring problems are resolved, and
production security and recovery checks pass.

## 2. Problem and evidence

### 2.1 Problem statement

- **Who:** Students attending US colleges, with initial emphasis on UMass
  Amherst, Massachusetts, and national resources.
- **Trigger:** A need for scholarship, grant, food, emergency, or housing help.
- **Current workaround:** Search provider and university sites, compare terms
  manually, and contact providers when requirements are unclear.
- **Cost:** Repeated searching, missed cycles, unnecessary sensitive-data
  disclosure, and unsupported assumptions about eligibility or selection.
- **Gap:** Existing information may be stale, uncited, incomplete, or fail to
  separate mandatory requirements from competitive selection factors.

### 2.2 Evidence

| Evidence | Source | Date | Confidence | Supports |
|---|---|---:|---|---|
| Product and implementation specification | [plan.md](../plan.md) | 2026-10-19 | Medium | Agreed scope and safety boundaries |
| Eligibility benchmark | `backend/app/quality_report.py` and CI | 2026-10-15 | High | 100/100 synthetic expected outcomes pass |
| Extraction benchmark | `backend/data/extraction_benchmark_v1.json` | 2026-10-15 | High for harness integrity | Ten versioned cases exercise evidence and claim metrics; live model accuracy is unmeasured |
| Student interviews and observed workflows | TBD — Aidan Jiang | Before launch | Unknown | Whether students experience the assumed pain and understand the flow |
| Alternatives research | TBD — Aidan Jiang | Before launch | Unknown | Concrete gaps in current products and workarounds |

**Unknowns:** No user-research validation, activation baseline, retention
baseline, production reliability measurement, or real catalog coverage
measurement exists yet.

## 3. Target users and jobs

### Primary persona

- **Context:** Undergraduate, graduate, community-college, part-time, or
  international student attending a US institution.
- **Experience:** No financial-aid expertise assumed.
- **Goal:** Identify relevant assistance and the next verified action.
- **Pain points:** Scattered information, ambiguous eligibility, stale
  deadlines, and unclear submission materials.
- **Constraints:** Limited time, mobile access, unknown answers, privacy
  concerns, and a small initial catalog.
- **Success:** The student can explain the result and reach the correct official
  next step.

> When I need financial or basic-needs assistance while attending college, I
> want to compare relevant reviewed programs and understand their requirements,
> so I can focus on applications or provider follow-up that may help me.

### Secondary persona

One deployment-configured administrator acquires official sources, reviews
AI-proposed data, records unresolved ambiguity, and explicitly approves or
rejects revisions. Provider self-service and multiple admin roles are deferred.

## 4. Goals, non-goals, and metrics

### Goals

1. Deliver a source-backed path from account creation to an official next step.
2. Keep eligibility and ranking deterministic, explainable, and reproducible.
3. Maintain catalog data through an auditable AI-assisted workflow with human
   publication authority.
4. Scan approved scholarship sources each morning, detect changes, and create review-ready candidates without manual submission.
5. Use student-facing AI only with consent, minimal data, validation, rate
   limits, and deterministic fallback.
6. Produce honest evaluation and deployment evidence for a portfolio demo.

### Non-goals

- Chat intake, RAG, embeddings, vector search, or broad autonomous web crawling. The MVP scans only administrator-approved sources and bounded one-hop discovery pages.
- PDF ingestion, model-directed tools, or model publication authority.
- Application submission/tracking, document storage, or checklist progress.
- Guaranteed eligibility, provider approval, award odds, or financial advice.
- Provider accounts, public admin registration, or granular admin roles.
- Native apps, localization, or non-US aid systems in v1.

### Success metrics

| Metric | Definition | Baseline | MVP target | Measurement |
|---|---|---:|---:|---|
| Core completion | Users reaching an official link ÷ users beginning intake | TBD | At least 4/5 observed sessions | Moderated sessions |
| Result comprehension | Participants distinguishing application eligibility from award selection | TBD | 5/5 sessions | Post-task question |
| Time to value | Sign-up completion to first useful result | TBD | Median under 5 minutes | Moderated timing |
| Eligibility correctness | Expected cases passed ÷ 100 | 100/100 | 100/100 required | Quality report and CI |
| Backend reliability | Successful API requests ÷ attempts | TBD | At least 99% during limited demo | Route/status telemetry |
| Catalog freshness | Current publications within maintenance interval | No real catalog | 100% at launch | Admin operations summary |

**Guardrails:** Zero known credential disclosures, cross-account access,
unreviewed public revisions, AI-changed eligibility labels, or student values in
operational telemetry.

## 5. MVP scope

**Core loop:** Learn limits → create profile → choose assistance → review ranked
results → answer relevant follow-ups → open evidence/checklist → follow official
link → return after profile or catalog changes.

| ID | Feature | Priority | MVP behavior | Excluded complexity | Status |
|---|---|---|---|---|---|
| F-01 | Student account/profile | Must | Auth, optional typed fields, consent, edit/delete | Social login, reset, guest profile | Implemented locally |
| F-02 | Reviewed catalog | Must | Current published revisions with provenance | Provider self-service, auto-publish | Backend implemented; real seed pending |
| F-03 | Discovery/eligibility | Must | Coverage, three-valued rules, follow-ups, stable ranking | Model decisions, opaque scores | Backend implemented |
| F-04 | Results/checklists | Must | Reasons, unknowns, evidence, materials, official links | Submission and progress tracking | Implemented locally |
| F-05 | Ingestion/review | Must | Acquire, extract, validate, retry, edit, approve/reject | Broad crawling and autonomous publication | Implemented locally |
| F-06 | Recommendation explanation | Should | Consent-gated grounded assistance with template fallback | AI eligibility or award prediction | Implemented locally |
| F-07 | Quality/deployment | Must | Benchmarks, PostgreSQL CI, containers, health/recovery | Invented metrics/hosting claims | Local foundation implemented |
| F-08 | Student/admin web UI | Must | Accessible responsive Next.js flows from Stitch | Native apps and invented designs | Implemented and browser-tested locally |
| F-09 | Launch catalog | Must | 10–20 current reviewed programs; at least four scholarships and two beyond UMass | Broad coverage claims | 12 official-source candidates validated; human review pending |
| F-10 | Scheduled scholarship discovery | Must | Daily approved-source scans, hash change detection, bounded one-hop discovery, private candidates | Broad crawling, silent content publication, notifications | Backend/admin UI and one controlled local official-source cycle verified; hosted verification pending |

**Scope freeze:** Scope freezes when the Stitch student and admin flows are
approved. Additions must identify the user outcome, release tradeoff, and work
displaced; Aidan Jiang approves changes.

## 6. End-to-end journeys

### Student happy path

1. Read product, catalog, and privacy limits.
2. Sign up and provide school, state, study level, enrollment, and categories.
3. Pathaid filters current published programs by category and coverage.
4. The deterministic engine evaluates and ranks candidates.
5. Review likely eligible, unresolved, unavailable, and closed sections.
6. Answer only relevant missing questions and reevaluate without automatic save.
7. Open a result and review evidence, verification, checklist, selection factors,
   and provider-only questions.
8. Follow the official link; later edit or delete the saved profile.

### Automated catalog refresh and administrator path

1. Each morning, the scheduler selects due approved program and discovery pages.
2. It records freshness for unchanged content without calling the model.
3. Changed pages and scoped candidate links enter acquisition, extraction, and validation automatically.
4. The administrator reviews prioritized new candidates and material changes.
5. The administrator compares evidence, edits if needed, and approves or rejects.
6. Publication updates the catalog; later student evaluations use it immediately.

Administrators may also start a manual ingestion:

1. Sign in with deployment credentials.
2. Submit an official webpage or pasted source plus its URL.
3. Worker acquires the source, requests structured extraction, validates it, and
   creates an unpublished draft.
4. Compare retained text with the proposal, edit, and revalidate.
5. Reject or attest source accuracy and completeness.
6. Approval atomically publishes and records an append-only review event.

### Failure paths

| Scenario | Required behavior | Recovery |
|---|---|---|
| Missing answer | Keep outcome unknown; ask only if it could change | Answer temporarily or edit profile |
| Provider-only condition | Show provider confirmation; do not ask repeatedly | Follow official contact/link |
| No coverage | Explain limited catalog; never label student ineligible | Change filters or return later |
| Closed/unknown cycle | Use labeled closed/confirm sections | Check official provider |
| Missing amount/deadline/material | Mark unverified; do not infer | Confirm with provider |
| AI unavailable/declined/invalid | Return deterministic template | Continue without AI |
| Duplicate ingestion | Return existing idempotent run | Inspect existing run |
| Transient failure | Retry no more than three times | Admin manual retry |
| Invalid draft | Block publication and show safe findings | Edit/revalidate or reject |
| Unauthorized admin | Return auth error without protected content | Authenticate as admin |

## 7. Functional requirements

### F-01 — Student accounts and profiles

- Normalize email and known UMass aliases; validate allowlisted optional fields.
- Use scrypt hashes, opaque server sessions, HttpOnly cookies, CSRF/origin checks,
  and shared authentication throttling.
- Students can access, edit, and delete only their own profile/account.
- Temporary evaluation answers are not saved automatically; validation errors
  never echo submitted values.
- AI opt-out prevents recommendation-provider calls.

**Acceptance:** Valid sign-up creates a session; cross-account or stale-CSRF
mutations fail; deletion removes profile and sessions; opt-out keeps the
deterministic journey available.

### F-02 — Reviewed catalog

- Stable programs point to immutable revisions.
- Public reads expose only the exact current published revision.
- Output includes description, coverage, verification, rules, checklist,
  selection factors, official links, and source metadata without source bodies.
- Replacement drafts cannot alter the current public pointer before approval.
- Seed import preserves real approvals and rejects conflicts or unsupported
  evidence; it cannot manufacture review history.

### F-03 — Discovery and eligibility

- Evaluate allowlisted trees with true/false/unknown semantics.
- Incomplete rule coverage cannot produce “Likely eligible.”
- Rank by eligibility group, availability, known deadline, relevance, program
  name, and stable ID exactly as defined in `plan.md`.
- Return the exact revision, criterion evidence, missing fields, unresolved
  conditions, coverage, section, and ranking factors.
- Identical inputs are deterministic and require no model call.
- All 100 versioned expected cases must pass.
- Missing questions come only from branches that could change the outcome.

### F-04 — Source-backed results and checklists

- Explain eligibility to apply separately from provider approval and selection.
- Mark unavailable amount, deadline, timezone, cycle, or materials unverified.
- Link every criterion to evidence from the evaluated revision.
- Show verified checklist items without evaluating their quality.
- AI output cannot change labels or add facts because final prose is rendered
  from reviewed server-owned reasons.
- Template fallback works without an AI provider key.

### F-05 — AI-assisted ingestion and review

- Accept public HTTP(S) pages or pasted text with a source URL.
- Block private/reserved destinations and unsafe redirects; bound time and size.
- Retain immutable provenance and treat source content as untrusted data.
- Request schema-constrained proposals and validate rule types, fields, URLs,
  coverage, dates, and exact evidence occurrence.
- Persist stages, leases, attempts, retries, versions, errors, and aggregate use.
- Require human source-accuracy and completeness decisions before publication.
- The model, worker, and public users have no publishing authority.
- Successful stages survive restart; invalid evidence cannot become a valid
  review draft; approval and its event commit atomically.

### F-06 — Recommendation assistance

- Only opted-in authenticated scholarship users can invoke the model path.
- Reevaluate the exact published revision and send only rule-relevant fields.
- The model selects supplied reason IDs; the server writes displayed prose.
- Default maximum is ten attempts per student per hour with bounded timeout and
  output tokens.
- Store aggregate outcome, model, tokens, and latency—not prompts, values, or
  generated text.
- Opt-out, missing key, refusal, error, rate limit, or invalid selection falls
  back to the source-backed template.

### F-07 — Quality and deployment

- CI applies PostgreSQL migrations, checks model drift, runs offline tests with
  no AI key, reports denominators, builds the image, and validates Compose.
- Compose provides private PostgreSQL/worker, one-shot migrations, and a
  loopback-bound API with liveness and migration-aware readiness.
- Reviewed catalog transfer and PostgreSQL backup/restore are documented.
- API logs contain only method, route template, status, and latency. Protected
  aggregate operations cover ingestion failure, model outcome/latency, and
  publication verification age.

### F-10 — Scheduled scholarship discovery and refresh

- Store an administrator-managed registry of program pages and one-hop discovery pages.
- Enqueue each due source once per morning window using durable schedules and deterministic idempotency keys.
- Respect robots directives, configured host/path scope, one source per host per scheduler cycle, and acquisition limits.
- Compare normalized content hashes and skip extraction for unchanged pages.
- Turn changed pages and discovered candidates into private ingestion runs and review drafts.
- Never close, remove, or materially change a public scholarship because a fetch failed.
- Require approval before new or materially changed scholarship content becomes public.
- Expose freshness, failures, candidates, and review backlog to the administrator.

**Acceptance:** overlapping schedulers do not duplicate a window; unchanged scans make no model call; changed sources remain private until approved; one source failure does not stop the batch; CI uses fake time and network/model providers.

## 8. Screens and frontend requirements

| Route | Purpose and primary action | Required states | Mobile requirement |
|---|---|---|---|
| `/` | Explain value/limits; sign up or log in | Default, API-independent | Single-column priority content |
| `/signup`, `/login` | Authenticate | Validation, throttle, failure | Touch-sized controls |
| `/onboarding` | Save short initial profile | Partial progress, unknown, validation | One clear section/action |
| `/home` | Review ranked recommendations | Loading, empty catalog, no coverage, error | Stacked labeled sections |
| `/programs/[id]` | Understand evidence/checklist; open official link | Historical revision, unknowns, fallback | Linear reading order |
| `/profile` | Edit fields/consent or delete account | Save error, confirmation | Accessible grouped fields |
| `/admin/login` | Admin entry | Missing config, throttle, invalid | Responsive form |
| `/admin/sources` | Manage sources and daily scan status | Empty, due, changed, paused, overdue, failed | Responsive source cards/table |
| `/admin/ingestion` | Submit/monitor manual and scheduled runs | Empty, queued, retry, failed | Readable status list |
| `/admin/revisions/[id]` | Compare, edit, approve/reject | Invalid, revalidation, conflict | Stacked source/proposal |

**Navigation:** Landing → auth → onboarding → home → detail → provider. Admin
login → runs → run detail → revision review → history.

The supplied Stitch prototype and `FRONTEND_DESIGN.md` govern visual work.
Frontend implementation follows those artifacts. All screens need
keyboard access, visible focus, semantic labels, meaningful loading/empty/error
states, and equivalent mobile and desktop task completion.

## 9. Data and business rules

### Core entities

| Entity | Purpose | Essential fields | Lifecycle |
|---|---|---|---|
| Student | Account/profile/consent | ID, email, hash, profile JSON, opt-in | Deleted on request with sessions/usage |
| Session | Revocable authentication | Token/CSRF hashes, owner, expiry | Logout, owner deletion, expiry cleanup |
| Program/revision | Stable identity and reviewed versions | Slug, pointer, status, rules, checklist, coverage, verification | Publications immutable; edits create drafts |
| Source snapshot | Evidence/provenance | URL, text, hash, acquisition metadata | Retained; excluded from public API/logs |
| Scheduled source/scan | Daily refresh | URL, type, scope, cadence, due time, hash, outcome, failure count | Retained for freshness/audit |
| Ingestion run/attempt | Durable workflow | State, lease, retries, versions, errors, latency | Retained for admin diagnostics |
| Review event | Human decision | Revision, reviewer, decision, time | Append-only |
| Recommendation attempt | Rate/operations | Student/revision, outcome, tokens, latency | Deleted with student; no prose/profile |

### Business rules

- **BR-01:** Likely eligible means reviewed application requirements appear
  satisfied; it does not predict selection or an award.
- **BR-02:** Missing, unsupported, or incomplete necessary conditions remain
  unresolved unless another necessary condition conclusively fails.
- **BR-03:** Availability is separate from eligibility and determines labeled
  open, confirm, and closed sections.
- **BR-04:** Only the current published revision is public; changed data needs a
  new draft and human decision.
- **BR-05:** Every eligibility, checklist, and selection claim retains exact
  source evidence.
- **BR-06:** Sensitive fields are optional and requested only when a reviewed
  candidate rule needs them.
- **BR-07:** AI receives only consented, rule-relevant profile fields and never
  identity or credentials.
- **BR-08:** Missing catalog coverage is not student ineligibility.

### Data lifecycle

- **Sources:** Student profile input, administrator sources, model proposals,
  and human review decisions.
- **Storage:** PostgreSQL in deployment; SQLite for isolated local/tests.
- **Updates:** Students edit profiles; admins create drafts; publications remain
  immutable.
- **Deletion:** Account deletion removes owned profile/session/recommendation
  records. Catalog provenance remains for auditability.
- **Safeguards:** Scrypt passwords; hashed session/CSRF/address values; HTTPS and
  Secure cookies in production; confidential backups.
- **Export:** Reviewed catalog bundles and database backups. Student data export
  is outside v1.

## 10. Technical boundaries

- **Frontend:** Next.js 16.4.2, React 19, TypeScript, Tailwind — implemented locally.
- **API:** FastAPI on Python 3.14.
- **Database:** PostgreSQL 16, SQLAlchemy 2, Alembic.
- **Authentication:** Custom server-side student and single-admin sessions.
- **AI:** Gemini or OpenAI structured-output APIs through separate adapters; deterministic CI stubs.
- **Scheduler:** Python process that selects due approved sources and creates idempotent runs — implemented.
- **Infrastructure:** Docker, Compose, GitHub Actions; hosting TBD after pricing.
- **Constraints:** One developer, 4–6 weeks, $25/month, 10–20 programs, one
  worker by default.
- **Risks:** Human-reviewed catalog, formal live model metrics, hosted operations,
  and deployed concurrency remain unverified.

### API summary

| Operation | Interface | Auth |
|---|---|---|
| Field metadata | `GET /api/profile-fields` | Public |
| Student auth | `POST /api/auth/signup`, `/login`, `/logout`; `GET /session` | Public/session; CSRF logout |
| Profile | `GET/PATCH/DELETE /api/profile` | Student; CSRF mutations |
| Catalog | `GET /api/programs`, `/api/programs/{id}` | Public |
| Evaluation | `POST /api/evaluate` | Student |
| Explanation | `POST /api/programs/{id}/recommendation-explanation` | Student; consent for model |
| Admin auth | `/api/admin/auth/*` | Admin session |
| Scheduled sources | `/api/admin/scheduled-sources*`, `/api/admin/scheduled-scans*` | Admin; CSRF mutations; implemented |
| Ingestion/review | `/api/admin/ingestion-runs*`, `/api/admin/revisions*` | Admin; CSRF mutations |
| Health | `GET /health/live`, `/health/ready` | Public |
| Operations | `GET /api/admin/operations/summary` | Admin |

## 11. Non-functional requirements

| Category | Minimum requirement | Verification |
|---|---|---|
| Performance | Evaluation has no external model dependency; production targets TBD after deploy | Route latency and load smoke test |
| Availability | Demo target TBD; readiness rejects unavailable/unmigrated DB | Health and hosted smoke tests |
| Security | HTTPS, exact origin, Secure/HttpOnly cookies, CSRF, throttling, private DB/worker, secret store | Automated tests and deployment review |
| Privacy | Minimize fields, require AI consent, omit private values from operations | Tests and log inspection |
| Accessibility | WCAG 2.2 AA for core tasks | Automated plus keyboard/screen-reader QA |
| Compatibility | Current Chrome, Safari, Firefox, Edge; mobile/desktop | Browser matrix after UI |
| Observability | Route/status/latency, model failures/latency, failed ingestion, scan success, overdue sources, review backlog, source age; no bodies | Capture tests and admin summary |
| Recovery | Migrations, catalog transfer, encrypted backups, practiced restore | CI and hosted restore exercise |
| Scale | Small portfolio catalog and limited demo; no unmeasured scale claim | PostgreSQL concurrency/load checks |

## 12. Analytics and learning

Frontend analytics are pending. Events must never contain profile values.

| Event | Trigger | Allowed properties | Metric |
|---|---|---|---|
| `signup_completed` | Account created | Device class, anonymous session | Activation |
| `profile_completed` | Initial intake saved | Non-sensitive field count, category count | Activation/time |
| `evaluation_completed` | Results returned | Result count and label counts | Completion |
| `follow_up_answered` | Temporary answer reevaluates | Field identifier only | Progressive intake |
| `official_link_opened` | Provider link followed | Program/revision ID, link type | Core outcome |
| `recommendation_fallback` | Template used | Safe fallback category | AI reliability |
| `api_request` | API response | Route template, method, status, latency | Reliability |

- **Usability:** Five US-college students complete sign-up, profile, result
  interpretation, checklist, official link, and profile editing across mobile
  and desktop.
- **Feedback:** Moderated observation/interview; in-app channel TBD — Aidan.
- **Decision:** Fix any issue recurring in at least two sessions. Any participant
  interpreting likely eligible as an award guarantee blocks launch until fixed.

## 13. Delivery plan

| Milestone | Deliverable | Owner | Exit criteria | Status |
|---|---|---|---|---|
| M0 | Scope/architecture | Aidan Jiang | Plan and feature specs | Complete |
| M1 | Backend core | Aidan Jiang | Auth, catalog, eligibility, results, ingestion, review pass tests | Complete |
| M2 | Evaluation/local deployment | Aidan Jiang | 100-case gate, PostgreSQL CI, Compose health, recovery docs | Complete locally |
| M3 | Scheduled discovery | Aidan Jiang | Daily approved-source scan, change detection, bounded discovery, admin API/status | Complete locally |
| M4 | Stitch and frontend | Aidan Jiang | Approved mobile/desktop flows implemented | Complete locally |
| M5 | Reviewed catalog/beta | Aidan Jiang + reviewer | 10–20 approved programs; browser/security/accessibility pass | Pending |
| M6 | Hosted demo/usability | Aidan Jiang | Deployment/recovery verified; five sessions; fixes complete | Pending |

**Critical path:** review real catalog → deploy securely → run a production accessibility check → conduct five sessions →
resolve findings.

## 14. Risks, assumptions, and questions

| ID | Type | Item | Impact | Owner | Mitigation/next action |
|---|---|---|---|---|---|
| R-01 | Risk | Program information changes | High | Aidan | Daily approved-source scans; hash detection; review material changes |
| R-02 | Risk | Eligibility is mistaken for award likelihood | High | Aidan | Separate selection language; comprehension tests |
| R-03 | Risk | Small catalog yields empty/misleading coverage | High | Aidan | Explain limits; balanced catalog; no ineligibility inference |
| R-04 | Risk | Student values leak to logs/model | High | Aidan | Consent, minimal payloads, template logs, privacy tests |
| R-05 | Risk | UI diverges from accessible designs | Medium | Aidan | Approve Stitch first; accessibility/browser QA |
| A-01 | Assumption | Students prefer fewer reviewed results to larger unverified lists | High | Aidan | Interviews and task-choice observation |
| A-02 | Assumption | Relevance explanations support optional sensitive questions | High | Aidan | Prototype tests with unknown/skip choices |
| Q-01 | Question | Which host meets security needs under $25/month? | Medium | Aidan | Compare current pricing before provisioning |
| Q-02 | Question | What catalog review interval is sustainable? | High | Aidan | Time initial review and reverification |
| Q-03 | Question | Which Stitch screens/tokens are approved? | High | Aidan | Attach link, screenshots, code, and `DESIGN.md` |

## 15. Launch readiness

### Product

- [ ] Stitch prototype covers every student/admin screen and state.
- [x] Complete student journey passes automated mobile and desktop browser tests.
- [x] Admin ingestion/review/publication passes automated browser tests.
- [ ] All Must features meet acceptance criteria.
- [ ] Loading, empty, unknown, closed, error, and recovery states work.
- [ ] Catalog has 10–20 current manually reviewed programs.
- [ ] Approved sources complete a controlled scheduled window; unchanged pages skip extraction and material changes enter review.

### Engineering and trust

- [x] Backend auth, CSRF, privacy, and publication boundaries have tests.
- [x] Eligibility passes 100/100 versioned cases.
- [x] PostgreSQL migration/schema checks run in CI.
- [x] Local Docker database, migrations, API readiness, and worker were verified.
- [ ] Release image build passes CI.
- [ ] Live extraction metrics are measured or explicitly remain unmeasured.
- [x] Automated accessibility and supported-browser checks pass locally.
- [ ] Hosted HTTPS, cookies, origin, networking, and log redaction are verified.
- [ ] Hosted backup restoration is practiced.

### Research and operations

- [ ] Five student usability sessions are documented.
- [ ] Recurring problems are resolved or block launch.
- [ ] Privacy-safe product events and dashboards are verified.
- [ ] Catalog owner and maintenance interval are documented.
- [ ] Incident/feedback contact is published.
- [ ] Hosting stays within $25/month.
- [ ] Aidan Jiang records the release decision.

## 16. Post-launch decision

- **Period:** First two weeks or first 20 qualified students, whichever is later.
- **Limitations:** A convenience sample cannot establish broad demand, fairness,
  or accuracy outside the reviewed catalog.
- **Outcomes/friction:** TBD after launch.
- **Decision:** Iterate if users complete and understand the task with repairable
  friction; expand only if review maintenance is sustainable; pause or pivot if
  users do not trust or understand source-backed results.
- **Next experiment:** TBD from usability and early-demo evidence.

## 17. Change log

| Date | Change | Why | Impact | Approved by |
|---|---|---|---|---|
| 2026-10-19 | Replaced generic template with Pathaid MVP | Align requirements with code and launch gaps | Establishes testable release boundary | Aidan Jiang |
| 2026-10-19 | Kept frontend pending Stitch artifacts | Avoid inventing visual requirements | UI remains critical path | Aidan Jiang |
| 2026-10-19 | Added daily approved-source discovery and refresh | Reduce manual scholarship collection while protecting publication quality | Scheduler and registry become MVP work; material changes still require review | Aidan Jiang |
| 2026-10-19 | Marked live AI, real catalog, and hosting pending | Avoid unsupported claims | Requires evidence before launch | Aidan Jiang |
| 2026-10-24 | Recorded responsive frontend and automated browser/accessibility completion | Keep scope status aligned with the tested implementation | Human review, hosted operations, and observed usability remain release gates | Aidan Jiang |

## 18. References

- [Implementation plan](../plan.md)
- [Feature specifications](../features/README.md)
- [Product requirements](PRD.md)
- [Architecture](ARCHITECTURE.md)
- [Frontend design](FRONTEND_DESIGN.md)
- Backend guide at `backend/README.md` in the implementation baseline
- [Deployment and recovery](deployment.md)
- [Quality evaluations](../features/10-quality-evaluations.md)
- [Demo deployment](../features/11-demo-deployment.md)

## Instructions for coding agents

1. Read this file, `FRONTEND_DESIGN.md`, `ARCHITECTURE.md`, and the relevant
   feature specification before implementation.
2. Implement Must features and the critical path before Should/Could work.
3. Preserve deterministic eligibility, human publication, evidence, consent,
   and privacy boundaries.
4. Do not claim catalog review, live model measurement, usability results,
   hosted deployment, or frontend states without evidence.
5. Treat every TBD as owned work, not permission to invent a requirement.
6. Report requirement IDs, verification, and remaining blockers after changes.
