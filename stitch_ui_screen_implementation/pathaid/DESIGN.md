---
name: PathAid
colors:
  surface: '#FFFFFF'
  surface-dim: '#c8e0d0'
  surface-bright: '#e8ffef'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#e2f9e9'
  surface-container: '#dcf4e3'
  surface-container-high: '#d6eede'
  surface-container-highest: '#d1e8d8'
  on-surface: '#0b1f16'
  on-surface-variant: '#404943'
  inverse-surface: '#21352a'
  inverse-on-surface: '#dff7e6'
  outline: '#707973'
  outline-variant: '#c0c9c1'
  surface-tint: '#2e694e'
  primary: '#084c33'
  on-primary: '#ffffff'
  primary-container: '#286449'
  on-primary-container: '#a0debc'
  inverse-primary: '#96d4b2'
  secondary: '#58605b'
  on-secondary: '#ffffff'
  secondary-container: '#dae2db'
  on-secondary-container: '#5c645f'
  tertiary: '#33463b'
  on-tertiary: '#ffffff'
  tertiary-container: '#4a5e52'
  on-tertiary-container: '#c0d6c7'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b1f0cd'
  primary-fixed-dim: '#96d4b2'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#105137'
  secondary-fixed: '#dce4de'
  secondary-fixed-dim: '#c0c8c2'
  on-secondary-fixed: '#161d19'
  on-secondary-fixed-variant: '#414944'
  tertiary-fixed: '#d2e8d9'
  tertiary-fixed-dim: '#b6ccbd'
  on-tertiary-fixed: '#0c1f16'
  on-tertiary-fixed-variant: '#384b40'
  background: '#FAFAF7'
  on-background: '#0b1f16'
  surface-variant: '#d1e8d8'
  foreground: '#24382D'
  surface-muted: '#F0F4EF'
  primary-foreground: '#FFFFFF'
  muted-foreground: '#52665A'
  border: '#D8E2D9'
  ring: '#286449'
  success: '#246B4C'
  warning: '#895400'
  destructive: '#A92D32'
typography:
  display:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 54px
    letterSpacing: -0.035em
  display-mobile:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 42px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.025em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: '0'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: '0'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: '0'
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-desktop: 2rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system embodies a calm, approachable, and encouraging utility designed to dismantle the anxiety surrounding student financing and scholarship discovery. Guided by a "Quiet Utility" philosophy inspired by high-focus productivity workspaces, the interface eliminates gamification, artificial urgency triggers, and decorative clutter. Instead, it prioritizes clarity, structural honesty, and supportive guidance.

### Design Movement: Quiet Utility & Utilitarian Minimalism
- **Atmosphere:** Low-stress, reliable, and deeply functional. Surfaces are quiet, relying on warm neutral canvases paired with deep botanical greens rather than aggressive primary highlights.
- **Visual Values:** 1px hairline structure over layered ambient blur; crisp hierarchy over decorative depth; unambiguous microcopy over hype or artificial match metrics.
- **Truth in UI:** Eligibility indicators distinguish clearly between matching user profile filters and confirmed organizational qualification. Critical deadlines are communicated with steady visual priority, not pulsating countdown timers.

## Colors

The palette is rooted in botanical forest and sage tones, anchored by an off-white warm canvas (`#FAFAF7`) and high-legibility dark slate typography (`#24382D`).

### Application Hierarchy
- **Canvas & Surfaces:** Primary application canvas renders with `--background` (`#FAFAF7`). Distinct cards, modular panels, and modal containers use `--surface` (`#FFFFFF`). Recessed wells, table striping, and inactive input backdrops use `--surface-muted` (`#F0F4EF`).
- **Interactive & Action:** `--primary` (`#286449`) is reserved for primary CTAs, active pagination steps, and high-impact control highlights. `--secondary` (`#E8F0E9`) provides subtle backdrops for filter tags, status pills, and secondary interactive actions.
- **Borders & Dividers:** Component bounds and data tables consistently resolve to `--border` (`#D8E2D9`).
- **Semantic Feedback:**
  - **Success (`#246B4C`):** Used for completed application steps and submitted materials.
  - **Warning (`#895400`):** Used for upcoming deadlines (e.g., within 7 days) and missing profile attributes.
  - **Destructive (`#A92D32`):** Used for closed programs, submission errors, and destructive account actions.

## Typography

Inter serves as the unified family across all typographic tiers, providing a balance of structural neutrality and high technical legibility.

### Numerical Treatment & Data Legibility
- Enable OpenType tabular figures (`font-variant-numeric: tabular-nums;` or `font-feature-settings: "tnum"`) across all dollar values, application deadline countdowns, progress ratios, and GPA requirements to prevent visual jitter when updating or listing tabular data.

### Prose & Hierarchy Constraints
- Limit long-form description blocks and scholarship criteria explanations to `max-width: 68ch`.
- Headings maintain restrained line-heights and negative tracking to preserve structural density.
- Table headers use `label-sm` in all-caps or title case paired with `--muted-foreground`.

