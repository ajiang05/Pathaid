# Pathaid Frontend Design and Implementation Contract

## Automation workflow addendum

The detailed visual system remains pending approved Google Stitch artifacts.
The revised MVP adds one required administrator route and updates the ingestion
workflow. Do not begin frontend implementation until those wireframes are
provided.

- **Route:** `/admin/sources`
- **Purpose:** Register, enable, pause, edit, and manually scan approved program
  pages and bounded discovery pages.
- **Primary content:** Last and next scan, cadence, timezone, allowed host/path,
  enabled state, change result, failures, candidates, and linked review work.
- **Primary actions:** Add source, save source, pause/resume, and scan now.
- **States:** No sources, due, scanning, unchanged, changed, candidates found,
  overdue, rate limited, robots disallowed, failed, and paused.
- **Safety copy:** An unchanged check may update freshness automatically. New
  scholarships and material changes remain private until administrator approval.
- **Responsive behavior:** Desktop may use a sortable table with a detail panel;
  mobile must use readable cards and must not hide failure or review state.

`/admin/ingestion` must identify whether a run was manual or scheduled and link
to its source and scan. `/admin/revisions/[id]` must identify new candidates and
material changes and show current published values beside proposed values.

The student UI does not need a scheduler screen. It continues to show each
published revision's verification date and source evidence.

> Replace all `[PLACEHOLDERS]` before use. This document is the frontend
> source of truth for UI development, including AI coding agents. Do not
> use it to define backend architecture.

## 0. Project metadata

-   **Project:** \[NAME\]
-   **Frontend stack:** \[Next.js / React / Vue / other\]
-   **Language:** \[TypeScript\]
-   **Styling:** \[Tailwind / CSS Modules / other\]
-   **UI primitives:** \[shadcn/ui / Radix / MUI / custom\]
-   **Icons:** \[Lucide / other\]
-   **Fonts:** \[FONT FAMILY AND WEIGHTS\]
-   **Design references:** \[FIGMA OR URLS\]
-   **Supported browsers:** \[BROWSERS AND VERSIONS\]
-   **Target accessibility:** WCAG 2.2 AA
-   **Owner / last updated:** \[OWNER / DATE\]

## 1. Product UI direction

### 1.1 Audience and jobs to be done

-   **Primary user:** \[WHO\]
-   **Primary user task:** \[WHAT\]
-   **Secondary tasks:** \[WHAT\]
-   **Critical screens:** \[LIST\]
-   **Primary platform:** \[DESKTOP / MOBILE / BOTH\]

### 1.2 Visual identity

-   **Design adjectives:** \[3--5 ADJECTIVES\]
-   **Desired feel:** \[HOW UI SHOULD FEEL\]
-   **References:** \[LINK + SPECIFIC PATTERN TO ADOPT\]
-   **Anti-references:** \[PATTERNS TO AVOID\]
-   **Visual priorities:** 1. Clarity 2. Consistency 3. Accessibility 4.
    Polish, unless changed here: \[ORDER\]

### 1.3 Non-negotiable rules

1.  Reuse existing components and tokens before introducing new ones.
2.  Never use arbitrary colors, spacing, shadows, or font sizes if a
    token exists.
3.  Every interactive control must have a functional outcome.
4.  Design loading, empty, error, success, focus, and disabled states as
    applicable.
5.  Mobile layouts must be intentionally designed, not merely
    scaled-down desktop views.
6.  Never silently replace product requirements with visually convenient
    behavior.

## 2. Design tokens

Implement in \[PATH, e.g., `src/styles/tokens.css` or
`tailwind.config.ts`\]. Do not hardcode these values across individual
components.

