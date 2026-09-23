# Deterministic eligibility and follow-up questions

Status: core evaluator and synthetic tests implemented; catalog/API integration pending. Parent specification: [plan.md](../plan.md).

## Goal
Evaluate reviewed eligibility rules reproducibly and identify information that could change the result.

## Scope and behavior
- Implement a Python evaluator over typed, allowlisted fields with equality, membership, numeric comparisons, and nested AND/OR groups.
- Reject unknown fields/operators, invalid operand types, empty groups, and excessive tree size/depth.
- Evaluate conditions as true, false, or unknown. Missing values are never false or zero by default.
- AND is false if any child is false, true if every child is true, otherwise unknown. OR is true if any child is true, false if every child is false, otherwise unknown.
- Return “Likely eligible” only for a satisfied and complete reviewed eligibility model; “Likely ineligible” only for conclusively failed necessary conditions; otherwise “Need more information.”
- Unsupported conditions stay unknown. If unmodeled exceptions could override a failed condition, that condition cannot independently disqualify a student.
- Distinguish mandatory scholarship criteria from competitive selection preferences.
- Collect follow-up fields only from branches that can change the outcome. Separate answerable questions from unresolved conditions requiring provider review.
- Generate reasons and questions from templates, retaining the source citation for every criterion. Explain failed OR alternatives in their group context.

## Interfaces and dependencies
`POST /api/evaluate` combines the authenticated student's saved profile with validated session answers and filters. Return evaluated revision IDs, outcomes, criterion results, missing field metadata, and citations. Persist new answers only when the student saves them. Use the registry from [profile](01-student-intake.md) and published rules from the [catalog](05-program-catalog.md).

## Acceptance criteria
- All 100 independently labeled synthetic-profile cases pass.
- Tests cover every operator, exact numeric boundaries, nested alternatives, unknown answers, incomplete coverage, and exceptions.
- A resolved OR branch does not trigger questions about irrelevant alternatives.
- Identical profile values and revisions produce identical results without a model call; evaluation alone does not change the saved profile.

## Exclusions
LLM eligibility decisions and scholarship winner selection.
