# Pathaid — Scholarships, Financial Aid, and Benefits Navigator

Status: implementation specification. Features and resume bullets below are targets, not claims of completed work.

Feature specifications: see [features/README.md](features/README.md) for individual feature requirements, dependencies, and acceptance criteria.

## 1. Purpose and success criteria

Pathaid addresses two related problems: financial-aid opportunities are scattered across provider websites, and students often cannot tell whether they meet the requirements to apply. It helps college students find scholarships, grants, and basic-needs assistance and turns reviewed official program information into personalized, source-backed checklists.

The first release is a portfolio demo built over 4–6 weeks. Its technical focus is AI workflow orchestration for program ingestion and grounded scholarship recommendations, supported by a tested Python backend and deterministic eligibility engine.

Success means a student can sign up, create and edit a profile, open a home page of relevant scholarships and other resources, understand why each is recommended and whether they appear eligible to apply, and follow an evidence-backed checklist to the official application page. An administrator can ingest an official source, review AI-extracted requirements, and publish a versioned program without changing application code. Before the portfolio release, five students complete observed usability sessions and recurring usability problems are addressed.

## 2. Audience and release scope

- Support students attending US colleges: undergraduate, graduate, community college, part-time, and international students. Attending a US institution does not imply eligibility for any particular benefit.
- Center the initial experience and campus-specific coverage on UMass Amherst students while retaining national opportunities for students at other US institutions.
- Seed 10–20 verified programs and resources: national resources plus Massachusetts and UMass Amherst examples.
- Accept students from any US college. Clearly identify the geographic and institutional coverage of each resource and the limits of the initial catalog.
- Include scholarships as a first-class MVP category alongside grants, food assistance, and emergency support. Cover both merit-based and need-based scholarships from verified university and scholarship-provider sources. Include housing-related resources where verified sources are available.
- Require student sign-up and login so students can save and edit their profile and return to their personalized home page. Defer application tracking.
- Use AI for administrator-facing ingestion and student-facing scholarship recommendation explanations grounded in published program data. Intake questions, eligibility decisions, and the candidate set remain deterministic.

Out of scope for v1: conversational intake, RAG, embeddings, pgvector, PDF ingestion, student document uploads, autonomous crawling, application submission, application tracking, and international aid systems outside the US.

## 3. Student experience

1. Explain the product, limited catalog coverage, and privacy behavior before sign-up using calm, plain language and visible source-verification cues. Let students create an account and log in.
2. Onboarding creates an editable profile through a short structured intake for school, state, study level, enrollment, and assistance needs. Normalize UMass Amherst aliases to one institution identifier; retain other school names without pretending they have campus-specific coverage.
3. Let students choose scholarships, grants, food assistance, emergency support, or housing resources, including multiple categories. Find candidate programs using reviewed categories and coverage metadata. A lack of catalog coverage must never be presented as a finding of ineligibility.
4. Evaluate candidates against published rules. Ask sensitive or detailed questions, including income, aid status, ethnicity, citizenship or immigration status, GPA, major, and class year, only when a candidate's reviewed requirements need them. Use labels and answer types from the profile-field registry and allow “I don’t know.” When a financial requirement permits it, prefer reviewed income ranges or aid indicators such as Pell eligibility or Student Aid Index thresholds over collecting exact household income.
5. Show a personalized home page after onboarding. Reevaluate after profile edits and rank results deterministically. Show likely-eligible matches first, unresolved matches next, and likely-ineligible results in a separate expandable section. Within each actionable eligibility group, order verified-open opportunities by the nearest known deadline, followed by opportunities whose deadlines are unknown. Break ties by institutional or geographic relevance and then program name. Put verified-closed opportunities in a separate section and expose the factors that determined each result's position.
6. Display each program’s description, eligibility outcome, reasons, unresolved conditions, verified assistance amount and deadline when available, required documents, source excerpts, verification date, and application or provider link.
7. For scholarships, ask about major/field of study, class year, and GPA with its grading scale only when a candidate requires them. Do not assume a 4.0 scale or convert between scales without a reviewed conversion rule.
8. Provide an actionable checklist and official provider or application link. Unknown amounts, deadlines, or document requirements must say they are not verified and direct the student to the provider.

