# PathAid frontend

This directory contains the Next.js student and administrator interface. The current slice provides the responsive landing page, sign-up and login flows, session handoff page, shared PathAid design tokens, and a same-origin proxy to the FastAPI backend.

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
```

The production build uses webpack because the current Tailwind worker can require a temporary local port under Turbopack in restricted build environments.
