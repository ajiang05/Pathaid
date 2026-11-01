# PathAid frontend

The frontend is being simplified into a single-user local Next.js workspace.
The target routes are Home, Profile, Discover, Scholarship detail, Saved,
Sources, Documents, and Settings. Login, signup, onboarding gates, administrator
ingestion, revision review, and publication are legacy behavior to remove.

See [the interface specification](../docs/FRONTEND_DESIGN.md) and
[implementation plan](../plan.md).

## Current development checks

```bash
cd frontend
npm install
npm run lint
npm run build
npm run test:e2e
```

Existing browser tests may still describe the legacy UI. Replace them alongside
each redesigned route; do not delete relevant accessibility coverage without a
new equivalent.

## Target rules

- Browser requests stay local and use the web app's same-origin API proxy.
- Eligibility, ordering, evidence, and policy restrictions come from FastAPI.
- Discover contains no profile follow-up questionnaire.
- Saved statuses are Not started, In progress, and Already applied.
- Action feedback appears next to the action and is announced accessibly.
- The web UI never receives Gemini/document encryption keys.
- The extension owns page inspection/filling; the web app never injects into
  third-party pages.
