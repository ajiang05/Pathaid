# Feature specifications

These documents break the agreed [project plan](../plan.md) into focused implementation specifications. Each feature records whether its foundation is implemented or still planned. The root plan owns shared scope, stack, budget, and milestones; update it alongside any feature-scope changes.

## Student features

- [Student intake and transient profile](01-student-intake.md)
- [Personalized scholarship and assistance discovery](02-personalized-discovery.md)
- [Deterministic eligibility and follow-up questions](03-eligibility-engine.md)
- [Source-backed results and application checklists](04-results-and-checklists.md)

## Catalog and AI administration

- [Verified program catalog and revision storage](05-program-catalog.md)
- [Official source acquisition and provenance](06-source-acquisition.md)
- [AI program and scholarship requirement extraction](07-ai-requirement-extraction.md)
- [Durable AI ingestion orchestration](08-ingestion-orchestration.md)
- [Protected admin review and publication](09-admin-review-and-publication.md)
- [Scheduled scholarship discovery and refresh](12-scheduled-scholarship-discovery.md)

## Quality and delivery

- [Reproducible eligibility and extraction evaluations](10-quality-evaluations.md)
- [Reproducible local setup and hosted demo](11-demo-deployment.md)

## Implementation order

Start with the profile registry, catalog, and eligibility engine. Connect intake, discovery, and checklists. Build source acquisition, extraction, orchestration, and admin review before adding the daily scheduler and approved-source registry. Add relevant evaluations as each feature is implemented and complete deployment after the release checks pass. Document numbers are identifiers, not a strict build sequence.

Future agent-harness work is described as deferred in the orchestration specification. Broad autonomous crawling, chat, RAG, application submission, and application tracking remain outside the MVP.
