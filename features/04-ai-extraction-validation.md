# Feature 04 — AI extraction and deterministic validation

## Outcome

Gemini converts changed public source content into structured scholarship facts;
deterministic validation decides whether the result is safe to activate.

## Requirements

- Send only public source content and provenance—not the student profile—to
  Gemini through a strict schema.
- Extract sponsor, title, award, cycle, deadlines, official/application URLs,
  hard eligibility, selection preferences, materials, steps, automatic-
  consideration status, sweepstakes rules, automation restrictions, AI-policy
  restrictions, and exact supporting evidence.
- Classify “required leadership” as hard eligibility and “leadership considered”
  as a selection preference.
- Validate types, operands, dates, cycles, URL safety, evidence occurrence,
  claim support, and coverage deterministically.
- Invalid output records findings and leaves the prior valid version active.
- Unchanged source hashes skip Gemini entirely.

## Acceptance criteria

- Extraction cannot activate a record without validation.
- Unsupported requirements and fabricated evidence fail validation.
- Mandatory conditions that cannot be represented prevent Strong matching.
- Provider timeout/refusal/quota behavior is bounded and visible without leaking
  prompts, source secrets, or keys.
- Saved benchmark fixtures cover common academic, location, demographic,
  membership, experience, deadline, and policy language.
