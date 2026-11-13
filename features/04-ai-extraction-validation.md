# Feature 04 — AI extraction and deterministic validation

## Outcome

Local Qwen3 through Ollama converts changed public source content into structured scholarship facts;
deterministic validation decides whether the result is safe to activate.

## Requirements

- Send only public source content and provenance—not the student profile—to
  loopback Ollama through a constrained schema. Never call Gemini for
  scholarship extraction.
- Extract sponsor, title, award, cycle, deadlines, official/application URLs,
  hard eligibility, selection preferences, materials, steps, automatic-
  consideration status, sweepstakes rules, automation restrictions, AI-policy
  restrictions, and exact supporting evidence.
- Classify “required leadership” as hard eligibility and “leadership considered”
  as a selection preference.
- Validate types, operands, dates, cycles, URL safety, evidence occurrence,
  claim support, and coverage deterministically.
- Invalid output records findings and leaves the prior valid version active.
- A page-level local failure does not stop extraction of remaining pages.
- Unchanged source hashes skip model extraction entirely.
- A valid result creates an immutable version and atomically advances the local
  scholarship's active-version pointer without review or publication state.

## Acceptance criteria

- Extraction cannot activate a record without validation.
- Replaying the same snapshot and structured draft does not duplicate a version.
- Unsupported requirements and fabricated evidence fail validation.
- Mandatory conditions that cannot be represented prevent Strong matching.
- Provider timeout/refusal/quota behavior is bounded and visible without leaking
  prompts, source secrets, or keys.
- Saved benchmark fixtures cover common academic, location, demographic,
  membership, experience, deadline, and policy language.
- Automatic consideration requires exact retained evidence. Sweepstakes also
  require a validated public official-rules URL and exact rules-link evidence;
  neither classification may be inferred from an opportunity's title.

## Implementation status

Schema 1.2 extracts separate automation and AI-assistance policy outcomes.
Blocked outcomes require exact retained evidence, and deterministic validation
additionally requires explicit prohibition language rather than a vague rules
reference. The active immutable scholarship version carries the validated flags.
Qwen3 4B is the default local provider on the supported 8 GB Mac; the local
request uses an 8K context, thinking disabled, bounded output, loopback-only
transport, and full deterministic validation before activation.
