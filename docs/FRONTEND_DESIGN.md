# PathAid local interface design

## Direction

The interface is a calm personal workspace, not a public marketplace or admin
console. It should help the student answer three questions quickly:

1. Which scholarships am I strongly or possibly eligible for?
2. What is missing, required, or due?
3. What can PathAid safely prepare while leaving final review/submission to me?

Retain the existing “Quiet Utility” visual language where practical: restrained
green, clear borders, strong text contrast, consistent cards, visible focus, and
no gamified match percentages or artificial urgency.

## Navigation

- Home
- Discover
- Saved
- Profile
- Sources
- Documents
- Settings

Remove student/admin login, admin ingestion, revision review, and publication
navigation. The local app opens directly to the single user's workspace.

## Screen contracts

### Home

Show profile completeness, last/next scan, overdue catch-up, source errors,
extension connection, and shortcuts to Strong matches and In progress items.

### Profile

Group fields into identity/contact, school and three locations, academics,
demographics/aid, citizenship, and structured experiences. Mark optional and
sensitive values clearly. Explain that completion reduces Possible matches.
Changing school previews which school sources will be deactivated.

### Discover

Show Strong first, Possible second, then separate Automatically considered and
Verified sweepstakes sections. Do not ask follow-up questions here. Not a match
may be inspectable through a filter for transparency but is not promoted.

All scholarship cards share the same grid and field order: sponsor/type, title,
award, deadline, match class, key passed/unknown reason, source freshness, and
one primary action. Missing data uses an explicit fallback, not a collapsed box.

### Scholarship detail

Separate hard requirements, selection preferences, materials, source evidence,
policy restrictions, and official links. Save/Skip/Apply feedback appears near
the clicked control and is announced accessibly; it must not appear only at the
top of a long page.

### Saved

Use three visible filters: Not started, In progress, Already applied. Skipped is
managed separately as a cycle-level hidden preference. Automatically considered
records use an informational state rather than a fake application status.

### Sources

Explain that approval authorizes a bounded directory, not an entire website.
Show adapter, host/path, school/sponsor, pause/resume, scan now, last/next scan,
page budget, and errors. Manual lead entry stores one URL and does not approve
the domain.

### Documents

Show one current résumé and transcript with replacement/removal actions and
encryption status. Essay cards show prompt, tags, themes, word count, date, and
prior use. Every attachment remains an extension-side explicit action.

### Settings

Show Gemini configured state without revealing the key, full-essay analysis
choice/data notice, extension connection, backup/restore, local diagnostics, and
destructive reset.

## Chrome side panel

The side panel has four stages:

1. **Page status:** supported, unsupported, disconnected, or policy blocked.
2. **Preview:** proposed values grouped into ordinary, sensitive, ambiguous, and
   skipped; every value names its profile source.
3. **Fill:** one Fill application action; no Submit action exists.
4. **Files:** separate explicit buttons for the relevant résumé, transcript, or
   recommended essay.

Always show that the student must review, certify, and submit. Policy warnings
must name whether automation, AI essay analysis, or both are disabled.

## Accessibility and responsiveness

- Target WCAG 2.2 AA.
- Use semantic landmarks, labels, status announcements, and visible focus.
- Provide at least 44px touch targets and never rely on color alone.
- Preserve entered values after recoverable errors.
- Mobile uses a compact navigation pattern without hiding safety information.
- Reduce motion when requested.
- Ensure preview tables/cards are keyboard navigable and sensitive indicators
  have text equivalents.

## State language

- Eligibility: Strong match, Possible match, Not a match.
- Requirement: Pass, Unknown, Fail.
- Saved: Not started, In progress, Already applied.
- Availability: Verified open, unavailable/expired, or verifying.

Avoid “guaranteed,” “best chance,” “approved,” or predicted award language.
