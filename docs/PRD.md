# Pathaid Product Requirements Document

**Product:** Pathaid  
**Owner:** Aidan Jiang  
**Status:** MVP development  
**Last updated:** October 19, 2026  
**Primary scope:** The MVP defined in [MVP.md](MVP.md)

## 1. Product summary

Pathaid helps students find assistance programs, understand whether they appear eligible to apply, and complete the next steps using requirements tied to reviewed source evidence.

The MVP combines a deterministic eligibility engine with an automatically refreshed, human-reviewed program catalog. A scheduler scans approved scholarship sources each morning, skips unchanged pages, and prepares changed or newly discovered scholarships for review. AI may help extract draft information from source documents and explain recommendations, but it must not make final publication decisions, change eligibility labels, or predict whether a student will receive an award.

## 2. Problem statement

Students often have to search across fragmented government, school, nonprofit, and provider websites. Program requirements may be hard to interpret, availability may be unclear, and application steps may be scattered across several pages or documents.

Pathaid addresses this problem by providing:

- One reviewed catalog of assistance opportunities.
- A profile students can reuse across programs.
- Reproducible eligibility results that explain which requirements passed, failed, or remain unresolved.
- Source-backed checklists and direct application links.
- An administrative workflow for reviewing changes before they become public.

## 3. Goals

### 3.1 MVP goals

1. Let a student create an account and maintain an optional, progressively completed profile.
2. Let a student discover reviewed opportunities relevant to their profile.
3. Clearly separate eligibility to apply from program availability and award selection.
4. Explain every eligibility result using the applicable requirements and supporting sources.
5. Provide an actionable checklist and application destination for each published opportunity.
6. Let an administrator ingest, review, approve, reject, and publish program revisions.
7. Run the backend reliably in a reproducible local deployment environment.
8. Deliver the student and administrator interfaces after the Google Stitch wireframes are approved.
9. Scan approved scholarship sources each morning and automatically prepare new or changed candidates for review.

### 3.2 Non-goals for the MVP

- Predicting whether a student will receive funding or an award.
- Submitting applications on a student's behalf.
- Replacing official program guidance or provider confirmation.
- Publishing AI-extracted content without human review.
- Supporting every assistance program or geographic area at launch.
- Native mobile applications.
- Broad autonomous web crawling or automatic publication of new and materially changed scholarship content.

## 4. Target users

### 4.1 Students

Students seeking financial, educational, housing, food, health, transportation, or related assistance. They need a simple way to identify relevant programs and understand what to do next.

### 4.2 Catalog administrators

Authorized operators who acquire sources, review extracted requirements, resolve changes, and decide whether a program revision should be published.

### 4.3 Program providers

External organizations that own the official application and determine final eligibility, availability, and award selection. They are a source of authoritative information but are not direct MVP users.

## 5. Core product principles

1. **Evidence before explanation:** Every public requirement and application step must trace to reviewed source material.
2. **Deterministic decisions:** The same published revision and profile must produce the same eligibility result.
3. **Explicit uncertainty:** Missing information and unsupported conditions remain unresolved unless a necessary condition conclusively fails.
4. **Separate concepts:** Eligibility to apply, current availability, and final award selection must be presented separately.
5. **Human publication control:** AI can prepare drafts; an authorized administrator controls publication.
6. **Data minimization:** Sensitive student information is optional, collected progressively, and used only when relevant and authorized.

## 6. MVP scope and status

| MVP ID | Capability | Priority | Current status |
| --- | --- | --- | --- |
| F-01 | Student account and profile | Must | Backend implemented; interface pending |
| F-02 | Reviewed opportunity catalog | Must | Backend implemented; real launch catalog pending |
| F-03 | Discovery and deterministic eligibility | Must | Backend implemented |
| F-04 | Source-backed results and checklists | Must | Backend implemented; interface pending |
| F-05 | Ingestion, review, and publication | Must | Backend implemented; admin interface pending |
| F-06 | Grounded recommendation explanations | Should | Backend implemented; interface pending |
| F-07 | Quality evaluation and deployment foundation | Must | Local foundation implemented; hosted deployment pending |
| F-08 | Student and administrator web interface | Must | Pending approved wireframes |
| F-09 | Reviewed launch catalog | Must | Research and review pending |
<<<<<<< HEAD
| F-10 | Scheduled scholarship discovery and refresh | Must | Backend implemented; admin UI and controlled external-source verification pending |
=======
| F-10 | Scheduled scholarship discovery and refresh | Must | Planned; acquisition and ingestion foundation implemented |
>>>>>>> 0aac2eb63c2ef53e9ae0503876e809002f385290

