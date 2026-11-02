# PathAid Chrome extension

This unpacked Manifest V3 foundation opens a side panel, authenticates to the
loopback API, and inspects only the active page's origin and form count after an
explicit click. It does not yet read or fill fields.

Run its dependency-free checks with:

```bash
cd extension
npm test
```

Developer-mode loading and token-pairing steps are documented in
[../INSTRUCTIONS.md](../INSTRUCTIONS.md#load-the-chrome-extension).
