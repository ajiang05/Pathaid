# Feature 13 — Backup, privacy, and security

## Outcome

Local-first operation has explicit trust boundaries, recoverable user data, and
testable guarantees about what never leaves or enters a backup.

## Requirements

- Bind API to loopback and reject unapproved Host/Origin values.
- Store Gemini, installation, and document keys in macOS Keychain.
- Redact secrets and sensitive values from logs and error responses.
- Never send profile data to Gemini for eligibility.
- Encrypt and version backups containing profile, scholarship/source records,
  essay bank, mappings, and saved/application status.
- Exclude API/encryption/install keys, credentials, browser data, résumé bytes,
  and transcript bytes.
- Restore into a temporary database, validate integrity/schema, then replace.
- Factory reset requires explicit confirmation and reports what will be removed.
- Document the privacy implications of optional full-essay Gemini analysis.

## Acceptance criteria

- Network tests prove the API is not reachable on non-loopback interfaces under
  default startup.
- Backup inspection tests prove every exclusion.
- Tampered/incompatible backups fail without changing current data.
- Logs from profile, extension, extraction, and document operations contain no
  seeded secret canaries.
- Dependency and extension-permission checks run in CI.
