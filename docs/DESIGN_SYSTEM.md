# GovMonitor workspace design

The redesign uses the analytics preview at https://uupm.cc/demo/saas-analytics-dashboard as its structural reference, together with UI/UX Pro Max guidance from https://github.com/nextlevelbuilder/ui-ux-pro-max-skill (reviewed 16 November 2026).

The reference's dashboard uses a four-card KPI row above a wide trend chart and smaller summary panel. GovMonitor follows that hierarchy with government accomplishment and budget data. Its marketing sections and sample business figures are not part of this application. React guidance calls for semantic controls, controlled form fields, and managed dialog focus.

## Decisions

- Fixed white sidebar with task groups in plain words: Start here (Step-by-step), See results, Enter data, Settings (folded), Help; consistent SVG line icons.
- The agency administrator's start page is Step-by-step: a six-step progress bar, what to collect from the offices before each step, and a per-office checklist. Pages that belong to a step show a green guide bar ("Step N of 6") with Back to the steps and Next links.
- Plain-English wording: gap (not variance), close (not lock), Years, Offices, Downloads; a word list on the Help page.
- Existing role restrictions, destinations, reporting rules, and data remain in force.
- White work surfaces, neutral light background, crisp gray borders, subtle shadows, 20-24px card spacing, and green accents limited to primary actions, active navigation, positive indicators, and chart highlights.
- Four KPI cards show monthly accomplishment, cumulative accomplishment, variance, and funds used. Percentage-point comparison badges distinguish plan comparison from previous-month comparison.
- Cumulative and variance sparklines use actual recorded history only through the selected month. Missing observations break the line and are not converted to zero. Previous-month badges disappear when that month's data is missing.
- The primary chart uses a green actual line with a subtle chart-only fill and a dashed gray plan line. A budget donut uses real used/remaining amounts and suppresses a zero-budget pie.
- Quarter summaries and office/indicator tables use restrained progress bars. Quarter details remain available in an expandable table.
- Offline system typography: Segoe UI and system sans-serif; no remote font dependency.
- Visible keyboard focus; decorative SVG icons accompany text labels.
- Standard controls target 44px height; desktop table actions use 38px, enlarged on small screens.
- Phone navigation expands in the page; editing restrictions on phones remain unchanged.
- Modal keyboard focus stays inside the dialog and returns to the previous control on close.
- Reduced-motion preferences stop transitions and loading animation.

## Implementation

`frontend/src/workspace.css` defines the shared visual layer after the existing component styles. `AppShell.tsx` and `layout/nav.ts` define the grouped navigation, account summary, and mobile menu; `lib/steps.ts`, `components/StepProgress.tsx`, `layout/GuideBar.tsx` and `pages/guide/GuidedStepsPage.tsx` the guided steps. `AuthCard.tsx` supplies the shared sign-in/password-page layout. `ResultTiles.tsx` and `Sparkline.tsx` render the KPI row; `DashboardPage.tsx` defines the chart layout and visual summaries. `chartTheme.ts` supplies the shared chart palette.

## Validation

`make check` (lint, formatting, backend and frontend tests, production build) and `make smoke`
(browser tests of the user flows and accessibility checks with axe, desktop and phone) cover the
workspace, including the guided steps, the guide bar, the folded Settings group and the export
dialog. The CI `image` job also opens every page of an offline install in a browser and downloads
each export.
