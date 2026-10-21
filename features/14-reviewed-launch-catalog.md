# Reviewed launch catalog

Status: intake workflow and first official-source candidate manifest implemented; human review and publication pending. Parent specifications: [plan.md](../plan.md), [MVP](../docs/MVP.md), and [verified catalog](05-program-catalog.md).

## Goal

Prepare, review, and publish a useful 10–20 program launch catalog without treating automated extraction or source discovery as human approval.

## Workflow

1. Maintain official source candidates in `backend/data/catalog_intake_v1.json`.
2. Validate size, unique sources, category coverage, scholarship count, and geographic breadth in CI.
3. Queue candidates through the existing durable ingestion workflow.
4. Acquire and retain source snapshots, extract proposals, and run deterministic validation.
5. Compare every proposal with its retained official source in the administrator interface.
6. Correct unsupported fields, preserve unresolved conditions, and approve or reject explicitly.
7. Export only approved current publications with `python -m app.catalog_seed export`.
8. Re-import that reviewed bundle for local demos and deployment.

The intake manifest is a work queue. Its names, URLs, and research notes are not published catalog records and do not represent completed verification.

## Commands

From `backend/`:

```bash
.venv/bin/python -m app.catalog_intake validate
.venv/bin/python -m app.catalog_intake queue
.venv/bin/python -m app.worker --once
```

Run the worker repeatedly or continuously until candidates reach review or a clear failure. A key for the configured Gemini or OpenAI provider is required for live extraction, while validation and the student experience over an already reviewed bundle do not require one.

## Acceptance criteria

- Intake contains 10–20 unique official HTTPS sources.
- It includes at least four scholarships and at least two scholarships beyond one institution.
- Scholarships, grants, food, emergency, and housing are all represented.
- Queuing is idempotent and creates no program or publication directly.
- Every published revision has retained source evidence, a verification date, and one real approval event.
- Closed programs remain labeled closed; missing or provider-only conditions remain unresolved.
- The final reviewed bundle supports student matching without live AI calls.
