# Feature 10 — Document vault and explicit attachments

## Outcome

The user can keep one current résumé and transcript encrypted locally and attach
one deliberately selected file at a time.

## Requirements

- Generate a random document-encryption key and protect it with macOS Keychain.
- Store encrypted managed copies plus non-sensitive metadata and content hash.
- Support one current résumé and one current transcript; replacement preserves
  only necessary audit metadata.
- Decrypt only for an explicit attachment action and remove temporary plaintext
  promptly.
- Require a separate user click before each résumé, transcript, or essay upload.
- Confirm the target file control type and scholarship context; never infer a
  transcript merely from a vague label.
- Exclude document bytes and document keys from backups and logs.

## Acceptance criteria

- Files are unreadable at rest without the Keychain-protected key.
- A copied app-data directory alone cannot decrypt documents.
- No file attaches without a contemporaneous user action.
- Wrong-type/ambiguous file controls remain untouched.
- Reset removes encrypted files and associated Keychain material after explicit
  destructive confirmation.
