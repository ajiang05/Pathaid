# Source-backed results and application checklists

Status: planned MVP feature; not yet implemented. Parent specification: [plan.md](../plan.md).

## Goal
Explain each match and help students take the next application step.

## Scope and behavior
- Show program description, eligibility outcome, supporting reasons, unresolved conditions, verification date, and official source/provider links.
- Display verified award amounts, deadlines, award cycles, and application availability. Clearly mark unavailable information as unverified.
- Render criterion-level source excerpts tied to the exact evaluated revision.
- Build checklists from reviewed requirements, including essays, transcripts, recommendations, and other documents when specified.
- Explain eligibility to apply separately from competitive selection and provider approval.
- Differentiate referral-service access from eligibility for benefits offered by referred providers.
- Allow relevant missing answers to be supplied and reevaluate. Do not repeatedly ask about conditions only a provider can resolve.
- Use deterministic templates and accessible, responsive layouts.

## Interfaces and dependencies
Consume evaluation results and `GET /api/programs/{id}`. Preserve evaluated revision provenance if the current published revision changes while results are displayed. Dependencies: [discovery](02-personalized-discovery.md), [engine](03-eligibility-engine.md), and [catalog](05-program-catalog.md).

## Acceptance criteria
- Every eligibility reason links to reviewed evidence from the evaluated revision.
- Unknown amounts, materials, and deadline/timezone information are not invented.
- Scholarship checklists include verified submission materials without scoring their quality.
- Loading, API failure, unknown-answer, and empty-result states are usable with keyboard and screen-reader labels.

## Exclusions
AI-written explanations, document storage, saved checklist progress, and application submission.
