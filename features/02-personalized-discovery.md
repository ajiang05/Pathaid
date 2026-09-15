# Personalized scholarship and assistance discovery

Status: planned MVP feature; not yet implemented. Parent specification: [plan.md](../plan.md).

## Goal
Help students find scholarships, grants, and basic-needs resources relevant to their circumstances.

## Scope and behavior
- Make scholarships a first-class category alongside grants, food assistance, emergency support, and housing resources.
- Retrieve only published revisions and filter candidates using reviewed category, institutional, and geographic coverage metadata.
- Match scholarships using applicable major, class-year, GPA/scale, financial-need, and other reviewed requirements through the shared eligibility engine.
- Do not assume a 4.0 GPA scale or convert scales without a reviewed conversion rule.
- Order likely-eligible results first, unresolved results next, and likely-ineligible results in a separate expandable section. Use program name as the stable ordering within each group.
- Separate application availability from eligibility. Put verified closed cycles in a closed-opportunities section; mark unknown availability for provider confirmation.
- A scholarship match means eligibility to apply, not probability of winning. Never rank applicants by invented award probabilities or essay quality.
- Explain limited catalog coverage and distinguish no catalog matches from ineligibility.

## Interfaces and dependencies
Use `GET /api/programs` and `POST /api/evaluate`, backed by the [catalog](05-program-catalog.md) and [eligibility engine](03-eligibility-engine.md). Render details through [checklists and explanations](04-results-and-checklists.md).

## Acceptance criteria
- A scholarship-only search returns relevant published scholarships, while a multi-category search can include other aid.
- Major/class-year restrictions and comparable GPA boundaries affect results correctly; unsupported scales stay unresolved.
- Closed awards never appear as currently actionable matches; unknown dates do not imply an open cycle.
- Students outside the sample campuses can receive national resources and an honest coverage message.

## Exclusions
Web-wide search, autonomous crawling, award prediction, and automatic applications.
