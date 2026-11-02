# Feature 09 — Application form adapters

## Outcome

The extension previews and fills supported application fields while leaving all
judgment, attachments, certification, and submission with the student.

## Requirements

- Define one adapter contract for field inspection, mapping, fill, and safe
  attachment targets; it cannot expose submit/click-arbitrary-element behavior.
- Support generic visible HTML forms, AcademicWorks/Blackbaud, and Kaleidoscope.
- Map using learned portal mapping first, safe semantic/label mapping second.
- Mark sensitive fields in a single preview; skip unknown and ambiguous fields.
- One **Fill application** action may fill approved ordinary and sensitive data.
- Remember user-corrected mappings by portal and form signature.
- Never fill signatures, certifications, attestations, terms, CAPTCHA, MFA, or
  hidden anti-bot fields.
- Disable automation when official rules prohibit bots/scripts/automation.
- Defer cross-origin iframe and Submittable support.

## Acceptance criteria

- Preview shows every proposed value's profile source and sensitivity.
- Fill changes only previewed supported fields.
- Ambiguous fixtures remain untouched.
- Submit/certification controls remain untouched in adversarial fixtures.
- Smoke tests pass for a generic form and representative AcademicWorks and
  Kaleidoscope pages without submitting anything.

## Implementation status

The shared adapter contract and portal-context boundary are implemented.
Adapters may expose only `matches`, `inspect`, and `map`; action-like methods are
rejected. The central fill-plan validator admits only visible, supported,
exactly mapped, explicitly preview-approved scalar values and blocks protected
semantics. File controls use a separate résumé/transcript/essay descriptor that
always requires an explicit attachment action. DOM inspection and filling are
not implemented yet.
