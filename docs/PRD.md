# PathAid product requirements

**Owner:** Aidan Jiang
**Status:** Approved redesign specification
**Last updated:** November 1, 2026
**Primary scope:** [MVP.md](MVP.md)

## 1. Product summary

PathAid is a personal, local-first scholarship finder and application copilot.
It discovers relevant U.S. college scholarships from approved public sources,
extracts their rules, compares them with one student's private profile, and
assists with—but never submits—applications.

The first product is macOS-only. Developers may fork it and supply their own
Gemini key. A consumer installer and Chrome Web Store release are separate
future distribution projects, not MVP promises.

## 2. Problem

Scholarships are scattered across school directories, sponsor sites, and
application portals. Requirements change by cycle, eligibility details are
buried in prose, and students repeatedly enter the same data and documents.
Aggregator listings can be stale or incomplete.

PathAid reduces this work by discovering only within defined boundaries,
verifying official sources, matching conservatively, keeping personal data
local, and preparing forms for the student to review and submit.

## 3. Goals

1. Maintain one comprehensive private student profile.
2. Discover current undergraduate-oriented scholarships from approved U.S.
   sources.
3. Separate hard eligibility requirements from selection preferences.
4. Produce reproducible Strong, Possible, and Not a match outcomes.
5. Preserve source evidence and detect cycle or material requirement changes.
6. Let the user save, skip, and minimally track applications.
7. Preview and fill supported forms through a Chrome extension.
8. Protect sensitive data, documents, keys, and credentials locally.
9. Respect robots directives, source terms, automation prohibitions, and AI-use
   restrictions.

## 4. Non-goals

- Automatic submission, signatures, attestations, or terms acceptance.
- Credential storage, MFA/CAPTCHA bypass, or access behind login walls.
- AI-written or AI-rewritten essays.
- Award prediction or sponsor-selection scoring.
- Grants, loans, food, housing, emergency aid, or other non-scholarship aid.
- High-school-senior-only or graduate-only discovery for the initial user.
- Scraping search engines or crawling the entire public web.
- Automatic crawling of BigFuture, Scholarship America, or Bold.org in v1.
- Hosted accounts, administrators, manual publication review, or a public catalog.
- Award-result tracking; the user handles results in email.
- Windows, Linux, mobile, or Chrome Web Store packaging in the MVP.

## 5. Scope and user

The sole MVP user is a current college student on macOS. Include scholarships
usable at accredited U.S. two- or four-year institutions, awards limited to the
user's current school, national/state/local/sponsor awards, and automatically
considered institutional awards. Include sweepstakes/no-essay awards only in a
separate section with verifiable official rules. Exclude opportunities without
a current official sponsor or rules page.

## 6. Product principles

1. **Official evidence wins.** Aggregators supply leads, not final eligibility.
2. **False positives are costly.** Unknown requirements produce Possible, never
   Strong.
3. **AI extracts; code decides.** Gemini structures public source material;
   deterministic code evaluates the private profile.
4. **Local by default.** Profile data, matching, mappings, documents, essays,
   and application status stay on the Mac.
5. **The student remains responsible.** PathAid fills drafts; the student checks,
   attaches, certifies, and submits.
6. **Rules override convenience.** Disable automation or AI analysis when
   official rules prohibit it.
7. **Unknown stays unknown.** Missing data is not silently treated as pass/fail.

## 7. Functional requirements

### 7.1 Profile

The profile supports identity/contact data; current school and location;
separate current and permanent residence; degree, year, major, GPA, enrollment,
and graduation; citizenship and veteran facts; optional race, ethnicity, gender,
disability, first-generation, Pell, income, and other scholarship attributes;
and structured activities, work, volunteering, memberships, leadership, honors,
skills, and interests.

Nonessential fields remain optional, and the UI explains that completeness
reduces Possible matches. Changing schools disables old school-specific sources
and begins onboarding for the new school.

### 7.2 Sources and discovery

PathAid proposes likely official directories for the selected school and the
user confirms each once. The user may approve additional official host/path
scopes or paste an individual lead URL.

Initial automatic sources are official school/sponsor directories, public
AcademicWorks/Blackbaud listings, public Kaleidoscope listings, and a generic
bounded directory adapter. BigFuture, Scholarship America, and Bold.org are
manual lead sources initially. A lead must resolve to a current official sponsor
page before it can appear as a match. The user confirms that candidate official
URL; PathAid then validates and snapshots the exact public page without
approving its surrounding domain.

Every scan stays inside an approved host/path, obeys `robots.txt` and terms,
uses a descriptive user agent and conservative rate limit, enforces one or two
link levels and a strict page budget, reads only public pages, retains snapshots
and hashes, and skips Gemini when content is unchanged. The scheduler runs daily
while the Mac is awake and performs a catch-up scan after a missed window.

