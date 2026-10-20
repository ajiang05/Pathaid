# PathAid frontend design and implementation contract

Status: implemented for the MVP. Last verified: October 20, 2026.

## Product direction

PathAid serves students who need a calm way to find reviewed scholarships and assistance programs, understand why a result applies to them, and continue to the official provider. Administrators use a separate workspace to monitor sources and ingestion and to approve revisions before publication.

The interface follows the supplied Google Stitch artifacts in `stitch_ui_screen_implementation/`. Its visual direction is **Quiet Utility**: clear, supportive, restrained, and trustworthy. It avoids gamification, artificial urgency, award predictions, and unsupported match scores.

## Technology and accessibility

- Next.js App Router 16, React 19, and TypeScript
- Tailwind CSS 4 plus shared semantic CSS classes in `frontend/src/app/globals.css`
- Custom semantic HTML components with no client component library
- Inter when available, followed by system sans serif fonts
- Current evergreen browsers supported by Next.js 16
- WCAG 2.2 AA target, semantic landmarks, visible keyboard focus, 44px controls, text paired with status color, and reduced motion support

The browser calls relative `/api/*` paths. Next.js proxies them to `PATHAID_API_URL`, preserving same-origin HttpOnly session cookies. Eligibility, ranking, evidence, publication status, and profile validation always come from the backend.

## Design tokens

Tokens live in `frontend/src/app/globals.css` and originate in `stitch_ui_screen_implementation/pathaid/DESIGN.md`.

| Purpose | Token | Value |
| --- | --- | --- |
| Page canvas | `--background` | `#FAFAF7` |
| Primary text | `--foreground` | `#24382D` |
| Card surface | `--surface` | `#FFFFFF` |
| Muted surface | `--surface-muted` | `#F0F4EF` |
| Primary action | `--primary` | `#084C33` |
| Supporting text | `--muted-foreground` | `#52665A` |
| Border | `--border` | `#D8E2D9` |
| Focus ring | `--ring` | `#286449` |
| Success | `--success` | `#246B4C` |
| Warning | semantic component value | `#895400` |
| Destructive | semantic component value | `#A92D32` |

The base spacing rhythm is 4px. Common spacing uses 8, 16, 24, 32, and 48px. Controls use an 8px radius, structural cards use 12px, and pills use a full radius. Cards use a one pixel border and generally no shadow. Long prose is limited to about 68 characters per line. Monetary and date facts use tabular figures where alignment matters.

## Responsive behavior

- **Mobile, below 640px:** one column, 16px page margins, stacked actions, single column choices and facts.
- **Tablet, 640–899px:** fluid one or two column content with 24px gutters.
- **Desktop, 900px and wider:** 240px student sidebar and a workspace capped at 1180px.
- The student sidebar becomes a header and fixed three item bottom navigation below 900px. Safe area insets protect the bottom navigation.
- Admin navigation wraps at mobile sizes; source and run rows become cards and review columns stack.
- Tables are avoided for core MVP tasks so critical state never disappears through horizontal clipping.

## Route contract

| Route | User goal and main action | Required states |
| --- | --- | --- |
| `/` | Understand PathAid and create a profile | Responsive marketing content and trust explanation |
| `/signup` | Create a student account | Pending, validation error, service failure |
| `/login` | Resume a student account | Pending, invalid credentials, service failure |
| `/onboarding` | Save the five core matching fields | Registry loading, save error, redirect to discovery |
| `/home` | See profile readiness and start discovery | Loading, incomplete profile, ready, API failure |
| `/discover` | Review deterministic grouped results and answer temporary follow-ups | Loading, empty catalog, missing profile, API failure, open/unknown/closed availability groups |
| `/programs/[id]` | Inspect criteria, evidence, checklist, unresolved conditions, and official links | Loading, absent from current results, API failure, explanation fallback |
| `/profile` | Edit saved answers, consent, or delete the account | Loading, saved, validation error, delete confirmation |
| `/privacy` | Understand data use and matching limits | Readable long-form content |
| `/admin/login` | Start an administrator session | Pending, invalid credentials, service failure |
| `/admin/sources` | Register, pause, resume, edit, and scan approved sources | Loading, empty, scan outcome, failure, scheduled source metadata |
| `/admin/ingestion` | Create and monitor manual or scheduled ingestion work | Loading, empty, queued/running/failed/draft/published, retry failure |
| `/admin/revisions/[id]` | Compare source material, edit structured data, approve, or reject a draft | Loading, not found, malformed JSON, mutation failure |

Student navigation is landing → authentication → onboarding → home/discovery → detail → official provider. Administrator navigation is login → sources or ingestion → revision review. Student and administrator sessions remain separate.

## Component rules

- Links navigate and buttons perform actions. Every control has a visible result.
- Primary buttons use the deep green fill. Outline and quiet buttons carry secondary actions. Destructive red is reserved for account deletion and rejection.
- Labels appear above inputs. Sensitive and optional fields explain that they may be skipped or removed. Recoverable errors retain entered values.
- Program cards show category, name, verified amount or fallback, eligibility label, deadline, availability, missing answer count, and a detail link.
- Eligibility labels use backend wording. Unknown answers and unknown availability remain explicit and never appear as failure.
- Loading panels reserve space. Empty and error panels name what happened and provide a next action when retry is possible.
- Official source links open in a new tab with `noopener noreferrer`.

## Privacy and product boundaries

The frontend does not make eligibility decisions, reorder API results, or expose unpublished revisions. Temporary follow-up answers are sent only with the current evaluation. Saved values are changed only through profile actions protected by CSRF. Optional AI wording requires profile consent and never changes eligibility or rank.

Saved scholarships, application tracking, notifications, award predictions, sponsored ranking, and provider self-service are outside the MVP.

## Verification contract

The frontend is complete when all of these pass:

```bash
cd frontend
npm run lint
npm run build
npm run test:e2e
```

Browser tests run the landing and authenticated discovery/detail paths in desktop Chromium and a mobile Chromium viewport with deterministic mocked API responses. CI repeats lint, build, browser tests, and the production container build without live AI calls.
