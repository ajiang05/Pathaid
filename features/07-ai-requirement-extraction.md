# AI program and scholarship requirement extraction

Status: structured schema, deterministic evidence/rule validation, configurable OpenAI adapter, offline stub, and 10-case benchmark harness implemented; ingestion-run persistence, admin review integration, and a separately budgeted live-model benchmark remain pending. Parent specification: [plan.md](../plan.md).

## Goal
Convert official source text into structured, evidence-backed drafts that an administrator can review.

## Scope and behavior
- Use OpenAI schema-constrained extraction behind a small adapter with an environment-configurable model.
- Extract program details, proposed eligibility rules, evidence excerpts, application materials, and unresolved conditions.
- For scholarships, extract cycle, amount, deadline/timezone, and distinguish mandatory criteria from selection preferences.
- Validate schema, allowlisted fields/operators, operand types, and excerpt occurrence in the retained snapshot.
- Preserve ambiguous or unsupported requirements as unresolved. Schema validity and matching excerpts do not prove semantic correctness or completeness.
- Surface refusals, invalid output, unsupported logic, and configuration errors for review or failure handling.
- Record model, prompt, and schema versions plus token usage when available.
- This extraction model receives official program text, never student profiles, and has no publishing authority. Student recommendation explanations use a separate, consent-gated model path.

## Interfaces and dependencies
Input: saved [source snapshot](06-source-acquisition.md). Output: proposed revision plus validation findings for [admin review](09-admin-review-and-publication.md), managed by the [orchestrator](08-ingestion-orchestration.md).

## Acceptance criteria
- Structured outputs are validated before entering review; invented excerpt references fail validation.
- Scholarship preferences do not silently become disqualifying rules.
- Missing key, refusal, invalid fields, and ambiguous evidence have explicit outcomes.
- Run the fixed extraction benchmark described in [evaluations](10-quality-evaluations.md); record actual results.

## Current verification
- The offline suite validates all 10 versioned synthetic benchmark records and their manually labeled evidence spans.
- Adapter tests use a deterministic provider stub and exercise missing-key, refusal, invalid-output, transient-provider, and oversized-source outcomes without an API key.
- The benchmark metric harness is tested with explicit numerators and denominators. No live-model quality result is claimed yet; that run is explicit and separately budgeted as required by Feature 10.

## Exclusions
Student-facing model calls from the extraction workflow, RAG, and autonomous tool selection.