## 7. User journeys

### J-01: Student finds a program and prepares to apply

1. The student creates an account or signs in.
2. The student supplies only the profile fields needed for relevant matching.
3. Pathaid evaluates the current published catalog revision against that profile.
4. Results identify likely eligible, ineligible, and unresolved opportunities while showing availability separately.
5. The student opens an opportunity to see requirement-level reasons, evidence, and missing information.
6. The student follows the checklist and official application link.

**Successful outcome:** The student can identify at least one relevant next action and explain that Pathaid assesses ability to apply rather than predicting an award.

### J-02: Student updates information and reevaluates results

1. The student reviews the profile fields that influenced a result.
2. The student adds, changes, or removes information.
3. Pathaid reevaluates results using the same published catalog rules.
4. The updated result identifies which requirement outcomes changed.

**Successful outcome:** The result is reproducible from the saved profile and published revision without hidden model judgment.

### J-03: Daily catalog refresh

1. The scheduler selects due approved program and discovery pages each morning.
2. It acquires each page within configured scope and compares its normalized content hash.
3. Unchanged pages record freshness without extraction.
4. Changed pages and newly discovered same-scope candidates run through extraction and validation.
5. Material changes and candidates enter the administrator review queue.
6. One failed source does not stop the remaining daily scans.

**Successful outcome:** Routine collection and change detection require no daily manual submission, while public content remains reviewed.

### J-04: Administrator publishes a reviewed program revision

1. The administrator starts or monitors an ingestion run for a source.
2. The worker acquires the source, extracts structured draft data, and saves durable progress.
3. The administrator compares the draft with its source evidence and the current published revision.
4. The administrator corrects, approves, or rejects the draft.
5. An approved revision becomes the only current public revision.

**Successful outcome:** No extracted draft becomes public without an explicit authorized decision and an auditable revision record.

### J-05: Worker resumes interrupted ingestion

1. A worker claims a ready job with a temporary lease.
2. It records progress at durable stage boundaries.
3. If the worker stops, the lease expires and another worker can resume from saved progress.
4. The completed draft enters administrative review.

**Successful outcome:** A recoverable failure does not require recreating already persisted work or allow two workers to process the same active stage concurrently.

## 8. Functional requirements

### FR-001: Student authentication and account isolation

**Maps to:** F-01, J-01, J-02  
**Status:** Backend implemented; interface pending

The system must let students register, sign in, sign out, and access only their own profile and evaluation data.

**Acceptance criteria:**

- Passwords are stored using an approved password hash rather than plaintext.
- Protected student operations require an authenticated session.
- A student cannot read or change another student's private data.
- Authentication credentials and session secrets never appear in client-visible logs or analytics.

### FR-002: Progressive profile and consent

**Maps to:** F-01, J-01, J-02  
**Status:** Backend implemented; interface pending

The system must let students save, update, and remove profile attributes used by eligibility rules. Sensitive fields must be optional and collected only with clear context and consent.

**Acceptance criteria:**

- A student can use the product with an incomplete profile.
- The system distinguishes missing information from a failing requirement.
- Recommendation assistance receives only opted-in fields relevant to the request.
- Removing or changing a profile value affects later evaluations without altering historical catalog revisions.

### FR-003: Public reviewed catalog

**Maps to:** F-02, F-09, J-01  
**Status:** Catalog system implemented; launch content pending

The system must expose only current, published program revisions to student-facing discovery and detail views.

**Acceptance criteria:**

- Each public opportunity has a stable identifier and one current published revision.
- Draft, rejected, and superseded revisions are not returned through public catalog endpoints.
- Each published requirement, checklist item, and application destination includes reviewed source provenance.
- The launch catalog contains 10–20 reviewed opportunities before the MVP is released to students.