Source-boundary confirmation and source-policy review are separate actions.
Unknown or explicitly blocked policies cannot scan. Policy decisions retain
their official URL and exact prohibition text when automation is blocked;
clearing a block requires a separate resume before crawling restarts.

### 7.3 Extraction and validation

Gemini extracts identity, sponsor, award, cycle, deadlines, URLs, hard
requirements, selection preferences, materials, steps, automatically-considered
status, sweepstakes rules, automation/AI restrictions, and exact evidence.

Deterministic validation rejects malformed dates, unsafe URLs, inconsistent
cycles, unsupported claims, evidence absent from the retained snapshot, and
rules that cannot be represented safely. Invalid extraction is not matched.
Valid extraction atomically creates an immutable version and makes it active;
invalid refreshes retain findings and leave the prior valid version active.
There is no reviewer or publication state.

### 7.4 Matching and ranking

Each hard requirement returns Pass, Fail, or Unknown:

- **Strong match:** every hard requirement passes.
- **Possible match:** no hard requirement fails and at least one is unknown.
- **Not a match:** at least one hard requirement fails.

Selection preferences cannot override a failure. Availability is independent:
closed, expired, or unverifiable records stay out of current results. Separate
sections hold automatically considered awards and verified sweepstakes.

Ranking is deterministic by result section, availability, deadline, source
freshness, relevance, and stable ID. Every unknown value has an explicit
ordering key.

### 7.5 Results, save, skip, and apply

Results show official identity, sponsor, award, deadline, freshness, match
class, requirement reasons, unknowns, selection preferences, materials, and the
official application URL.

- **Save** creates a **Not started** record.
- **Apply** changes it to **In progress**, opens the official application, and
  opens the extension side panel.
- **Skip this cycle** hides it until the cycle, deadline, award, eligibility, or
  opening date materially changes.

Saved scholarships visibly use **Not started**, **In progress**, and **Already
applied**. Automatically considered and skipped states may exist internally.

### 7.6 Application copilot

The Manifest V3 extension initially supports ordinary HTML forms,
AcademicWorks/Blackbaud, and Kaleidoscope. After user activation it reads
supported fields, maps them to local values, and shows one preview that marks
sensitive and ambiguous entries. One **Fill application** action fills accepted
ordinary and sensitive values; unknown and ambiguous fields stay empty.

It may learn corrected mappings by portal. It never submits, signs, certifies,
accepts terms, bypasses MFA/CAPTCHA, or stores credentials. It disables filling
when official rules explicitly prohibit automated participation.

### 7.7 Documents and essays

PathAid manages one current résumé and transcript as encrypted local copies. A
random encryption key is protected by macOS Keychain. Every résumé, transcript,
or essay attachment requires an explicit click.

The essay bank stores title, tags, original prompt, word count, date, prior use,
themes, and student-written text. Gemini may recommend an essay and identify
mismatched sections, but never generate or rewrite it. When rules prohibit AI
assistance, PathAid warns the user and disables Gemini essay analysis.

### 7.8 Backup

Encrypted backups may include profile, scholarships, essay bank, approved
sources, learned mappings, and application status. They exclude Gemini keys,
Keychain/encryption secrets, credentials, résumé content, and transcript content.

## 8. Security and privacy

- Bind FastAPI only to `127.0.0.1`.
- Require an installation-specific random token from the extension.
- Allow exact local web/extension origins and expose narrow endpoints.
- Request minimal extension permissions: `activeTab`, `scripting`, `sidePanel`,
  and loopback access.
- Keep Gemini and document-encryption keys in macOS Keychain.
- Never send private profile fields to Gemini for eligibility.
- Gate full-essay analysis behind explicit configuration and a clear data notice.
- Redact secrets and sensitive values from logs.

## 9. MVP success criteria

- A fresh macOS checkout runs from one documented command sequence.
- A user can complete a profile and confirm a school source.
- Scheduled discovery creates verified records without per-scholarship review.
- Deterministic fixtures prove all match classes and unknown boundaries.
- A skipped record reappears only after a material cycle change.
- A supported real form can be previewed and filled without submission.
- Prohibited automation and AI assistance are blocked.
- Document encryption and backup exclusions are verified.
- No core workflow requires legacy admin review, publication, or PostgreSQL.

## 10. Deferred decisions

Chrome Web Store publication, signed macOS packaging, native messaging,
Windows/Linux, paid/general search APIs, Submittable, cross-origin iframe forms,
multiple document variants, and any hosted multi-user service are post-MVP.
