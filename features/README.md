# PathAid feature specifications

These files define the approved local-first product in implementation order.
They replace the prior hosted, multi-user, administrator-review feature set.
Feature completion is recorded only in [../plan.md](../plan.md).

| # | Feature | Depends on |
| --- | --- | --- |
| 01 | [Local foundation and profile](01-local-foundation-profile.md) | — |
| 02 | [School onboarding and source registry](02-school-onboarding-source-registry.md) | 01 |
| 03 | [Bounded source acquisition](03-bounded-source-acquisition.md) | 02 |
| 04 | [AI extraction and deterministic validation](04-ai-extraction-validation.md) | 03 |
| 05 | [Eligibility, availability, and ranking](05-eligibility-ranking.md) | 01, 04 |
| 06 | [Discovery results and saved scholarships](06-results-saved-scholarships.md) | 05 |
| 07 | [Scheduled discovery and change detection](07-scheduled-discovery.md) | 02–04 |
| 08 | [Chrome extension foundation](08-chrome-extension-foundation.md) | 01, 06 |
| 09 | [Application form adapters](09-application-form-adapters.md) | 08 |
| 10 | [Document vault and attachments](10-document-vault.md) | 08 |
| 11 | [Essay bank and recommendations](11-essay-bank.md) | 01, 08 |
| 12 | [Local web interface](12-local-web-interface.md) | 01–07, 10–11 |
| 13 | [Backup, privacy, and security](13-backup-privacy-security.md) | 01–12 |
| 14 | [macOS packaging and release quality](14-macos-packaging-quality.md) | 01–13 |

## Cross-feature invariants

- PathAid is single-user and local-first; no student/admin accounts exist.
- Gemini extracts public requirements but never determines eligibility.
- Strong requires all hard requirements to pass; unknown produces Possible.
- Aggregator listings require current official-source verification.
- The extension never submits, signs, certifies, accepts terms, or bypasses
  CAPTCHA/MFA.
- Every file attachment requires an explicit user click.
- Source rules can disable automation or AI assistance.
- Secrets, credentials, and plaintext sensitive documents never enter logs or
  backups.
