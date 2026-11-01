# Feature 02 — School onboarding and source registry

## Outcome

The user defines where PathAid may discover scholarships by confirming official
school directories and approving bounded sponsor/source scopes once.

## Requirements

- Select a U.S. institution from an authoritative local dataset.
- Propose likely official scholarship directory URLs using the institution's
  official domain, sitemaps, and bounded scholarship-related checks.
- Require one user confirmation before scanning a proposed school directory.
- Allow an explicit host plus path prefix, adapter, depth (maximum two), page
  budget, rate, scan interval, pause/resume, and scan-now action.
- Allow an individual manual lead URL/title without approving its entire domain.
- Store ownership, confirmation time, last/next scan, policy result, and errors.
- On school change, deactivate old school scopes and propose the new school's
  directories.

## Source policy

Initial automatic source types are official school/sponsor directories, public
AcademicWorks/Blackbaud, public Kaleidoscope, and generic bounded directories.
BigFuture, Scholarship America, and Bold.org are manual lead sources only.

## Acceptance criteria

- No unconfirmed scope can be scheduled.
- A path approval cannot silently expand to the whole host.
- Pause prevents scheduling; resume preserves history.
- Manual lead creation does not authorize crawling sibling pages.
- School-change tests deactivate only school-owned scopes.
