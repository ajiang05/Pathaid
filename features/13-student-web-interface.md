# Student web interface

Status: implemented. Parent specifications: [plan.md](../plan.md), [MVP](../docs/MVP.md), and [frontend design contract](../docs/FRONTEND_DESIGN.md).

## Goal

Give students an accessible, responsive Next.js interface for creating an account, managing their profile, discovering reviewed opportunities, understanding eligibility, and following official application links.

## Design source

Use the supplied Google Stitch artifacts in `stitch_ui_screen_implementation/` and the PathAid design tokens. Preserve their calm botanical palette, border-based hierarchy, clear typography, and desktop navigation while adapting every flow intentionally for mobile. Product requirements and backend contracts take precedence over prototype-only concepts such as saved scholarships or application tracking, which are outside the MVP.

## Implementation slices

1. Create the Next.js App Router, TypeScript, Tailwind, lint, and build foundation.
2. Build reusable design tokens, responsive navigation, page shell, buttons, fields, cards, badges, and status messages.
3. Implement landing, sign-up, login, and session-aware navigation against the existing student authentication API.
4. Implement onboarding and profile editing from `/api/profile-fields` and `/api/profile`, including consent and account deletion.
5. Implement the personalized home/discovery flow against `/api/evaluate`, preserving the server's deterministic sections and ordering.
6. Implement program detail with evidence, unresolved conditions, checklist, provider links, and optional grounded recommendation explanations.
7. Add loading, empty, error, unauthorized, keyboard, responsive, and reduced-motion behavior.
8. Add focused component and browser tests, frontend CI checks, container support, and deployment documentation.

## Boundaries

- Do not implement saved scholarships, application tracking, notifications, award predictions, sponsored ranking, or client-side eligibility decisions.
- Treat the API as authoritative for sessions, profile validation, eligibility labels, ordering, evidence, and published revisions.
- Do not store profile values, credentials, source bodies, or recommendation prompts in browser logs or analytics.
- Proxy API calls through the Next.js server so browser cookies remain same-origin in local and deployed environments.

## Acceptance criteria

- A student can sign up, log in, complete or edit a profile, view deterministic recommendations, answer relevant follow-ups, open a result, inspect evidence and checklist items, and reach the official provider.
- Authentication and mutation failures preserve safe user input and display field-level or form-level guidance without echoing sensitive values.
- The same core tasks work at mobile and desktop widths with keyboard-only navigation, visible focus, semantic landmarks, and WCAG 2.2 AA contrast.
- Loading, empty catalog, no coverage, missing information, model fallback, session expiry, API failure, and not-found states are understandable and recoverable.
- Frontend type, lint, build, and representative browser checks run in CI without live AI calls.
