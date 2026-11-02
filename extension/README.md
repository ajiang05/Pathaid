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
Kaleidoscope remains unsupported pending its dedicated adapter.

Run its dependency-free checks with:

```bash
cd extension
npm test
```

Developer-mode loading and token-pairing steps are documented in
[../INSTRUCTIONS.md](../INSTRUCTIONS.md#load-the-chrome-extension).