Use an LLM to generate a concise, optional “why this scholarship fits” explanation from the student's relevant profile fields, the deterministic result, and reviewed source excerpts. Validate the output against the supplied program revision; display source-backed reasons and unresolved requirements separately. The model cannot invent eligibility, change ranking, or claim an award is likely. If generation fails or is unavailable, show a template explanation so the home page still works.

Prototype the student flow in Google Stitch before frontend implementation. Cover the landing page, sign-up/login, profile creation and editing, follow-up questions, personalized home page, ranked results, and program details with corresponding mobile and desktop designs. Give both screen sizes equal design priority and use a calm, clear, trustworthy visual and writing style.

Use three eligibility labels:

| Label                 | Meaning                                                                                                 |
| --------------------- | ------------------------------------------------------------------------------------------------------- |
| Likely eligible       | All reviewed eligibility conditions are represented and satisfied. Provider approval is still required. |
| Likely ineligible     | A reviewed necessary condition, including its modeled exceptions, conclusively fails.                   |
| Need more information | Missing answers, unsupported conditions, or incomplete rule coverage prevent a supported conclusion.    |

For competitive scholarships, “Likely eligible” means the student appears to meet the requirements to apply; it does not predict selection or an award. Keep selection factors such as essay quality and committee judgment separate from eligibility rules. Include verified essay, transcript, recommendation, and other submission requirements in the checklist without scoring them.

Separate missing student answers from conditions that require provider review. Do not keep asking students questions that cannot resolve a program’s incomplete rule coverage. For referral directories, describe access to the referral service separately from eligibility for benefits offered by listed providers.

Store profile fields only for authenticated students, encrypt traffic, and give students a way to edit and delete their profile and account. Explain which fields are saved and which relevant fields may be sent to OpenAI for recommendation explanations; obtain explicit opt-in before sending any student data. Never send identity, credentials, or unnecessary sensitive fields. If a student declines, use deterministic recommendations and template explanations. Never include profile values in operational logs.

## 4. Architecture and backend

| Component      | Choice and responsibility                                                                            |
| -------------- | ---------------------------------------------------------------------------------------------------- |
| Frontend       | Next.js, TypeScript, Tailwind; student auth/profile/home page and protected admin review UI           |
| API            | FastAPI and Python; student auth/profile, validation, matching, eligibility, admin review, publication |
| Database       | PostgreSQL; student accounts/profiles, program revisions, sources, rules, runs, and review history    |
| AI             | OpenAI extraction and grounded recommendation explanations behind configurable adapters               |
| Orchestration  | Explicit Python workflow with persisted run states, bounded retries, validation, and human approval  |
| Infrastructure | Docker, Docker Compose, and GitHub Actions                                                           |

Use a typed profile-field registry shared through API metadata. It defines accepted field names, answer types, allowed values, question wording, sensitivity, and whether a field may appear during progressive follow-up. Add fields only when supported by a reviewed program requirement. Keep citizenship, ethnicity, income, and aid-status questions optional and program-specific; never infer status from school, name, location, or nationality.

### Data model

- **Programs:** stable identity and a pointer to the current published revision.
- **Program revisions:** draft/published/rejected status, descriptive fields, assistance categories, coverage, source references, checklist information, eligibility tree, completeness declaration, and review metadata. Scholarship revisions also retain the award cycle, deadline and timezone when stated, application availability (open/closed/unknown), and selection factors separately from eligibility criteria.
- **Source snapshots:** source URL, acquisition time, content hash, retained source text, and acquisition method (webpage or pasted text).
- **Ingestion runs:** input source, state, attempts, model/prompt/schema versions, timing, token usage when available, structured errors, and resulting draft revision.
- **Review events:** administrator identity, decision, notes, revision, and timestamp.
- **Student accounts and profiles:** credential hash, account metadata, editable profile fields, consent preference, and deletion timestamps. Keep profile access scoped to the account owner; do not store model prompts or generated text containing profile values by default.

