# GovMonitor workspace design

The redesign uses the analytics preview at https://uupm.cc/demo/saas-analytics-dashboard as its structural reference, together with UI/UX Pro Max guidance from https://github.com/nextlevelbuilder/ui-ux-pro-max-skill (reviewed 16 November 2026).

The reference's dashboard uses a four-card KPI row above a wide trend chart and smaller summary panel. GovMonitor follows that hierarchy with government accomplishment and budget data. Its marketing sections and sample business figures are not part of this application. React guidance calls for semantic controls, controlled form fields, and managed dialog focus.

## Decisions

- Fixed white sidebar with task groups: Monitor, Plan & report, Agency, Support; concise labels and consistent SVG line icons.
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

`frontend/src/workspace.css` defines the shared visual layer after the existing component styles. `AppShell.tsx` defines the grouped navigation, account summary, and mobile menu. `AuthCard.tsx` supplies the shared sign-in/password-page layout. `ResultTiles.tsx` and `Sparkline.tsx` render the KPI row; `DashboardPage.tsx` defines the chart layout and visual summaries. `chartTheme.ts` supplies the shared chart palette.

## Validation and local review

Completed: production build, lint/formatting, 87 tests across 33 files, and browser checks of the running frontend against the existing local backend. The checks cover navigation, dialog focus, actual-data badges, missing/future history, zero budgets, and decimal rounding. The suite bounds jsdom startup concurrency to avoid lazy-page timeouts on Windows.

Browser verification includes desktop, tablet, and phone layouts; fixed desktop navigation; phone menu and horizontal overflow checks; chart/table toggling; and successful Excel report preparation. The development frontend runs on localhost:5173, with its local API proxy forwarding to the backend on port 8000. CSRF tokens are still required. Production Docker images still require rebuilding to serve the new frontend from port 8000.

Current screenshots are embedded in `USER_GUIDE.md` and `user-guide/USER_GUIDE.pdf` (edition 2.3). The app has a searchable 34-section guide at `/user-guide`, with PDF download and section printing. Operator commands and practice text files remain separate documents and are excluded from the shipped guide assets. Guide text is rendered as React nodes, with no injected HTML.

Screen descriptions, tooltips, status messages, and help use plain language for monitoring and finance. Scoring methods have readable display names; office-access and audit labels describe what users can see and what changed. Stored setting keys, audit filter values, permissions, and calculations are unchanged.

Production settings exclude the demo seed command. `initialize_workspace` creates a real agency and its first administrator, then suspends recognizable built-in training agencies and disables their demo accounts. It retains records and skips renamed agencies or agencies with other users. Existing administrator passwords remain unchanged when setup is repeated. No practice figures are loaded automatically.

Browser verification covers guide search and section navigation. The production build includes every guide download. Docker access was unavailable in the editing session, so rebuilding port 8000 and applying real-agency setup remain local operator steps in `RUN_AND_CLOSE.txt`.

From the project directory, run `docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build web worker` to rebuild and start the updated app using the existing local settings and data.
