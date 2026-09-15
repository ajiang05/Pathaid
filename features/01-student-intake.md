# Student intake and transient profile

Status: planned MVP feature; not yet implemented. Parent specification: [plan.md](../plan.md).

## Goal
Collect enough information to personalize scholarships and assistance resources without requiring an account.

## Scope and behavior
- Support all students at US colleges, including graduate, community college, part-time, and international students.
- Collect school, state, study level, enrollment, and selected assistance categories. Allow multiple categories.
- Normalize UMass Amherst aliases; retain other school names without claiming campus-specific coverage.
- Define answer types, allowed values, validation, and question wording in a typed profile-field registry exposed through `GET /api/profile-fields`.
- Ask major, class year, GPA and grading scale, or other program-specific questions only when relevant. Allow unknown answers; do not infer citizenship or aid status.
- Keep answers in page memory only. Reload clears them. Do not use browser storage, persist profiles on the server, log answers, or send them to OpenAI.

## Interfaces and dependencies
The frontend submits the transient profile and category filters to `POST /api/evaluate`. The [eligibility engine](03-eligibility-engine.md) determines relevant follow-up fields.

## Acceptance criteria
- A student can complete intake, revise answers, and select multiple categories using a keyboard.
- Unknown answers remain unknown; invalid types produce accessible errors without echoing sensitive values in server responses.
- A non-UMass student can use the flow without being assigned UMass coverage.
- Reload removes answers; evaluation leaves no student records or value-bearing logs.

## Exclusions
Accounts, saved profiles, conversational intake, and document uploads.
