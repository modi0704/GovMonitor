# Changelog

All notable changes. Versions follow semantic versioning: a new major version may need a manual
step on update (described here); minor and patch versions update with `update.sh` alone.

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