### FR-004: Deterministic eligibility evaluation

**Maps to:** F-03, J-01, J-02  
**Status:** Implemented

The system must evaluate a student profile against structured rules in a published opportunity revision without using a generative model to choose the label.

**Acceptance criteria:**

- Identical profile data and revision data produce identical outputs.
- Each necessary condition is reported as passed, failed, or unresolved.
- A conclusive necessary-condition failure may produce an ineligible result.
- Missing, incomplete, or unsupported data remains unresolved when no conclusive failure exists.
- A likely-eligible result means the known requirements to apply are satisfied; it does not predict award selection.
- The benchmark suite passes all 100 required eligibility cases before release.

### FR-005: Discovery, availability, and ranking

**Maps to:** F-03, J-01  
**Status:** Implemented

The system must return a stable, reproducible ordering of published opportunities while treating eligibility and availability as separate values.

**Acceptance criteria:**

- Results include eligibility status and availability status as distinct fields.
- Verified-open opportunities rank ahead of unknown-availability opportunities within equivalent relevance and eligibility groups.
- Unknown-availability opportunities remain discoverable and tell the student to confirm with the provider.
- Verified-closed opportunities rank after open and unknown opportunities and are clearly marked closed.
- Stable tie-breakers produce the same ordering for the same inputs.
- A catalog coverage gap is never presented as student ineligibility.

### FR-006: Source-backed results and checklists

**Maps to:** F-04, J-01, J-02  
**Status:** Backend implemented; interface pending

The system must explain evaluation results at the requirement level and provide practical application steps from the published revision.

**Acceptance criteria:**

- A result names the relevant opportunity and published revision.
- Each reason identifies its rule outcome and exact supporting evidence reference.
- Unresolved requirements state what information or provider confirmation is needed.
- Checklist items distinguish required documents, actions, deadlines, and unknowns when the source supports those distinctions.
- The official application destination is clearly identified and is never fabricated.

### FR-007: Grounded recommendation assistance

**Maps to:** F-06, J-01  
**Priority:** Should  
**Status:** Backend implemented; interface pending

The system may use AI to summarize already computed recommendations in plain language when the explanation remains grounded in deterministic results and reviewed evidence.

**Acceptance criteria:**

- The model cannot change an eligibility or availability label.
- The prompt excludes credentials, identity fields, and profile values unrelated to the recommendation.
- The response cites only evidence supplied from published revisions.
- If the model is unavailable or its output fails validation, deterministic results remain usable.

### FR-008: Source acquisition and draft extraction

**Maps to:** F-05, J-04, J-05  
**Status:** Implemented

The system must acquire supported source material and convert it into a structured draft for human review.

**Acceptance criteria:**

- The ingestion record retains the source location, retrieval metadata, and content identity needed for an audit.
- Extracted fields retain evidence spans or references to the source material.
- Low-confidence, missing, and conflicting fields are identified for review rather than silently completed.
- Extraction creates a draft revision and never publishes directly.

### FR-009: Durable ingestion orchestration

**Maps to:** F-05, J-05  
**Status:** Implemented

The worker must claim ready ingestion jobs with time-limited leases, save progress, retry recoverable failures, and expose terminal failures for review.

**Acceptance criteria:**

- Only the worker holding a valid lease may advance an active job.
- Lease expiration makes abandoned work available for another worker.
- Completed stages and error details are persisted in the database.
- Retry limits prevent a permanently failing job from looping indefinitely.
- Running a worker with `--once` processes at most one available job and then exits.

### FR-010: Administrative review and publication

**Maps to:** F-05, J-04  
**Status:** Backend implemented; admin interface pending

The system must provide authenticated administrative actions for comparing, correcting, approving, rejecting, and publishing revisions.

**Acceptance criteria:**

- Only authorized administrators can make review and publication decisions.
- The reviewer can inspect every proposed field with its evidence before deciding.
- Approval records the actor, decision time, and resulting revision state.
- Publishing a revision atomically makes it current and supersedes the prior current revision.
- Editing published information creates a new draft rather than rewriting published history.

