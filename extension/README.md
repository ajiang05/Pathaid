# PathAid Chrome extension

This unpacked Manifest V3 foundation opens a side panel, authenticates to the
loopback API, and inspects only the active page's origin and form count after an
explicit click. It does not yet read or fill fields.

The shared adapter contract is descriptive by design: adapters can match,
inspect, and map, but cannot click, submit, sign, certify, or accept terms. An
authenticated backend context lookup also requires the active portal origin to
match an **In progress** scholarship before later inspection work may proceed.

Run its dependency-free checks with:

```bash
cd extension
npm test
```

Developer-mode loading and token-pairing steps are documented in
[../INSTRUCTIONS.md](../INSTRUCTIONS.md#load-the-chrome-extension).
