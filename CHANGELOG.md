# Changelog

All notable changes. Versions follow semantic versioning: a new major version may need a manual
step on update (described here); minor and patch versions update with `update.sh` alone.

## Unreleased

### Fixed
- A backend test needed the built frontend and failed in CI.
- When the app cannot open its database, it now says why (for example "password authentication
  failed") and how to fix it, instead of only "database not reachable".

### Running on one PC
- **Testing mode without sign-in** (`LOGIN_DISABLED`, on by default in `run.sh`): the app opens
  straight away as the agency administrator (`LOGIN_AS` can name another account), with a notice
  at the top and no Sign out button. `run.sh` then starts only the database, the app and the worker,
  so the app is reachable from this PC alone (the HTTPS front door stays stopped), and loads the
  practice data when the database is empty. `./run.sh login on|off` switches the sign-in page back
  on or off. The sign-in code is unchanged; servers keep sign-in (the setting is off by default).
- `./run.sh start | stop | update | demo | setup | status | logs | fix-db` replaces the long Docker
  commands. It always uses the same settings, waits until the app answers, and `fix-db` repairs a
  saved database created with other passwords without losing data.
- **User Guide with Sample Data** (`docs/USER_GUIDE_WITH_SAMPLE_DATA.md`, PDF, and a download on
  the in-app User guide page): a practice center with two offices, every figure to type, and the
  results to expect after each step, checked against the app. Replaces `SAMPLE_INPUT.txt` and
  `INPUT_AND_METRICS.txt`.
- Over-all performance deck: the output-indicator panel compares what was reached with what was
  planned by that month (100% only in December), not with the whole year's target; long status
  words fit their box; the title bar no longer repeats the office name.
- `./run.sh reset-password [email]` (management command `reset_password`): lists the administrator
  accounts, or gives one a new temporary password — for installs without email.

### Easier to use
- **Step-by-step** start page for the monitoring administrator: six steps (offices, year, plans,
  monthly results, check & close, report) with a progress bar, what to collect from the offices
  before each step, and a checklist of every office. A guide bar on each related page shows the
  step and links back. "Mark as final" confirms a plan in one go.
- Plain-English menu and screens: Downloads, Office plans, Monthly results, Who has reported,
  Years, Offices, Reminders, Report look, Change history; "gap" for variance, "close" for lock.
  Rarely used settings are folded away. A word list on the Help page.
- A new, short user guide (edition 3.0, in the app and as a PDF) built around the six steps, with
  new screenshots; simpler practice and Windows start/update/close instructions.
- `tools/user_guide_pdf.sh` rebuilds the user guide PDF from `docs/USER_GUIDE.md`; the administrator
  guide, release checklist, security review and design notes follow the new flow. Duplicate and
  placeholder files removed from `docs/`.

### Reporting
- **Over-all performance for the year**: a PowerPoint deck modelled on the year-end presentation —
  over-all performance based on activities (PPAs) and on output indicators, panels for the offices
  beneath, each office's activities month by month, indicators, and rankings by activities and by
  output indicators.

## 1.0.0 — 2026-11-15

First release.

### Monitoring
- Organisation structure with named levels, any depth, office groups, paste import, moves.
- Fiscal years with twelve monthly periods and cutoffs; scoring profiles with presets
  (workbook compatible, capped with tolerance) and every rule adjustable; locked months keep the
  settings they were scored with.
- Plans entered in a spreadsheet-style editor, copied from last year or imported from Excel;
  validation, submission, approval, revisions with versions and comparison.
- Monthly reports with live results, delay reasons, supporting files (MOVs), optional amounts
  spent; submission board; return with a note; lock and unlock with a reason.
- Results from one scoring engine: cumulative plan and accomplishment, variance and status, funds,
  indicators, owner and implementing views, budget-weighted roll-up, sibling and group rankings —
  reproducing the MOST December 2023 workbook figures exactly.
- Dashboards, activity history, rankings with change since last month.

### Reporting
- Excel export in the agency workbook layout (live formulas, SUMMARY sheet), checked by
  recalculation; plan import from the same layout.
- PowerPoint deck with native charts, rankings and indicator tables; report template with colours
  and logo.
- Alerts: reminders before the cutoff, late reports, missing accomplishments, delays after locking,
  returned reports, locked months, plans waiting for approval; in-app bell and optional daily email.

### Platform
- Multi-agency service with row-level security and same-agency foreign keys; single-agency office
  installs with a signed licence.
- Audit log of every change; two-step sign-in; rate limits; strict content security policy.
- Phone layouts for following results and attaching photos; in-app help per role.
- Docker images, single-machine and cloud compose files, Caddy HTTPS, backup and restore, offline
  install bundle with update and automatic rollback.