### FR-011: Quality evaluation and deployment foundation

**Maps to:** F-07  
**Status:** Local foundation implemented; hosted operations pending

The repository must support repeatable validation, database migration, API startup, worker startup, and service health checks.

**Acceptance criteria:**

- Automated tests run in CI for proposed changes.
- Alembic upgrades a new supported database to the current schema.
- Docker Compose starts the database, applies migrations, starts the API, and starts the worker.
- Liveness and readiness endpoints distinguish a running process from a service ready to accept work.
- The hosted MVP has external monitoring and a verified database backup and restore procedure before launch.

### FR-012: Student and administrator web interface

**Maps to:** F-08, J-01, J-02, J-03, J-04  
**Status:** Pending approved Google Stitch wireframes

The web interface must implement the approved designs for student discovery and administrative review without changing the product rules in this document.

**Required routes:**

- `/`
- `/signup`
- `/login`
- `/onboarding`
- `/home`
- `/programs/[id]`
- `/profile`
- `/admin/login`
- `/admin/sources`
- `/admin/ingestion`
- `/admin/revisions/[id]`

**Acceptance criteria:**

- The student interface supports J-01 and J-02 from end to end.
- The admin interface supports scheduled-source management from J-03 and the review and publication flow from J-04.
- Eligibility, availability, and award-selection language remains visually and semantically distinct.
- Keyboard navigation, labels, focus states, and color contrast meet WCAG 2.1 AA for the implemented flows.
- No frontend implementation begins until the wireframes are supplied and approved by the product owner.

### FR-013: Scheduled scholarship discovery and refresh

**Maps to:** F-10, J-03  
<<<<<<< HEAD
**Status:** Backend implemented; administrator UI and controlled external-source verification pending
=======
**Status:** Planned; underlying acquisition, extraction, orchestration, and review are implemented
>>>>>>> 0aac2eb63c2ef53e9ae0503876e809002f385290

The system must scan administrator-approved scholarship sources daily, avoid unnecessary model calls for unchanged content, and create private review work for new or materially changed scholarships.

**Acceptance criteria:**

- Source schedules, scope, and scan state are durable in PostgreSQL.
- A due source is enqueued once per scheduled window even if schedulers overlap.
- Program pages are checked directly; discovery pages follow only bounded, canonical, same-scope links.
<<<<<<< HEAD
- Robots directives, source terms, one-source-per-host cycle limits, and acquisition security limits are honored.
=======
- Robots directives, source terms, per-host delays, and acquisition security limits are honored.
>>>>>>> 0aac2eb63c2ef53e9ae0503876e809002f385290
- Identical normalized content updates freshness without extraction or a new draft.
- Changed sources retain a snapshot and create one traceable ingestion run.
- Fetch failure never automatically closes or removes a published opportunity.
- New and materially changed content requires administrator approval before publication.
- Scan success, overdue sources, failures, candidates, and review backlog are observable.

### FR-014: Reviewed launch catalog

**Maps to:** F-09, J-01, J-04  
**Status:** Pending research and review

The product owner must select a coherent launch audience and publish 10–20 opportunities with verified requirements, availability handling, checklists, and application destinations. The set must include at least four scholarships and at least two opportunities beyond UMass.

**Acceptance criteria:**

- Every launch opportunity has a named authoritative source and review date.
- Every launch opportunity passes the same administrative publication workflow as ingested content.
- Every public requirement and checklist item has exact evidence.
- The catalog includes at least four scholarships and at least two opportunities beyond UMass.
- Catalog freshness is 100% at launch under the cadence selected before release.

## 9. Business rules

### BR-001: Eligibility meaning

`likely eligible` means the known requirements to apply are satisfied. It does not mean the applicant will be approved, selected, or funded.

### BR-002: Unresolved information

If a decision depends on missing student data, an unsupported rule type, an ambiguous source, or provider confirmation, that condition remains unresolved unless another necessary condition conclusively fails.

### BR-003: Availability

Availability is independent of eligibility:

