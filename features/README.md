# Feature specifications

These documents break the agreed [project plan](../plan.md) into focused implementation specifications. Each feature records its current status. The root plan owns shared scope, stack, budget, and milestones.

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
- [Student web interface](13-student-web-interface.md)

## Implementation order

The backend foundation through scheduled discovery is implemented. The next active feature is the responsive student web interface, beginning with its shared shell, authentication, profile, discovery, and source-backed result flows. Add the protected administrator screens after the student flow is connected. Complete deployment after browser, accessibility, catalog, and usability checks pass.

Future agent-harness work is deferred. Broad autonomous crawling, chat, RAG, application submission, and application tracking remain outside the MVP.