Use database migrations from the start. Keep published revisions immutable; edits create a new draft. Publishing atomically updates the program’s published pointer and records the approval. A failed ingestion or rejected draft leaves the previous published revision intact.

Do not create student-application tables.

### API boundaries

- `GET /api/profile-fields`: supported fields and question metadata.
- `GET /api/programs` and `GET /api/programs/{id}`: published program summaries/details only.
- `POST /api/evaluate`: authenticated student's saved profile plus validated session answers and assistance filters; returns deterministically ordered program outcomes, criterion-level reasons, missing fields, citations tied to evaluated revision IDs, application availability, verified deadline data, applicable coverage, and the ranking factors shown to the student. Persist new answers only when the student saves them to their profile.
- Student endpoints: sign-up/login/logout, read/update/delete own profile and account, and fetch a personalized home page. Recommendation explanation requests require the student's AI opt-in and accept only server-selected published candidates.
- Protected administrator endpoints: login/logout, create and inspect ingestion runs, retry failed runs, edit drafts, approve/publish, reject, and inspect revision history.

Authenticate students with hashed passwords and server-side account ownership checks. Authenticate one administrator with credentials supplied through deployment secrets; no public administrator registration. Use expiring HttpOnly session cookies, secure cookies in production, CSRF protection on mutations, and throttling for login and sign-up. Return field-level validation errors without echoing sensitive submitted values.

## 5. Eligibility engine

Use ordinary Python to evaluate a validated rule tree. The LLM proposes rules during ingestion; it never decides a student’s eligibility.

- Support equality, membership, numeric comparisons, and nested AND/OR groups over allowlisted profile fields.
- Reject incompatible types, unknown fields/operators, empty groups, and excessively large or deeply nested trees.
- Evaluate each condition as true, false, or unknown. Missing answers remain unknown; never coerce unanswered fields to false or zero.
- AND: any false condition makes the group false; all true makes it true; otherwise unknown.
- OR: any true condition makes the group true; all false makes it false; otherwise unknown.
- Explicitly represent unsupported conditions as unknown. An incomplete eligibility model cannot produce “Likely eligible.”
- Do not encode a condition as independently disqualifying if unmodeled exceptions could override it; mark that condition unresolved until its exceptions are represented.
- Treat application availability separately from eligibility: exclude verified closed cycles from actionable matches and make them available in a closed-opportunities section. Unknown dates or availability require checking with the provider; do not assume a scholarship repeats annually or is currently open.
- Rank without an LLM or opaque score. Preserve the eligibility-group, deadline, relevance, and program-name ordering defined in the student experience, and derive every ranking factor from reviewed catalog data and the student's explicit answers. The LLM may explain a recommendation but cannot select or reorder candidates.
- Collect missing fields only from branches that could change the outcome. Generate questions and explanations from templates and reviewed evidence.
- Every criterion must refer to a source snapshot and a supporting excerpt. Explain a failed alternative within an OR group as an alternative, not as a program-wide rejection.

Tests must use synthetic rules for edge cases rather than inventing real program requirements. All illustrative names, amounts, and eligibility claims from the original draft require official-source verification before entering the catalog.

## 6. AI ingestion and orchestration

The core AI deliverable is a controlled, inspectable ingestion workflow:

```text
Official URL or pasted text + source URL
  → acquire and normalize source
  → extract a structured draft with OpenAI
  → validate fields, rules, and evidence references
  → flag unsupported or ambiguous conditions
  → administrator reviews and edits
  → explicit approval publishes a revision
```

### Run lifecycle and failure behavior

Persist transitions through `queued`, `acquiring`, `extracting`, `validating`, and `awaiting_review`, with terminal `published`, `rejected`, or `failed` states. An edit after review invalidates the prior validation result and requires validation again before publication.

