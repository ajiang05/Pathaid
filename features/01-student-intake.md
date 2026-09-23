# Student account and editable profile

Status: backend implementation in progress; frontend and end-to-end flow pending. Parent specification: [plan.md](../plan.md).

## Goal
Let students sign up, log in, and maintain the profile used for personalized scholarships and assistance resources.

## Scope and behavior
- Support all students at US colleges, including graduate, community college, part-time, and international students.
- Provide student sign-up, login, logout, and account/profile deletion. Hash passwords; enforce account ownership on every profile endpoint. Use expiring HttpOnly session cookies, secure cookies in production, CSRF protection on mutations, and login/sign-up throttling.
- Prototype sign-up, login, intake, and profile editing in Google Stitch at mobile and desktop sizes before implementing those screens.
- Begin with a short intake for school, state, study level, enrollment, and selected assistance categories. Allow multiple categories.
- Save initial answers in the authenticated student's profile; let the student review and edit them later. Show which fields are saved and allow account/profile deletion.
- Normalize UMass Amherst aliases; retain other school names without claiming campus-specific coverage.
- Define answer types, allowed values, validation, question wording, sensitivity, and progressive-follow-up behavior in a typed profile-field registry exposed through `GET /api/profile-fields`.
- Ask income, aid status, ethnicity, citizenship or immigration status, major, class year, GPA and grading scale, or other sensitive and detailed questions only when a candidate's reviewed requirements need them. Allow unknown answers; do not infer answers from school, name, location, nationality, or other profile data.
- Prefer reviewed income ranges, Pell eligibility, Student Aid Index thresholds, or other aid indicators over exact household income when the program's published requirements permit them.
- Keep unsaved follow-up answers in page memory until the student explicitly saves them. Do not log profile values. Request explicit opt-in before sending minimum relevant fields to OpenAI for recommendation explanations; never send identity or credentials. Declining AI leaves deterministic matching available.

## Interfaces and dependencies
Student auth and own-profile endpoints support the frontend. `GET /api/profile-fields` exposes field metadata. `POST /api/evaluate` combines the saved profile with validated session answers and category filters; the [eligibility engine](03-eligibility-engine.md) determines relevant follow-up fields. [Discovery](02-personalized-discovery.md) uses the profile for the home page.

## Acceptance criteria
- A student can sign up, log in, complete intake, edit saved answers, and select multiple categories using a keyboard.
- Unknown answers remain unknown; invalid types produce accessible errors without echoing sensitive values in server responses.
- Sensitive and detailed questions appear only when they could change a candidate program's outcome.
- A non-UMass student can use the flow without being assigned UMass coverage.
- A reload retains saved profile fields but clears unsaved answers. Another student cannot read or edit the profile. Deletion removes the account and profile; evaluation leaves no value-bearing logs.
- AI opt-in is recorded and enforced; declining it does not block matching or template explanations.

## Exclusions
Conversational intake, document uploads, and application tracking.
