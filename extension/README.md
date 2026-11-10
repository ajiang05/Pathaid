# PathAid Chrome extension

This unpacked Manifest V3 extension opens a side panel, authenticates to the
loopback API, and inspects only visible field metadata after an explicit click.

The shared adapter contract is descriptive by design: adapters can match,
inspect, and map, but cannot click, submit, sign, certify, or accept terms. An
authenticated backend context lookup also requires the active portal origin to
match an **In progress** scholarship before inspection proceeds.

The generic adapter shows exact mappings in one ordinary/sensitive preview and
fills explicitly approved values. It skips ambiguous, unknown, hidden, action,
credential, certification, consent, signature, CAPTCHA, and MFA controls.
AcademicWorks/Blackbaud application forms use a dedicated conservative mapping
adapter. Because each institution configures its own questions, PathAid fills
only exact supported wording and otherwise leaves the question untouched.
Kaleidoscope applications use the same conservative approach: exact reusable
learner-profile questions are supported, while sponsor-specific questions,
essay textareas, certifications, and submission remain untouched. Exact résumé,
transcript, and essay-file inputs use a separate explicit attachment action.

Safe preview rows also allow the student to correct their profile source. The
local API remembers only value-free portal/form/field signatures and the chosen
profile field; a changed form shape fails closed and requires another review.
If the validated active scholarship version says official rules prohibit
automation, the backend releases neither the profile nor mappings and the panel
shows that automation is disabled.

From the local web interface, **Apply** sends only a scholarship ID. PathAid's
authenticated backend returns the retained official application URL to the
extension, which owns the new tab and opens the side panel. Direct-link fallback
still works when the unpacked extension is not loaded.

Run its dependency-free checks with:

```bash
cd extension
npm test
```

Developer-mode loading and token-pairing steps are documented in
[../INSTRUCTIONS.md](../INSTRUCTIONS.md#load-the-chrome-extension).
