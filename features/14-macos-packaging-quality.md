# Feature 14 — macOS packaging and release quality

## Outcome

A developer can clone PathAid on macOS, run one documented setup, load the
unpacked extension, and verify the MVP without hosted infrastructure.

## Requirements

- Provide bootstrap/start/stop/status/reset/backup commands or scripts.
- Create the local app-data directory, SQLite schema, Keychain entries, and
  installation token safely.
- Document Gemini key setup and extension developer-mode loading.
- Start local services and perform one due-scan catch-up check.
- CI runs SQLite migrations, backend tests, frontend lint/build/E2E, extension
  tests/build, adapter fixture contracts, and secret/policy checks without live
  Gemini calls.
- Maintain optional, explicitly budgeted live-provider and real-portal smoke
  procedures that never submit applications.
- Treat Chrome Web Store and signed consumer macOS distribution as post-MVP.

## Acceptance criteria

- A clean supported Mac reaches a healthy local UI from a fresh checkout.
- Restart preserves local state and interrupted jobs recover.
- Extension connects using the generated install token and minimal permissions.
- All release gates in `docs/MVP.md` pass.
- Setup docs do not require PostgreSQL, Caddy, admin credentials, or a hosted
  domain.
