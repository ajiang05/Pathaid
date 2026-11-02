# Feature 06 — Discovery results and saved scholarships

## Outcome

The user understands why a scholarship matches and can save, skip, or begin it
without maintaining a complex application-management system.

## Requirements

- Result/detail views show official title/sponsor, award, deadline, source
  freshness, match class, requirement reasons, unknowns, preferences, materials,
  evidence, and official URL.
- Save creates visible status **Not started**.
- Apply creates/updates **In progress**, opens the official application, and
  requests the extension side panel.
- The user may mark **Already applied**.
- Skip this cycle stores the active version's material fingerprint and hides it.
- A skipped record returns only when its cycle, deadline, opening date, award,
  or eligibility materially changes.
- Automatically considered awards do not expose a misleading Apply action;
  verified sweepstakes remain separately labeled.

## Acceptance criteria

- Saved state survives restart and duplicate Save/Apply operations are idempotent.
- Cosmetic source edits do not revive skipped records.
- Any defined material change revives the record once.
- Disappeared or expired records are removed from current matches, not deleted.
- No award-result tracking or skip-reason questionnaire is present.

## Implementation status

The local API and web app now implement idempotent Save/Apply actions, the three
visible status views, removal, and cycle-level skipping. Saved state lives in
SQLite and survives restart. Skip comparison uses the active version's material
fingerprint, so cosmetic extraction changes remain hidden and material changes
return the opportunity to Discover.