### 2.1 Semantic colors

  Token                    Light     Dark      Purpose
  ------------------------ --------- --------- --------------------
  `--background`           \[HEX\]   \[HEX\]   Page canvas
  `--foreground`           \[HEX\]   \[HEX\]   Primary text
  `--surface`              \[HEX\]   \[HEX\]   Cards/panels
  `--surface-muted`        \[HEX\]   \[HEX\]   Secondary regions
  `--primary`              \[HEX\]   \[HEX\]   Primary CTA
  `--primary-foreground`   \[HEX\]   \[HEX\]   CTA text
  `--secondary`            \[HEX\]   \[HEX\]   Secondary controls
  `--muted-foreground`     \[HEX\]   \[HEX\]   Supporting text
  `--border`               \[HEX\]   \[HEX\]   Borders/dividers
  `--ring`                 \[HEX\]   \[HEX\]   Focus ring
  `--success`              \[HEX\]   \[HEX\]   Success
  `--warning`              \[HEX\]   \[HEX\]   Warning
  `--destructive`          \[HEX\]   \[HEX\]   Errors/deletion

-   **Dark mode:** \[SUPPORTED / NOT SUPPORTED\]
-   **Color contrast:** WCAG 2.2 AA minimum; check actual
    foreground/background combinations.
-   **Status:** Always pair colors with meaningful text/icons.

### 2.2 Typography

  Role      Font       Size       Weight       Line height   Tracking
  --------- ---------- ---------- ------------ ------------- -----------
  Display   \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]
  H1        \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]
  H2        \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]
  H3        \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]
  Body      \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]
  Small     \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]
  Label     \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]
  Caption   \[FONT\]   \[SIZE\]   \[WEIGHT\]   \[VALUE\]     \[VALUE\]

-   **Heading capitalization:** \[SENTENCE / TITLE CASE\]
-   **Max reading width:** \[CH OR PX\]
-   **Truncation:** \[WHEN TO TRUNCATE VS WRAP\]
-   **Font fallback:** \[STACK\]

### 2.3 Spacing and geometry

-   **Base spacing unit:** \[4px / 8px\]
-   **Approved spacing scale:** \[0, 4, 8, 12, 16, 24, 32, 48, 64\]px
-   **Radius scale:** \[4, 8, 12, 16, full\]px
-   **Border widths:** \[1px DEFAULT, OTHER CASES\]
-   **Shadows:** \[NONE / NAMED TOKENS WITH CSS VALUES\]
-   **Icon sizes:** \[16 / 20 / 24\]px
-   **Control heights:** \[SM / MD / LG\]
-   **Minimum touch target:** \[SIZE AND EXCEPTIONS\]
-   **Z-index layers:** \[BASE / STICKY / POPOVER / MODAL / TOAST\]

## 3. Responsive layout

### 3.1 Breakpoints

  Name      Width       Columns    Gutter      Behavior
  --------- ----------- ---------- ----------- ---------------
  Mobile    \[RANGE\]   \[1\]      \[VALUE\]   \[STACK\]
  Tablet    \[RANGE\]   \[2\]      \[VALUE\]   \[ADAPT\]
  Desktop   \[RANGE\]   \[GRID\]   \[VALUE\]   \[FULL NAV\]
  Wide      \[RANGE\]   \[GRID\]   \[VALUE\]   \[MAX WIDTH\]

-   **Content max width:** \[VALUE\]
-   **Sidebar width / collapsed width:** \[VALUES\]
-   **Header height:** \[VALUE\]
-   **Sticky behavior:** \[WHICH ELEMENTS\]
-   **Horizontal overflow:** \[TABLES / CHARTS / CODE HANDLING\]
-   **Container queries:** \[WHEN TO USE\]
-   **Safe areas:** \[MOBILE NOTCH / INSETS\]

### 3.2 Responsive rules

1.  Navigation: \[DESKTOP → MOBILE TRANSFORMATION\].
2.  Multi-column layouts: \[WHEN AND HOW TO STACK\].
3.  Tables: \[SCROLL / CARD VIEW / COLUMN PRIORITIZATION\].
4.  Dialogs: \[CENTERED → FULL-SCREEN OR SHEET\].
5.  Primary actions: \[PLACEMENT BY BREAKPOINT\].
6.  Typography: \[RESPONSIVE TYPE SCALING\].
7.  Images: \[ASPECT RATIO, CROP, AND LAZY LOADING\].