- `verified open`: the reviewed source supports that applications are currently open.
- `unknown`: current availability could not be verified; the student should confirm with the provider.
- `verified closed`: the reviewed source supports that applications are currently closed.

### BR-004: Publication

Only one revision per opportunity is current and public. Changes are made through a new draft and require a recorded human decision.

### BR-005: Evidence

Public claims about requirements, availability, deadlines, checklists, and application destinations must have exact reviewed evidence. AI-generated text is not evidence.

### BR-006: Privacy

Sensitive profile fields are optional and progressively requested. AI receives only consented fields relevant to its current task. Authentication secrets and direct identity data are excluded.

### BR-007: Catalog coverage

The absence of a suitable opportunity in Pathaid's catalog means coverage is incomplete; it must not be interpreted or displayed as proof that the student is ineligible for assistance generally.

## 10. Data and API expectations

### 10.1 Main data concepts

- Student account and session.
- Student profile and field-level consent.
- Opportunity and immutable revision history.
- Structured eligibility rules.
- Source documents and exact evidence references.
- Evaluation, requirement outcomes, and checklist items.
- Scheduled source, scan cadence, allowed scope, content hash, scan outcome, and next due time.
- Ingestion run, durable stage progress, lease, and error state.
- Administrative review and publication decision.

### 10.2 API behavior

- Public catalog endpoints return published data only.
- Private student endpoints require an authenticated student context.
- Administrative endpoints require an authorized administrator context.
- Validation errors identify the affected field without exposing secrets or internal stack traces.
- Responses use stable identifiers so the interface can link evaluations to the revision that produced them.

## 11. Nonfunctional requirements

### 11.1 Security and privacy

- Prevent credential disclosure and cross-account access.
- Keep secrets out of source control, responses, logs, and analytics.
- Apply least-privilege authorization to administrative operations.
- Minimize stored student data and document why each sensitive field is needed.

### 11.2 Reliability and recovery

- The limited hosted demo must achieve at least 99% backend availability during its measured operating window.
- Database migrations must be repeatable on a clean environment.
- Worker progress must survive process restarts.
- Backup restoration must be tested before launch.

### 11.3 Performance

- Core student API interactions should complete quickly enough to support a median time to first useful result below five minutes for the full observed journey.
- Deterministic eligibility evaluation must not depend on a model call.
- Slow extraction or recommendation work must not block health endpoints or unrelated student requests.

### 11.4 Accessibility and usability

- Implemented interfaces must meet WCAG 2.1 AA for core flows.
- Status language must be understandable without requiring knowledge of eligibility systems.
- Error and empty states must provide a concrete next action.

### 11.5 Observability

- Health checks expose service liveness and readiness.
- Operational logs identify request or job context without recording sensitive profile values.
- Ingestion failures, scheduled scan failures, overdue sources, and exhausted retries are visible to administrators.
- Hosted monitoring alerts on API unavailability and worker failure before launch.

## 12. Analytics and measurement

Analytics must use event metadata that does not contain credentials, direct identity information, or raw sensitive profile values.

| Metric | MVP target | Measurement |
| --- | --- | --- |
| Core journey completion | At least 4 of 5 sessions | Observed usability sessions using J-01 |
| Result comprehension | 5 of 5 participants | Participant distinguishes apply eligibility from award selection |
| Time to first useful result | Median under 5 minutes | From session start to opening an actionable result |
| Eligibility correctness | 100 of 100 benchmark cases | Automated deterministic benchmark suite |
| Backend reliability | At least 99% | Hosted limited-demo availability window |
| Catalog freshness | 100% at launch | Review dates meet the selected refresh cadence |

Suggested product events:

- Account created.
- Onboarding started and completed.
- Profile field category updated.
- Discovery results viewed.
- Opportunity detail viewed.
- Checklist item opened.
- Official application link selected.
- Scheduled scan started, unchanged, changed, completed, or failed.
- Candidate scholarship discovered.
- Ingestion run started, completed, or failed.
- Revision approved, rejected, or published.

## 13. Release gates

The MVP is ready for limited student use when all of the following are true:

