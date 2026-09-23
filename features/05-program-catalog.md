# Verified program catalog and revision storage

Status: planned MVP feature; not yet implemented. Parent specification: [plan.md](../plan.md).

## Goal
Maintain a small, reliable catalog that supports personalized scholarship and benefits screening.

## Scope and behavior
- Curate 10–20 official university, government, and provider resources, including at least four merit-/need-based scholarships and at least two scholarships available beyond UMass.
- Cover national resources plus Massachusetts and UMass Amherst examples. Verify sources and current award cycles before publication.
- Store stable program identities with a pointer to the current published revision.
- Revisions contain categories, coverage, descriptions, checklist data, eligibility trees, completeness declarations, source references, and review metadata.
- Scholarship revisions additionally retain award cycle, deadline/timezone when stated, open/closed/unknown availability, and selection factors separately from eligibility rules.
- Store source snapshots and review events. Preserve published revisions as immutable records; edits create drafts.
- Use PostgreSQL migrations and an explicit reviewed-seed import. Never manufacture a human review event or import draft examples as verified programs.
- Student account/profile storage belongs to [student account and profile](01-student-intake.md), outside the catalog schema. Do not create application-tracking tables.

## Interfaces and dependencies
Public `GET /api/programs` and `GET /api/programs/{id}` expose published information only. [Review and publication](09-admin-review-and-publication.md) controls changes; [source acquisition](06-source-acquisition.md) supplies provenance.

## Acceptance criteria
- Seed catalog meets the size and scholarship coverage targets with reviewer, source, and verification dates.
- Drafts and rejected revisions never appear in public reads.
- Editing or rejecting a replacement draft preserves the previously published version.
- Migrations work against PostgreSQL; matching from seed data needs no AI key.

## Exclusions
Comprehensive national coverage and automatic renewal of expired award cycles.
