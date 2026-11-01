# Feature 01 — Local foundation and student profile

## Outcome

One student maintains a reusable private profile in a local SQLite database.
There is no signup, login, administrator, or account-selection flow.

## Requirements

- FastAPI binds to `127.0.0.1`; the local web UI is the only normal client.
- SQLite runs with migrations, foreign keys, WAL, a busy timeout, and short
  transactions.
- The singleton profile supports identity/contact, current school, separate
  current/permanent/school locations, academics, citizenship/residency, optional
  sensitive eligibility fields, and structured experiences.
- Experiences cover employment, activities, volunteering, memberships,
  leadership, honors, skills, and interests.
- Fields support known values, explicit unknown, and unanswered states.
- Profile completeness is advisory and explains how missing values increase
  Possible matches; no question blocks discovery.
- Changing the school emits a source-onboarding change and deactivates prior
  school-specific scopes without deleting history.

## Acceptance criteria

- A fresh database migrates and creates one profile, never multiple accounts.
- Saving and reloading preserves types and unknown semantics.
- Sensitive values are redacted from logs and validation errors.
- No profile endpoint requires an email/password session.
- Unit tests cover location separation, GPA scale, expected graduation,
  structured experiences, sensitive booleans, and school changes.

## Excluded

Authentication, hosted synchronization, multiple users, portal credentials,
and inline Discover follow-up questions.
