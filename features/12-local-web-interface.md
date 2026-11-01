# Feature 12 — Local web interface

## Outcome

The Next.js interface exposes the complete single-user workflow without login,
admin, review, publication, or Discover follow-up questionnaires.

## Routes

- `/` — scan summary, profile readiness, and alerts
- `/profile` — full profile and school-source onboarding
- `/discover` — Strong/Possible plus separate automatic/sweepstakes sections
- `/scholarships/[id]` — evidence, rules, materials, and actions
- `/saved` — Not started, In progress, Already applied
- `/sources` — approvals, leads, scan history, pause/resume/scan now
- `/documents` — résumé, transcript, and essay bank
- `/settings` — Gemini, privacy, backup/reset, and extension connection

## Requirements

- Consistent scholarship cards with title, sponsor, award, deadline, match class,
  availability, and primary action.
- Every action gives visible success/failure feedback near the control.
- Optional profile fields live only in Profile; Discover never asks follow-ups.
- Unknown, unavailable, automatically considered, and sweepstakes states are
  explicit and never conveyed by color alone.
- Responsive keyboard-accessible behavior targets WCAG 2.2 AA.
- Browser calls a local same-origin proxy; it does not contain Keychain secrets.

## Acceptance criteria

- No student/admin login or review routes appear in target navigation.
- Core profile → discover → detail → save/apply journey passes Playwright on
  desktop and mobile viewports.
- Empty/loading/error/success/policy-blocked states have an actionable message.
- Scholarship boxes remain visually consistent for the same information type.
