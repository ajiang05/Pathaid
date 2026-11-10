# Feature 11 — Essay bank and Gemini recommendations

## Outcome

The student reuses their own writing intelligently without PathAid generating or
rewriting application essays.

## Requirements

- Store essay title, full student-authored text, original prompt, tags, themes,
  word count, date, and prior scholarship use.
- Use local metadata/keyword matching before optional Gemini analysis.
- Gemini may rank existing essays and identify sections mismatched with the new
  prompt; it may not output replacement prose.
- Show the destination prompt, word limit, recommendation rationale, and
  mismatch warnings.
- When official rules prohibit AI assistance, show a warning and disable Gemini
  essay analysis for that scholarship.
- Gate full-text analysis behind explicit configuration and a clear notice about
  the configured Gemini account's data handling.
- Essay attachment follows Feature 10's explicit-click rule.

## Acceptance criteria

- Recommendation never changes the stored essay.
- AI-disabled scholarships make no essay-analysis request.
- Provider failures fall back to local recommendations without blocking apply.
- Prompts/tests reject generated or rewritten essay content.
- Full essay text and model responses are not logged.

## Implemented design

- Essays and prior-use history live in the local SQLite database. Word count is
  computed by the backend rather than trusted from the browser.
- Local title, prompt, tag, and theme matching always runs first. Gemini is an
  optional analysis layer and a provider failure returns the local result.
- The structured Gemini response can contain only essay IDs, ranking rationale,
  and mismatch references. Extra fields such as replacement prose fail schema
  validation.
- Full-text analysis requires an explicit setting and acknowledgement of a
  tier-specific Gemini data-handling notice. A validated `blocked` AI policy
  prevents the provider from being called.
- Exact essay-file inputs appear in the extension attachment preview with a
  stored-essay selector. Only the user's Attach click releases a plain-text copy;
  essay textareas, attestations, and submission remain untouched.
