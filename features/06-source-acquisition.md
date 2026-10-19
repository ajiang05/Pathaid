# Official source acquisition and provenance

Status: implemented for individual webpages and pasted text; scheduled-source and discovery-page support is planned. Parent specification: [plan.md](../plan.md).

## Goal
Turn an approved manual or scheduled source into bounded, inspectable text for extraction.

## Scope and behavior
- Accept an official public HTTP(S) URL or pasted text with a source URL.
- Accept scheduled URLs only from the administrator-managed source registry.
- Preserve normalized source text, URL, acquisition method/time, and content hash before extraction.
- Label pasted text as administrator-supplied rather than automatically checked against the live URL.
- Validate destinations and every redirect; block local, private, and reserved addresses and prevent DNS rebinding bypasses.
- Bound redirects, response size, and request duration. Accept supported text content only.
- Treat source text as untrusted data, never as instructions granting tools or publication authority.
- Return structured acquisition errors to the workflow. Avoid duplicating source bodies in operational logs.
- For scheduled scans, respect robots directives, configured scope, and per-host request delays.
- Approved discovery pages may yield canonical same-host candidate links within path and count limits.

## Interfaces and dependencies
An authenticated admin request or the [scheduled discovery service](12-scheduled-scholarship-discovery.md) selects an approved source. The [orchestrator](08-ingestion-orchestration.md) passes changed snapshots to [extraction](07-ai-requirement-extraction.md).

## Acceptance criteria
- Both URL and pasted-text paths create traceable snapshots.
- Private addresses, unsafe redirects, unsupported content, oversize responses, and timeouts are handled without extraction or publication.
- External instructions cannot alter the workflow or its permissions.
- An unchanged scheduled source records freshness without invoking extraction.
- Discovered links stay within configured host/path scope and remain private candidates.

## Exclusions
PDFs, student uploads, broad or multi-hop crawlers, search-engine scraping, and bypassing source access restrictions.