## 4. Navigation and page anatomy

### 4.1 App shell

-   **Top bar:** \[LOGO / SEARCH / USER MENU / ACTIONS\]
-   **Sidebar:** \[GROUPS / COLLAPSE / ACTIVE STATE\]
-   **Breadcrumbs:** \[WHEN SHOWN\]
-   **Page header:** \[TITLE / DESCRIPTION / ACTIONS\]
-   **Content region:** \[WIDTH / PADDING / BACKGROUND\]
-   **Footer:** \[WHEN SHOWN\]

### 4.2 Page patterns

  -------------------------------------------------------------------------
  Page type         Required regions  Key interaction     Empty/error state
  ----------------- ----------------- ------------------- -----------------
  Dashboard         \[HEADER,         \[FILTERS\]         \[FALLBACK\]
                    METRICS,                              
                    CONTENT\]                             

  List/search       \[SEARCH,         \[SORT/PAGINATE\]   \[NO RESULTS\]
                    FILTERS,                              
                    RESULTS\]                             

  Detail            \[HEADER, DATA,   \[EDIT/SHARE\]      \[NOT FOUND\]
                    ACTIONS\]                             

  Create/edit       \[FORM, HELP,     \[VALIDATE/SAVE\]   \[FAILURE\]
                    ACTIONS\]                             

  Settings          \[GROUPS,         \[SAVE/RESET\]      \[FAILURE\]
                    CONTROLS\]                            

  Auth              \[FORM, STATUS,   \[SIGN IN\]         \[ERROR\]
                    RECOVERY\]                            
  -------------------------------------------------------------------------

For every implemented route, document: - **Route:** `[PATH]` -
**Purpose:** \[USER GOAL\] - **Content hierarchy:** \[ORDER OF
REGIONS\] - **Primary CTA:** \[LABEL AND ACTION\] - **Secondary
actions:** \[LABELS AND ACTIONS\] - **Data dependencies:** \[WHAT UI
NEEDS; NO BACKEND DESIGN\] - **Loading / empty / error states:**
\[EXPECTED UI\] - **Mobile adaptation:** \[SPECIFIC CHANGES\]

## 5. Component contracts

Each shared component MUST specify: **Purpose → Anatomy → Props/variants
→ Dimensions → Visual states → Keyboard behavior → Responsive behavior →
Usage rules → Anti-patterns.**

### 5.1 Buttons

-   Variants: \[PRIMARY, SECONDARY, OUTLINE, GHOST, DESTRUCTIVE\].
-   Sizes: \[SM, MD, LG\] with \[EXACT HEIGHT/PADDING\].
-   States: default, hover, focus-visible, active, disabled, loading.
-   Primary action: \[RULE FOR MAXIMUM PROMINENCE\].
-   Icon-only: accessible name required.
-   Loading: show progress; prevent accidental double submission.
-   Navigation uses links; actions use buttons.

### 5.2 Inputs and forms

-   Label placement: \[ABOVE / OTHER\].
-   Helper and error text: \[LOCATION AND STYLE\].
-   Required indicator: \[CONVENTION\].
-   Validation: \[ON BLUR / SUBMIT / CONDITIONAL\].
-   Field types: text, textarea, select, checkbox, radio, date, file
    upload.
-   Form grouping: \[SECTIONS AND SPACING\].
-   Submit behavior: \[LOADING / SUCCESS / ERROR / RETRY\].
-   Preserve user input after recoverable errors.
-   Associate errors and descriptions with their controls.

### 5.3 Cards

-   Variants: \[DEFAULT / INTERACTIVE / METRIC / MEDIA\].
-   Anatomy: \[TITLE, CONTENT, ACTIONS, META\].
-   Padding: \[TOKEN\].
-   Radius/border/shadow: \[TOKENS\].
-   Clickability: \[CARD CLICK VS INNER CONTROLS\].
-   Empty state: \[PLACEHOLDER OR OMIT\].