Use a lightweight worker process backed by PostgreSQL run records; defer Redis and Celery. Claim jobs atomically with a lease so work is not executed concurrently. Expired leases are recoverable after a worker restart. Reuse persisted successful source/extraction stages when retrying later failures. Deduplicate repeated job submissions with an idempotency key.

Permit at most three automatic attempts per transient acquisition or model failure, with exponential backoff. Authentication/configuration failures, unsafe URLs, and invalid drafts stop for administrator action. A manual retry creates a linked new attempt while retaining prior diagnostics. Configure source-size, output-token, request-timeout, and per-run limits; prevent unbounded model loops. Use one worker by default to bound concurrency.

### Extraction and review contract

- Accept public HTTP(S) pages or pasted source text accompanied by its URL. Treat pasted material as administrator-supplied, not automatically verified against the live page.
- Validate destinations and redirects, block private/local/reserved addresses, and prevent DNS rebinding from bypassing the checks. Bound redirects, download size, and duration; accept supported text content only.
- Preserve source text and provenance before extraction. External source text is untrusted data and cannot authorize tools, publication, or changes to the workflow.
- Request schema-constrained program fields, proposed rules, source excerpts, and unresolved conditions. For scholarships, distinguish mandatory eligibility criteria from competitive selection preferences, and extract the award cycle, application deadline, award amount, and required application materials when supported by the source. Validate semantic types and ensure cited excerpts occur in the retained source.
- Flag omissions, ambiguous language, unsupported logic, model refusals, and invalid output. Schema validity alone does not establish factual correctness or complete rule coverage.
- Present original text and extracted fields/rules side by side. Let the administrator edit, reject, or explicitly approve a draft and attest to source accuracy and coverage completeness.
- The model has no publishing authority. Every new or changed program requires administrator approval.

Record stage latency, attempts, validation errors, model/prompt/schema versions, and token usage when available. Operational logs must omit student answers, admin credentials, and API keys. Keep source content in the database rather than duplicating it in logs.

### Student recommendation explanations

Send only the consented, minimum relevant profile fields plus the selected published revision and its evidence excerpts to the explanation model. Require a short structured response tied to cited revision IDs; reject unsupported claims, invented deadlines or amounts, and eligibility conclusions that differ from the deterministic engine. Show a template explanation on refusal, timeout, validation failure, or missing API key. Bound request time, tokens, and per-user request frequency, and record aggregate latency, error rate, and token usage without recording student values.

### Agent terminology and future extension

The v1 implementation supports the claim **AI workflow orchestration**: the application coordinates acquisition, model execution, validation, retries, persisted state, and human review. It is not yet a model-directed tool-using agent.

A future **agent harness** milestone may add bounded model-selected tools for source inspection and extraction repair, with typed tool interfaces, per-run state, tool-call budgets, traces, and evaluations. It must retain the deterministic evaluator and approval boundary. This milestone is deferred and must not be claimed on a resume until implemented and tested.

## 7. Dataset and evaluations

### Catalog

Curate 10–20 real programs/resources from official university, government, and provider pages. Include at least four scholarships spanning merit-based and need-based opportunities, with at least two available beyond UMass; the remaining entries cover grants and basic-needs resources. Verify current application cycles instead of importing expired awards as open opportunities. Record source URL, snapshot, verification date, and reviewer for every published revision. Publish seed data only after review; seed import must not manufacture a human-approval event.

Prefer conservative partial screening for complex benefits. Retain unresolved conditions and provider referral steps instead of simplifying a program until it appears universally eligible. Manually reverify the catalog before the public demo and display last-verified dates.

### Required tests