- F-01 through F-05 and F-07 through F-10 satisfy their acceptance criteria.
- F-06 either satisfies its acceptance criteria or is disabled without blocking deterministic results.
- The frontend implements the approved wireframes for the required routes.
- The launch catalog contains 10–20 reviewed, current opportunities.
- The eligibility benchmark passes 100 of 100 cases.
- Five observed usability sessions meet the completion and comprehension targets.
- No known issue permits credential disclosure, cross-account access, unreviewed publication, AI label changes, or sensitive profile values in telemetry.
- Hosted health monitoring and database backup restoration have been verified.

## 14. Validation matrix

| Requirement | Primary validation | State |
| --- | --- | --- |
| FR-001–FR-002 | Authentication, authorization, profile, and consent tests | Backend coverage implemented; UI validation pending |
| FR-003 | Catalog revision and public visibility tests | Backend implemented; launch data pending |
| FR-004–FR-005 | Unit, integration, and 100-case benchmark tests | Implemented; benchmark currently 100/100 |
| FR-006 | API response, provenance, and checklist tests | Backend implemented; UI validation pending |
| FR-007 | Grounding, validation, privacy, and fallback tests | Backend implemented; UI validation pending |
| FR-008–FR-010 | Extraction, lease, retry, review, and publication tests | Backend implemented; admin UI pending |
| FR-011 | CI, migration, Compose, and health-check verification | Local deployment verified; hosted checks pending |
| FR-012 | Accessibility checks and end-to-end usability sessions | Pending wireframes and implementation |
<<<<<<< HEAD
| FR-013 | Scheduler, deduplication, change detection, scope, and failure-isolation tests | Backend implemented and tested |
=======
| FR-013 | Scheduler, deduplication, change detection, scope, and failure-isolation tests | Planned |
>>>>>>> 0aac2eb63c2ef53e9ae0503876e809002f385290
| FR-014 | Manual source audit and freshness review | Pending launch catalog |

## 15. Delivery sequence

1. Implement scheduled-source storage, daily scheduling, change detection, and bounded discovery.
2. Obtain and approve Google Stitch wireframes, including `/admin/sources`.
3. Implement the student and administrator web interface against the existing APIs.
4. Select the launch audience and build the 10–20 opportunity reviewed catalog.
5. Run end-to-end, accessibility, privacy, and usability validation.
6. Select hosting within the $25 per month target using current provider pricing.
7. Deploy the API, scheduler, worker, and PostgreSQL database; apply migrations.
8. Configure monitoring, verify backup restoration, and run a limited launch.

## 16. Open decisions

- Which geographic area and student segment define the first catalog?
- What timezone and morning scan window should be the production default?
- What per-source cadence and host request delay applies to each launch source?
- Which Google Stitch wireframes are approved as the frontend source of truth?
- Which hosting provider meets the deployment requirements within the monthly budget?
- What privacy-preserving analytics service, if any, will be used for the limited launch?
- What support or correction channel should students use when program information appears outdated?

## 17. Decision log

| Decision | Reason |
| --- | --- |
| Use deterministic rules for eligibility labels | Results must be reproducible, testable, and explainable |
| Keep availability separate from eligibility | A student can satisfy requirements while a program is closed or unverified |
| Require human review before publication | Source extraction can be incomplete or incorrect |
| Scan approved sources daily and hash before extraction | Automates collection while avoiding needless model calls |
| Bound discovery to approved one-hop scopes | Finds new scholarships without an uncontrolled crawler |
| Keep the eligibility engine independent of FastAPI and SQLAlchemy | Domain logic remains easy to test and reuse |
| Use durable leased jobs for ingestion | Work can recover after worker interruption without duplicate active processing |
| Delay frontend implementation until wireframes are approved | The product owner requested design direction before interface code |
| Use PostgreSQL, SQLAlchemy, Alembic, FastAPI, and a Python worker | The stack supports relational history, migrations, API delivery, and durable background work |

## 18. Related documents

- [MVP scope](MVP.md)
- [Implementation plan](../plan.md)
- [Architecture](ARCHITECTURE.md)
- [Frontend design](FRONTEND_DESIGN.md)
- [`features/`](../features/) feature specifications

