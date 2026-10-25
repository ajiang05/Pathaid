# Student account and editable profile

Status: backend and responsive student account/profile interface implemented; PostgreSQL, desktop/mobile browser, and accessibility checks pass locally. Parent specification: [plan.md](../plan.md).

## Goal
Let students sign up, log in, and maintain the profile used for personalized scholarships and assistance resources.

## Scope and behavior
- Support all students at US colleges, including graduate, community college, part-time, and international students.
- Provide student sign-up, login, logout, and account/profile deletion. Hash passwords; enforce account ownership on every profile endpoint. Use expiring HttpOnly session cookies, secure cookies in production, CSRF protection on mutations, and login/sign-up throttling.
- Implement the approved sign-up, login, intake, and profile editing designs at mobile and desktop sizes.
- Begin with a short intake for school, state, study level, enrollment, and selected assistance categories. Allow multiple categories.
- Save initial answers in the authenticated student's profile; let the student review and edit them later. Show which fields are saved and allow account/profile deletion.
- Normalize UMass Amherst aliases; retain other school names without claiming campus-specific coverage.
- Define answer types, allowed values, validation, question wording, sensitivity, and optional-field behavior in a typed profile-field registry exposed through `GET /api/profile-fields`.
- Keep optional eligibility fields in the editable student profile, including race, ethnicity, first-generation status, Pell eligibility, income range, Student Aid Index, citizenship or immigration status, major, class year, GPA, and grading scale. Allow students to skip or remove every optional answer; do not infer answers from school, name, location, nationality, or other profile data.
- Prefer reviewed income ranges, Pell eligibility, Student Aid Index thresholds, or other aid indicators over exact household income when the program's published requirements permit them.
- Do not collect temporary answers on the Discover page. Reevaluate results from saved profile values after the student edits the profile. Do not log profile values. Request explicit opt-in before sending minimum relevant fields to the configured AI provider for recommendation explanations; never send identity or credentials. Declining AI leaves deterministic matching available.

## Interfaces and dependencies
Student auth and own-profile endpoints support the frontend. `GET /api/profile-fields` exposes field metadata. `POST /api/evaluate` evaluates the saved profile with validated category filters; the [eligibility engine](03-eligibility-engine.md) identifies missing fields without collecting them on Discover. [Discovery](02-personalized-discovery.md) uses the saved profile.

## Acceptance criteria
- A student can sign up, log in, complete intake, edit saved answers, and select multiple categories using a keyboard.
- Unknown answers remain unknown; invalid types produce accessible errors without echoing sensitive values in server responses.
- Sensitive and detailed questions are clearly optional and remain editable only in the student profile.
- A non-UMass student can use the flow without being assigned UMass coverage.
- A reload retains saved profile fields but clears unsaved answers. Another student cannot read or edit the profile. Deletion removes the account and profile; evaluation leaves no value-bearing logs.
- AI opt-in is recorded and enforced; declining it does not block matching or template explanations.

## Exclusions
Conversational intake, document uploads, and application tracking.
