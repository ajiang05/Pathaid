# Feature specifications

<<<<<<< HEAD
These documents break the agreed [project plan](../plan.md) into focused implementation specifications. Each feature records its current status. The root plan owns shared scope, stack, budget, and milestones.
=======
These documents break the agreed [project plan](../plan.md) into focused implementation specifications. Each feature records whether its foundation is implemented or still planned. The root plan owns shared scope, stack, budget, and milestones; update it alongside any feature-scope changes.
>>>>>>> 0aac2eb63c2ef53e9ae0503876e809002f385290

## Student features

- [Student account and editable profile](01-student-intake.md)
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

Start with student accounts, the profile registry, catalog, and eligibility engine. Build source acquisition, extraction, orchestration, and review before scheduled discovery. Add relevant evaluations and observability as each feature is implemented; complete the frontend and deployment after release checks pass.

Future agent-harness work is deferred. Broad autonomous crawling, chat, RAG, application submission, and application tracking remain outside the MVP.
