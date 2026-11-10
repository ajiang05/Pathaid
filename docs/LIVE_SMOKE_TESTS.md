# Optional live-provider and real-portal smoke tests

These checks are intentionally outside normal CI. They spend Gemini quota or
touch changing third-party pages, so run them only before a tagged release with
a small explicit budget. They never submit, certify, sign, enter credentials,
or bypass a portal control.

## Budget and safety limits

- Gemini extraction: at most three changed public pages and 20,000 total input
  tokens for one release candidate.
- Portal inspection: one public or personally authenticated application each
  for generic HTML, AcademicWorks/Blackbaud, and Kaleidoscope.
- Use only scholarships the tester may legitimately view. Log in manually;
  PathAid must not receive or store the password, cookies, or MFA response.
- Stop at the reviewed preview/filled draft. Do not click Submit, certify,
  accept terms, sign, or upload a file that contains production-sensitive data.

## Public discovery/provider smoke

1. Start PathAid with `scripts/pathaid start` and confirm a narrow official
   sponsor or school path whose policy review permits automation.
2. Record the current Gemini quota, select **Scan now**, and wait for one job.
3. Verify a changed page creates one validated active version with retained
   evidence. Verify the profile never appears in provider-request diagnostics.
4. Scan the unchanged page again. Confirm freshness advances and no second
   Gemini request is made.
5. If the provider fails or quota is exhausted, confirm the prior version stays
   active and only a safe error code is shown.

## Real-portal application smoke

Repeat this procedure for one generic form, one AcademicWorks/Blackbaud form,
and one Kaleidoscope form:

1. Save the scholarship and click **Apply** from its detail page.
2. Confirm only the retained official application URL opens and the side panel
   identifies the correct scholarship and adapter.
3. Select **Inspect page**. Check that every proposed value names its profile
   source, sensitive values are marked, and ambiguous/custom fields stay empty.
4. Select **Fill application** once. Confirm only checked preview fields change.
5. If an exact résumé, transcript, or essay-file target exists, use its separate
   attachment button and verify the chosen file. Do not attach to an ambiguous
   target.
6. Confirm signatures, certifications, terms, CAPTCHA/MFA, essay textareas, and
   the portal Submit control remain untouched. Close the tab without submitting.

Record the date, portal family, scholarship ID, result, and any changed form
labels in release notes. Never record field values, page HTML, cookies, tokens,
essay text, or document contents.
