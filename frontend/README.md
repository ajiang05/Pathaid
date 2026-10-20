# PathAid frontend

This directory contains the complete Next.js MVP interface for students and administrators. It includes authentication, onboarding, profile and privacy controls, deterministic discovery, evidence-backed program details, scheduled source monitoring, ingestion monitoring, and human revision review.

## Run locally

Start the backend on port 8000, then run:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Set `PATHAID_API_URL` when the backend is available at a different server-side URL; browser requests continue to use `/api/*` so the HttpOnly session cookie stays same-origin.

## Verify

```bash
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The production build uses webpack because the current Tailwind worker can require a temporary local port under Turbopack in restricted build environments.