- **Eligibility:** 100 synthetic profiles with independently specified expected outcomes, covering every rule operator, numeric boundaries, AND/OR exceptions, missing answers, unsupported conditions, and incomplete coverage. Require all expected outcomes to pass.
- **Scholarships:** GPA threshold boundaries and unknown grading scales, major/class-year restrictions, optional selection preferences versus mandatory criteria, application eligibility versus award selection, closed cycles, missing deadline/timezone information, and application-material checklists.
- **Ranking:** eligibility-group order, nearest verified-open deadline, unknown deadlines, institutional and geographic tie-breakers, stable program-name ties, ranking explanations, and separation of closed opportunities.
- **Student accounts and recommendations:** sign-up/login/logout, profile ownership and edits, deletion, consent enforcement, minimal model payloads, unsupported-claim rejection, and deterministic fallback when AI is disabled or fails.
- **Extraction:** a fixed versioned set of at least 10 source excerpts with manually labeled fields, criteria, and evidence spans. Include scholarship sources, ambiguous requirements, exceptions, and unsupported logic. Report field accuracy, criterion precision/recall, unsupported-claim rate, and evidence fidelity with explicit denominators. Do not invent performance numbers or measure retrieval precision when retrieval is absent.
- **Workflow:** transient failures, exhausted retries, worker restart, duplicate submissions, invalid model output, refusal, missing API key, review edits, rejection, and publication of a replacement revision.
- **Backend:** unauthorized student/admin access, CSRF, unsafe URL/redirect handling, invalid profiles, published-only reads, atomic publication, profile deletion, and absence of value-bearing error logs.
- **Frontend:** sign-up → short profile intake → personalized home page → progressively requested answer → ranked results → profile edit and reevaluation, sensitive questions appearing only for relevant candidates, school without campus coverage, unknown answers, empty catalog/filter results, API errors, corresponding mobile and desktop layouts, keyboard use, and accessible labels.
- **End to end:** student screening and admin ingestion/review/publication journeys. Use a deterministic model stub in CI; live OpenAI evaluations are explicit, separately budgeted runs.
- **Usability:** observe five students signing up, completing and editing a profile, interpreting recommendations and eligibility results, using a checklist, and reaching an official application page; record findings and address problems that recur across sessions before release.

GitHub Actions runs backend tests, frontend type/build checks, migration checks against PostgreSQL, and representative browser tests. Record real evaluation results and reproducible commands in project documentation.

## 8. Delivery milestones

Implement student sign-up, login, the typed profile-field registry, and editable profile storage as the first feature. Use that foundation for the personalized home page and deterministic evaluation. Prototype the account and student flow in Stitch before building its frontend screens; add AI recommendation explanations after source-backed matching works.

| Milestone           | Target    | Completion evidence                                                                                                                                                              |
| ------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Foundation          | Week 1    | Schema/migrations, student authentication/profile storage, profile registry, eligibility engine, representative reviewed resources, passing logic tests                           |
| Student flow        | Week 2    | Stitch prototype, sign-up, editable profile, personalized home page, progressive questions, ranked cited results, checklists, privacy controls                                    |
| AI orchestration    | Weeks 3–4 | Source acquisition, structured extraction, durable runs/retries, admin review/publication, grounded recommendation explanations with fallback                                     |
| Evaluation and demo | Weeks 5–6 | 10–20 reviewed resources including at least four scholarships, 100-profile evaluation, extraction report, browser tests, five student usability sessions, observability, demo |

## 9. Deployment and operations

- Provide Docker Compose for frontend, API, worker, and PostgreSQL, plus migrations and an explicit seed command.
- Student matching must run from reviewed seed data without an OpenAI API key. Recommendation explanations fall back to templates; ingestion reports a clear configuration error when a key is absent.
- Target a hosted public student flow and protected admin interface within **$25/month total** for hosting and API usage. Verify current provider pricing before selecting services or provisioning paid resources.
- Keep secrets outside the repository. Provide `.env.example`, setup instructions, health/readiness endpoints, migration steps, and database backup/restore instructions.
- Deploy behind HTTPS. Restrict CORS/origins to the frontend, keep database/worker private, and prevent request-body logging at the proxy and application layers.
- Add an observability tool for API/frontend errors, request latency, recommendation model latency and failures, failed ingestion runs, and source verification age. Use aggregate counts and redacted traces; exclude passwords, profile fields, prompts containing student data, and source text. Document catalog limitations and ongoing manual maintenance.
- Do not represent deployment, live AI evaluation, or human source review as completed without the corresponding evidence.