### 5.4 Tables and lists

-   Header treatment: \[STYLE\].
-   Row height: \[DENSITY\].
-   Sort indicators: \[BEHAVIOR\].
-   Selection: \[CHECKBOX / BULK ACTIONS\].
-   Pagination: \[PAGE SIZE / CONTROLS\].
-   Loading: \[SKELETON OR PROGRESS\].
-   Empty: \[MESSAGE AND NEXT ACTION\].
-   Mobile: \[SCROLL OR RESPONSIVE ALTERNATIVE\].
-   Numeric columns: align consistently; label units.

### 5.5 Dialogs, menus, and feedback

-   Dialog sizes: \[SM / MD / LG\].
-   Opening focus: \[TARGET\].
-   Closing: Escape, explicit close, and \[BACKDROP POLICY\].
-   Restore focus to trigger on close.
-   Menus: \[KEYBOARD NAVIGATION AND DISMISSAL\].
-   Toasts: \[POSITION / DURATION / PERSISTENCE\].
-   Alerts: \[INLINE VS GLOBAL\].
-   Destructive confirmation: \[WHEN REQUIRED\].

### 5.6 Icons and imagery

-   Approved icon library: \[LIBRARY\].
-   Default stroke and size: \[VALUES\].
-   Do not mix unrelated icon families.
-   Meaningful images require alt text; decorative images use empty alt.
-   Images: \[ASPECT RATIOS / PLACEHOLDER / FALLBACK\].

## 6. Interaction and motion

-   **Hover feedback:** \[RULE\]
-   **Focus-visible:** \[RING STYLE\]
-   **Selected state:** \[NON-COLOR INDICATOR\]
-   **Transitions:** \[DURATION / EASING TOKENS\]
-   **Animation allowed for:** \[FUNCTIONAL PURPOSES\]
-   **Animation prohibited for:** \[DISTRACTING OR BLOCKING EFFECTS\]
-   **Reduced motion:** Honor `prefers-reduced-motion`.
-   **Optimistic updates:** \[WHEN ALLOWED; ROLLBACK UI\]
-   **Unsaved changes:** \[WARNING OR AUTOSAVE BEHAVIOR\]
-   **Undo:** \[WHICH ACTIONS\]
-   **Notifications:** \[WHAT TRIGGERS TOAST VS INLINE STATUS\]

## 7. Content and UI copy

-   **Voice:** \[CONCISE / FRIENDLY / PROFESSIONAL\].
-   **Headings:** \[CAPITALIZATION\].
-   **Button labels:** Use explicit verbs, e.g., "Save changes".
-   **Errors:** Say what failed and how to recover; avoid blame.
-   **Empty states:** Explain what is missing and offer a relevant
    action.
-   **Loading:** Avoid unexplained spinners on long operations.
-   **Dates/numbers:** \[LOCALE / TIMEZONE / UNITS / PRECISION\].
-   **Destructive actions:** Clearly state consequences.

## 8. Accessibility contract

-   [ ] Semantic HTML and logical heading order.
-   [ ] All controls keyboard operable.
-   [ ] Visible focus indicator.
-   [ ] Accessible labels and error associations.
-   [ ] Contrast verified for text and UI elements.
-   [ ] No color-only communication.
-   [ ] Touch targets and spacing checked.
-   [ ] Dialog focus management correct.
-   [ ] Screen-reader announcements for dynamic status where
    appropriate.
-   [ ] Zoom, reflow, and reduced motion tested.
-   [ ] No inaccessible custom widgets when a native element works.

## 9. Frontend architecture conventions

-   **Folder structure:** \[e.g., `src/app`, `src/components/ui`,
    `src/components/features`, `src/hooks`, `src/styles`\].
