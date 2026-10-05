# Official source acquisition and provenance

Status: internal validation, bounded webpage acquisition, normalization, provenance persistence, migration, and mocked tests implemented; admin/orchestrator integration and PostgreSQL verification pending. Parent specification: [plan.md](../plan.md).

## Goal
Turn an administrator-supplied source into bounded, inspectable text for extraction.

## Scope and behavior
- Accept an official public HTTP(S) URL or pasted text with a source URL.
- Preserve normalized source text, URL, acquisition method/time, and content hash before extraction.
- Label pasted text as administrator-supplied rather than automatically checked against the live URL.
- Validate destinations and every redirect; block local, private, and reserved addresses and prevent DNS rebinding bypasses.
- Bound redirects, response size, and request duration. Accept supported text content only.
- Treat source text as untrusted data, never as instructions granting tools or publication authority.
- Return structured acquisition errors to the workflow. Avoid duplicating source bodies in operational logs.

## Interfaces and dependencies
An authenticated admin ingestion request supplies the source. The [orchestrator](08-ingestion-orchestration.md) invokes acquisition and passes the saved snapshot to [extraction](07-ai-requirement-extraction.md).

## Acceptance criteria
- Both URL and pasted-text paths create traceable snapshots.
- Private addresses, unsafe redirects, unsupported content, oversize responses, and timeouts are handled without extraction or publication.
- External instructions cannot alter the workflow or its permissions.

## Exclusions
PDFs, student uploads, link-following crawlers, and bypassing source access restrictions.
