# Feature 08 — Chrome extension foundation

## Outcome

An unpacked Manifest V3 extension connects safely to the local PathAid instance
and shows a user-activated application side panel.

## Requirements

- Use a service worker, side panel, and on-demand content-script injection.
- Request only `activeTab`, `scripting`, `sidePanel`, storage, and loopback host
  access required by the implementation.
- Authenticate narrow `/api/extension/*` requests with a high-entropy,
  installation-specific token protected by Keychain.
- Validate exact extension origin, request schema, scholarship context, and the
  active portal origin.
- Display connected/disconnected, supported/unsupported, and policy-blocked
  states clearly.
- Do not request broad all-sites access or persist page contents/sensitive values
  in extension logs/storage.

## Acceptance criteria

- Missing/wrong tokens and disallowed origins receive no private data.
- The content script runs only after explicit user activation on the active tab.
- Service-worker restarts restore non-sensitive connection state safely.
- The extension has no API capable of submitting or certifying an application.
