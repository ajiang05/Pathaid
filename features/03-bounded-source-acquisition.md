# Feature 03 — Bounded source acquisition

## Outcome

PathAid safely retrieves public scholarship pages and retains immutable evidence
without crossing the user's approved scope or a site's access controls.

## Requirements

- Accept public HTTP(S) text pages only.
- Validate DNS destinations and every redirect; block private, loopback,
  link-local, metadata, multicast, and unsupported addresses.
- Reject HTTPS downgrade and cap redirects, response size, time, and normalized
  characters.
- Check `robots.txt`, explicit automation rules, approved host/path, rate, depth,
  and page budget before fetching/following.
- Require an immutable user-reviewed policy assessment before a confirmed scope
  can scan. Explicit prohibitions clear queued work and block the source.
- Use a descriptive PathAid user agent and never log in or bypass CAPTCHA.
- Canonicalize URLs, normalize content, compute a SHA-256 hash, and retain an
  immutable snapshot with retrieval metadata.
- Adapters share one acquisition boundary and cannot weaken network safety.

## Acceptance criteria

- SSRF, redirect, oversized-response, timeout, robots-denied, out-of-scope, and
  page-budget fixtures fail closed.
- Same normalized content produces the same hash.
- A failed refresh never destroys the last valid snapshot.
- Generic traversal follows only scholarship-related links inside the confirmed
  host/path and configured depth.
- Tests use saved transports/fixtures and make no live network requests.
- Unknown and blocked policy states cannot scan; clearing a blocked assessment
  leaves the source paused until an explicit resume.