-   **Server/client component boundary:** \[IF APPLICABLE\].
-   **Reusable component criteria:** \[WHEN TO EXTRACT\].
-   **Component naming:** \[PASCALCASE ETC.\].
-   **File naming:** \[CONVENTION\].
-   **State management:** \[LOCAL / CONTEXT / LIBRARY\].
-   **Form handling:** \[LIBRARY\].
-   **Validation:** \[LIBRARY\].
-   **Fetching/caching:** \[FRONTEND CONVENTION\].
-   **Error boundaries:** \[PLACEMENT\].
-   **Styling conventions:** \[UTILITY ORDER / CSS MODULE RULES\].
-   **Testing:** \[UNIT / COMPONENT / E2E TOOLS\].
-   **Performance:** \[IMAGE OPTIMIZATION / CODE SPLITTING / LOADING
    STRATEGY\].
-   **Localization:** \[SUPPORTED LOCALES AND RTL REQUIREMENTS\].

## 10. AI agent implementation instructions

Before writing UI code: 1. Read this file, relevant route requirements,
and existing components. 2. Inspect the project's installed UI library
and token definitions. 3. Identify existing components to reuse. 4. Plan
desktop and mobile layouts and all relevant states. 5. Flag any missing
product/design decision instead of inventing it.

While implementing: 1. Build with semantic elements and accessible
interaction. 2. Use existing tokens; avoid arbitrary Tailwind values or
inline CSS without justification. 3. Keep changes scoped to the
requested screen/feature. 4. Preserve existing behavior and design
patterns. 5. Implement functional actions; do not add dead buttons or
fake links. 6. Support real content, long text, and empty datasets. 7.
Do not introduce dependencies without explicit justification.

Before finishing: 1. Run relevant typecheck, lint, and tests. 2. Inspect
responsive behavior at \[MOBILE\], \[TABLET\], and \[DESKTOP\] widths.
3. Check keyboard focus, loading, empty, error, and disabled states. 4.
Verify design tokens and shared component consistency. 5. Summarize
changed files, deviations, and any remaining issues.

## 11. Anti-patterns / prohibited shortcuts

-   No arbitrary gradients, glassmorphism, or excessive shadows unless
    explicitly approved.
-   No one-off fonts/colors/spacings where tokens exist.
-   No inaccessible clickable `div` elements.
-   No hover-only essential actions.
-   No placeholder content presented as real production data.
-   No hidden overflow that conceals primary controls.
-   No unnecessary new component library.
-   No unrelated redesigns.
-   **Project-specific prohibited patterns:** \[ADD\].

## 12. Visual QA / definition of done

  -----------------------------------------------------------------------
  Check                               Acceptance criterion
  ----------------------------------- -----------------------------------
  Design consistency                  Uses approved tokens and components

  Visual hierarchy                    Primary task and action are obvious

  Responsive                          Works at all supported widths

  Interaction                         Every control functions as intended

  State coverage                      Loading, empty, error, success,
                                      disabled as relevant

  Accessibility                       WCAG 2.2 AA checks completed

  Content                             Realistic lengths and edge cases
                                      handled

  Engineering                         Relevant checks pass

  Regression                          Existing flows remain functional
  -----------------------------------------------------------------------

### Per-page review record

-   **Route:** \[PATH\]
-   **Reference / screenshot:** \[LINK\]
-   **Viewports checked:** \[VALUES\]
-   **Issues found:** \[LIST\]
-   **Exceptions approved:** \[LIST\]
-   **Reviewer / date:** \[NAME / DATE\]

## 13. Change log

  Date       Change       Reason          Owner
  ---------- ------------ --------------- ----------
  \[DATE\]   \[CHANGE\]   \[RATIONALE\]   \[NAME\]

## 14. References

-   Google Labs DESIGN.md: https://github.com/google-labs-code/design.md
-   Google Labs specification:
    https://github.com/google-labs-code/design.md/blob/main/docs/spec.md
-   WCAG 2.2: https://www.w3.org/TR/WCAG22/
-   Project design file: \[FIGMA LINK\]
-   Project component library: \[URL/PATH\]
