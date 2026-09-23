# Personalized scholarship and assistance discovery

Status: backend candidate filtering, deterministic ranking, and ranking-factor responses implemented; frontend home page and AI explanations pending. Parent specification: [plan.md](../plan.md).

## Goal
Show signed-in students a personalized home page of scholarships, grants, and basic-needs resources relevant to their saved profile.

## Scope and behavior
- Make scholarships a first-class category alongside grants, food assistance, emergency support, and housing resources.
- Populate the home page from the saved profile, and refresh it after profile edits or new follow-up answers.
- Retrieve only published revisions and filter candidates using reviewed category, institutional, and geographic coverage metadata.
- Match scholarships using applicable major, class-year, GPA/scale, financial-need, and other reviewed requirements through the shared eligibility engine.
- Do not assume a 4.0 GPA scale or convert scales without a reviewed conversion rule.
- Order likely-eligible results first, unresolved results next, and likely-ineligible results in a separate expandable section. Within each eligibility group, show verified-open opportunities first, ordered by the nearest known deadline and then open opportunities whose deadlines are unknown. Show opportunities with unknown application availability next in a clearly labeled “Confirm availability” section; order them by institutional or geographic relevance and then program name because an unverified deadline cannot determine priority. Put verified-closed opportunities in a final closed-opportunities section. Break remaining ties in every section by institutional or geographic relevance and then program name. Return the ranking factors for display; do not use an LLM or opaque score.
- Treat application availability separately from eligibility. Unknown availability never implies that an opportunity is open and always requires provider confirmation.
- A scholarship match means eligibility to apply, not probability of winning. Never rank applicants by invented award probabilities or essay quality.
- Explain limited catalog coverage and distinguish no catalog matches from ineligibility.
- Show a short LLM-generated “why this scholarship fits” explanation only after opt-in. Ground it in the reviewed revision and deterministic outcome; reject unsupported claims and fall back to a template if the model is unavailable or fails.

## Interfaces and dependencies
Use the authenticated student's [saved profile](01-student-intake.md), `GET /api/programs`, and `POST /api/evaluate`, backed by the [catalog](05-program-catalog.md) and [eligibility engine](03-eligibility-engine.md). Render details through [checklists and explanations](04-results-and-checklists.md). The server selects published candidates before any explanation model call.

## Acceptance criteria
- A scholarship-only search returns relevant published scholarships, while a multi-category search can include other aid.
- Major/class-year restrictions and comparable GPA boundaries affect results correctly; unsupported scales stay unresolved.
- Closed awards never appear as currently actionable matches; unknown dates do not imply an open cycle.
- Ranking is reproducible across open, unknown-availability, and closed sections; known and unknown deadlines; institutional and geographic relevance; and program-name ties. The student can see why a result has its position.
- Students outside the sample campuses can receive national resources and an honest coverage message.
- The home page updates after saved profile edits; AI output cannot add, remove, reorder, or change eligibility of results.

## Exclusions
Web-wide search, autonomous crawling, award prediction, and automatic applications.
