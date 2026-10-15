# Protected admin review and publication

Status: backend administrator authentication, protected ingestion inspection, draft editing and revalidation, revision history, rejection, atomic publication, and copy-on-edit replacement drafts implemented; admin frontend and deployed PostgreSQL concurrency verification remain pending. Parent specification: [plan.md](../plan.md).

The backend review workflow is complete without frontend screens. A wireframe is required before implementing the source-and-draft comparison interface.

## Goal
Give one administrator control over the accuracy and publication of AI-generated program drafts.

## Scope and behavior
- Provide login/logout with deployment-supplied credentials and no public registration.
- Use expiring HttpOnly cookies, secure production cookies, CSRF protection, login throttling, and server-side authorization for every admin operation.
- Show source text beside extracted fields, rules, completeness findings, and unsupported conditions.
- Allow editing, rejection, and explicit approval. Edits invalidate validation and require revalidation.
- Require the reviewer to attest to source accuracy and record whether eligibility coverage is complete. Incomplete programs may publish only with unresolved conditions retained and conservative screening.
- Keep published revisions immutable. Atomically change the program’s published pointer and write the review event on approval.
- Record reviewer, timestamp, decision, notes, and revision. Rejection or failed ingestion must not replace current published data.
- Expose revision history and ingestion diagnostics through protected APIs and UI.

## Interfaces and dependencies
Use [catalog](05-program-catalog.md) storage and [orchestration](08-ingestion-orchestration.md) run state. Public readers never receive drafts through admin paths.

## Acceptance criteria
- Unauthorized and CSRF-invalid mutation attempts fail.
- Invalid drafts cannot publish, and valid drafts require explicit approval.
- Editing a published program creates a draft; rejection preserves its public version.
- Concurrent or repeated approvals cannot produce inconsistent publication pointers or review events.

## Exclusions
Multiple admin roles, public registration, and automatic model approval.