## Layout & Spacing

Layout geometry follows a strict 4px base rhythm, scaling upward through standardized 8px intervals.

### Grid & Canvas Structure
- **Mobile (< 640px):** Single-column stacked layout with `1rem` (16px) margins and gutters. Controls default to full-width or natural bottom-sheet triggers.
- **Tablet (640px – 1023px):** Fluid multi-column flow with `1.5rem` (24px) gutters and canvas padding.
- **Desktop (1024px+):** Fixed 240px lateral navigation rail paired with a fluid main workspace. Core workspace content is capped at `1200px` to maintain comfortable eye-tracking distance.

### Internal Spacing Rhythm
- **Card Padding:** `1.25rem` (20px) on desktop, reduced to `1rem` (16px) on mobile viewports.
- **Form Group Spacing:** Elements within a field stack separated by `space-xs` (4px) to `space-sm` (8px). Adjacent vertical input fields spaced by `space-md` (16px). Major form sections separated by `space-xl` (32px).

## Elevation & Depth

Visual hierarchy is communicated through subtle boundary lines and tonal separation rather than heavy drop shadows.

### Border-Dominant Hierarchy
- Base containers (cards, summary statistics, search filters) rest flush with the canvas using a `1px solid var(--border)` outline and zero box-shadow.
- When an interactive card is hovered, the border shifts smoothly to an emphasized state without translation or elevation lift.

### Floating Planes & Overlays
- **Restrained Card Depth (Optional Floating Cards):** `0 1px 2px rgba(16, 36, 22, 0.05)`
- **Flyouts & Dropdowns:** `0 12px 32px rgba(16, 36, 22, 0.12)` accompanied by `1px solid var(--border)` to keep edge contrast sharp.
- **Modals & Dialogs:** Elevated through a full viewport backdrop overlay (`rgba(36, 56, 45, 0.40)`) with blurred refraction (`backdrop-filter: blur(4px)`).

## Shapes

The design system maintains a clean hierarchy of roundedness: structural surfaces sit at an accessible 12px corner radius, while interactive controls settle at 8px.

### Corner Radius Mapping
- **Control Radius (`8px` / `0.5rem`):** Applied to buttons, text inputs, dropdown triggers, and select controls.
- **Container Radius (`12px` / `0.75rem`):** Standard for cards, panels, filters, and list containers.
- **Overlay Radius (`16px` / `1rem`):** Used on modals, dialogs, and slide-in sheets.
- **Full Pill (`9999px`):** Applied exclusively to status badges, category tags, removable filter chips, and user avatars.

## Components

### Buttons
- **Primary:** Solid `--primary` (`#286449`) fill with `--primary-foreground` (`#FFFFFF`). Height is 44px (md) or 36px (sm), with 8px radius.
- **Secondary:** `--secondary` (`#E8F0E9`) fill with `--foreground` (`#24382D`). 1px border with `--border`.
- **Ghost:** Transparent background with `--foreground` text. Surface tints to `--surface-muted` on hover.
- **Focus State:** `2px solid var(--ring)` with a `2px` offset (`focus-visible`).

### Input Fields & Controls
- **Height & Bounds:** 44px uniform height, 8px border radius, `1px solid var(--border)` outline on `--surface` background.
- **Active / Focused:** Replaces default border with a 1px `--primary` stroke and matches the focus ring token.
- **Helper & Validation Text:** Displayed at `14px` (`body-md`) with persistent layout space to prevent cumulative layout shift.

### Cards & Scholarship Tiles
- **Surface:** `--surface` fill bounded by `1px solid var(--border)`. 12px radius.
- **Header Structure:** Title displayed with `headline-sm`, reward amount highlighted with tabular numbers (`tnum`) in `--primary`, and metadata chips aligned cleanly in a row.
- **Hover Behavior:** Border transitions from `--border` to `--tertiary` over 120ms without geometric scale adjustments.

### Chips & Filter Tags
- **Default State:** Full pill (`rounded-full`), height of 28px–32px, filled with `--surface-muted` and bounded by `--border`.
- **Active State:** `--secondary` fill with `--primary` text and a subtle 1px `--primary` border stroke.
- **Dismissible Variant:** Houses a 14px Lucide `X` icon aligned right with minimum 44px interactive tap area padding.

### Checkboxes & Radio Controls
- **Geometry:** 18px × 18px dimensions; checkboxes utilize 4px border radius, radios use circular form.
- **State:** Unchecked state uses `1.5px solid var(--border)` on `--surface`. Checked state uses `--primary` fill with white indicator marks.

### Status Indicators
- **Requirement Flags:** Always pair an icon with textual copy (never rely on color alone).
- **Match Labels:** Clearly separate calculated filter overlap (e.g., "Matches 5/5 criteria") from formal application acceptance indicators.