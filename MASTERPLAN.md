# MASTERPLAN — Performance Monitoring Web Application

> **This file is the single source of truth for the build.** It is written so that any AI coding
> agent (or human developer) can open it cold, find where work stopped, and continue. It does not
> depend on any chat history. If something in the code disagrees with this file, either fix the
> code or record the change in section 14 (Decision log) — never leave the two out of step.

---

## 0. STATUS — read this first, update it last

```
CURRENT PHASE      : 8
LAST COMPLETED TASK: P8.5
NEXT TASK          : P8.6
BLOCKERS / NOTES   : Reference files in reference/ (git-ignored). See the P14.1 note on cross-agency foreign keys
LAST UPDATED       : 2026-11-15 by Claude Code (build agent)
```

### 0.1 Resume protocol (mandatory for every session)

1. Read sections 0, 1, 2 and 3 of this file in full. Skim the rest.
2. Read the STATUS block above. Open the phase named in `CURRENT PHASE`.
3. Run that phase's **Verify start state** commands. If they fail, repair the state before doing
   anything new. If you cannot tell what state the repo is in, run `make check` and `git status`,
   then `git log --oneline -15`.
4. Find the first unchecked task `[ ]` in that phase. That is your next task, even if STATUS says
   otherwise (the checkboxes win over the STATUS block if they disagree; then fix STATUS).
5. Do **one task at a time**. After each task:
   - run the task's check (and `make check` if code changed);
   - change `[ ]` to `[x]` for that task in this file;
   - update the STATUS block;
   - commit with the message `P<phase>.<task>: <short description>` (this file is part of the commit).
6. A task that is half done when a session ends stays `[ ]`. Add one line under the task starting
   with `> IN PROGRESS:` saying exactly what exists and what is missing. Remove the line when done.
7. When every task and every **Phase exit check** of a phase passes, tick the phase line in
   section 4, set `CURRENT PHASE` to the next phase, and append one line to section 15 (Progress log).
8. Never tick a box for work that is not committed and passing. Never delete a task; if a task
   turns out to be wrong, strike it through with `~~text~~`, add `(superseded — see D-xx)` and log
   the reason in section 14.

### 0.2 Rules that apply to every phase

- **No MOST-specific code.** Nothing in `backend/` or `frontend/` may contain the names of MOST
  offices, activities or indicators. MOST data lives only in `backend/fixtures/` and
  `backend/seed/` as sample data and test vectors.
- **Every tenant table has `agency_id`** and a row-level-security policy (section 6.1). A new table
  without both fails the test in P1.9.
- **All scores come from `backend/apps/scoring/`** (section 7). No other module, template, export
  or frontend file may re-implement a scoring formula.
- **Every state-changing request writes an audit row** (section 6.5) once Phase 3 is done.
- **No runtime internet dependency.** No CDN links, no hosted fonts, no external APIs. Everything
  is bundled.
- **Tests first for business rules.** Sections 7 and 8 contain test vectors; turn them into tests
  before writing the implementation.
- **Do not touch `reference/`.** It holds the customer's original workbooks, read-only.
- **Phases are restartable.** Migrations, seed commands and scripts must be idempotent (safe to
  run twice).

---

## 1. What is being built

A commercial, general-purpose web application that lets a government agency monitor and evaluate
the performance of its offices (services, divisions, field units) against their annual work and
financial plans. It replaces a manual Excel workflow. It is sold to many agencies; each agency
configures its own structure, plans, indicators and scoring rules.

### 1.1 Origin

The business logic comes from a set of Excel workbooks and one PowerPoint deck used by one ministry
(BARMM Ministry of Science and Technology, "MOST"). MOST has seven provincial centers and seven
divisions. **MOST is the first configuration and the test case, not the design.** The analysis of
those files produced the method in section 7 and the test vectors in section 8.

### 1.2 Feature list (all are in scope for version 1)

| # | Feature | Phase |
|---|---|---|
| F1 | Multi-agency data isolation and security | 1 |
| F2 | Customisable agency and office structure, any depth | 2 |
| F3 | Multiple users per office with two access levels: Admin, Read-Only | 1, 2 |
| F4 | User activity and action audit logs | 3 |
| F5 | Analytics dashboard with performance ranking | 8 |
| F6 | Exact-structure Excel export (standard layout, section 9) | 9 |
| F7 | PowerPoint report export (section 10) | 10 |
| F8 | Limited phone access | 12 |
| F9 | User-friendly UI and UX (spreadsheet-style entry grid) | 5, 6, 12 |
| F10 | Monthly cutoff and report locking | 7 |
| F11 | Supporting attachment uploads (MOVs = means of verification) | 6 |
| F12 | Deadline and delay alerts | 11 |

### 1.3 Out of scope for version 1

Offline data entry; SMS alerts; single sign-on; any cross-agency or oversight view; native mobile
apps; a custom report designer; importing arbitrary legacy Excel layouts; virus scanning of
uploads (leave a hook, section 6.6).

---

## 2. Decisions (approved by the product owner)

Each decision is final unless section 14 records a change. `ASSUMED` marks items the owner did not
answer explicitly; build as written and keep them easy to change.

| ID | Decision |
|---|---|
| D1 | **Roles.** Two access levels inside an agency: `admin` and `read_only`. Each is assigned at an office and covers that office and all offices beneath it. An `admin` at the agency's root office is the *agency administrator*: additionally manages structure, users, fiscal years, scoring settings, cutoff calendar, plan approval, locking and unlocking. The vendor holds separate *platform owner* accounts outside any agency. |
| D2 | **Review.** One light step: the agency administrator can return a submission for correction before locking. No multi-level approval chain. |
| D3 | **Plan revisions.** Allowed mid-year as a new plan version approved by the agency administrator. Old versions are kept. Locked months keep the results they were locked with. |
| D4 | **Cutoff.** The agency sets one cutoff day per month. The agency administrator locks a month manually; automatic locking at cutoff is an agency option (default off). Unlocking needs a reason and is logged. |
| D5 | **Default scoring.** A preset named `workbook_compatible` reproduces the Excel method exactly (cost-share weights, no ceiling, zero tolerance, budget-weighted roll-up). Every rule is switchable per agency per fiscal year. Acceptance = the December 2023 figures in section 8. |
| D6 | **Report once, roll up twice.** Every activity has an owning office (the plan's office) and an implementing office. Scores can be viewed along either dimension. |
| D7 | **Spending.** Optional actual-amount field per activity per month. "Funds used" shows real amounts where entered, otherwise the estimate (budget × cumulative accomplishment), always labelled as an estimate. |
| D8 | **Ranking.** Offices are ranked against siblings (same parent) and within office groups, by cumulative accomplishment for the selected month. Tied offices share a rank (1, 1, 3). |
| D9 | **Periods.** Monthly periods. Fiscal-year start month is configurable per agency. Quarterly and annual views are derived. Multi-year projects are re-entered in each year's plan. |
| D10 | **Excel export.** One standard layout (section 9) taken from the 2024 workbook's division entry sheets: one sheet per office, live formulas, plus a summary sheet. The workbook's calculation and dashboard sheets are not reproduced. All agencies get this layout; custom layouts are a paid template (the code must allow adding templates, nothing more). |
| D11 | **PowerPoint export.** Same sequence as the source deck: one dashboard slide per office and ranking slides, native editable charts, agency logo (section 10). |
| D12 | **Phone.** Fewer features on small screens, no device restriction: view dashboards, rankings and alerts; upload MOV photos. No plan setup and no grid entry. |
| D13 | **Deployment.** `ASSUMED` — not decided. The build must run unchanged as (a) a single-agency office-network install and (b) a multi-agency cloud service. Field-office connectivity is unknown: keep pages light, no offline mode. Sizing ceiling for version 1 tests: 50 agencies; per agency 500 offices, 1,000 users, 5,000 activities per fiscal year. |
| D14 | **Stack.** `ASSUMED` (owner accepted the recommendation; maintainers not yet named): Python + Django, PostgreSQL, React + TypeScript. See section 5. |
| D15 | **MOVs.** Optional by default; an agency setting can require at least one per reported accomplishment. Allowed: PDF, JPG, PNG, DOCX, XLSX, PPTX. Maximum 25 MB per file. |
| D16 | **Alert channels.** In-app and email. Email is off when no SMTP server is configured. |
| D17 | **Excel import.** Plans can be imported from a standard template that the system itself generates (the section 9 layout with empty data). |
| D18 | **Isolation and sign-in.** `ASSUMED` reading of the owner's "No": no cross-agency view of any kind; isolation is strict. Sign-in by email and password with password rules and optional TOTP two-factor codes. If the owner meant the opposite (an oversight view is wanted), add it as a new phase after Phase 14; the schema needs only an `agency_group` table and a read-only role, nothing else changes. |

---

## 3. Glossary

| Term | Meaning |
|---|---|
| Agency | One customer organisation (tenant). All data belongs to exactly one agency. |
| Office | A node in an agency's tree: the agency itself (root), a service, division, field unit, etc. |
| Office group | A named set of offices compared together (e.g. "Mainland centers"). |
| Fiscal year | Twelve consecutive monthly periods. |
| Plan | One office's work and financial plan for one fiscal year (Philippine term: WFP). Versioned. |
| Outline row | A heading line in a plan: outcome, outcome indicator, output, output indicator, program, project. |
| Activity | A scoreable plan line with an annual target, a cost and a monthly schedule. |
| Indicator | A performance indicator with monthly targets and actuals, scored separately from activities. |
| Period | One month of a fiscal year. Status `open` or `locked`. |
| Submission | One office's monthly report for one period. |
| MOV | Means of verification: a file supporting a reported number. |
| Periodic / cumulative | For one month only / from the first month through the selected month. |
| Variance | Cumulative actual % minus cumulative plan %. |
| Owner view / implementing view | Scores grouped by the office that owns the plan / by the office that carries out the activity. |

---

## 4. Phase overview

Tick a phase only when all its tasks and exit checks pass.

- [x] **Phase 0** — Repository, tooling, containers, pinned versions
- [x] **Phase 1** — Agencies, sign-in, roles, row-level security
- [x] **Phase 2** — Office structure and user management
- [x] **Phase 3** — Audit log
- [x] **Phase 4** — Scoring engine (pure module, test vectors)
- [x] **Phase 5** — Fiscal years, scoring profiles, plans, activities, indicators
- [x] **Phase 6** — Monthly reporting and MOV uploads
- [x] **Phase 7** — Cutoff, locking, frozen results
- [ ] **Phase 8** — Dashboards and ranking
- [ ] **Phase 9** — Excel export and plan import
- [ ] **Phase 10** — PowerPoint export
- [ ] **Phase 11** — Alerts and notifications
- [ ] **Phase 12** — Phone layouts and UX polish
- [ ] **Phase 13** — Deployment packaging (office install and cloud)
- [ ] **Phase 14** — Hardening, performance, documentation, release

Dependency order is linear (each phase needs the ones before it), except that Phase 4 depends only
on Phase 0 and may be done at any point before Phase 5.

---

## 5. Architecture

### 5.1 Shape

A **modular monolith**: one Django project, one React single-page app built to static files and
served by the same Django process, one PostgreSQL database, one background worker process (the
same code image started with a different command). No microservices, no message broker, no Redis.

```
Browser (desktop / phone)
        │  HTTPS, same origin, session cookie + CSRF
        ▼
  web container ── Django + DRF API (/api/v1/...) + built React app (/)
        │
        ├── PostgreSQL  (data, row-level security, job queue table)
        ├── file storage (local directory OR S3-compatible bucket)
        └── SMTP server (optional)
  worker container ── same image: `manage.py run_worker` (exports, imports, alert scans)
```

### 5.2 Stack and versions

Versions marked *verified* were checked against the vendor's site on 2026-11-15. Everything else
must be checked in task P0.2 and the exact versions written into this table.

| Layer | Choice | Version to pin | Notes |
|---|---|---|---|
| Language | Python | 3.13.18 (image `python:3.13-slim`) | Supported by Django 5.2. |
| Backend framework | Django | 5.2.19 (5.2 LTS, *verified*: extended support to April 2028) | Do not use 6.0/6.1 (short support). Plan an upgrade to 6.2 LTS after its release (expected April 2027). |
| API | Django REST Framework | 3.18.3 | JSON only. |
| DB driver | psycopg (binary) | 3.3.9 | LGPL-3.0 — licence exception D20. |
| Database | PostgreSQL | 18.7 in the compose image (`postgres:18`); CI and dev tested on 16 (the minimum) | Minimum supported by the app: 16. Do not adopt 19 until Django 5.2 lists it. |
| Frontend | React + TypeScript + Vite | React 19.3.1, react-router-dom 7.18.5, TypeScript 6.0.3, Vite 8.3.8, Node 22 | TypeScript 7 not used: typescript-eslint 8.72 supports <6.1 (D21). Built to `frontend/dist`, served by WhiteNoise. |
| Data grid | TanStack Table | 9.3.1 (MIT) | Headless; the grid UI is our own component. |
| Charts (web) | Apache ECharts | 6.1.0 (Apache-2.0) | Bundled, no CDN. |
| Excel writing | XlsxWriter | 3.3.1 | Writes formulas and formats. |
| Excel reading | openpyxl | 3.1.5 | Used by plan import and fixture extraction. |
| PowerPoint | python-pptx | 1.0.2 | Native charts. |
| Two-factor | pyotp (TOTP) + qrcode (SVG) | 2.11.2 / 8.2 | Replaces django-otp (Unlicense, not on the allow-list) — D19. Optional per user. |
| File storage | Django storage API; `django-storages[s3]` + boto3 | 1.14.6 / 1.44.3 | Selected by environment variable. |
| Licence signatures | cryptography | 50.0.2 | Ed25519 (Phase 13). |
| App server | Gunicorn + WhiteNoise | 27.0.1 / 6.12.0 | |
| Reverse proxy / TLS | Caddy | 2.11.9 (image `caddy:2`) | Optional container. |
| Packaging | Docker + Docker Compose | — | Same images for both deployment modes. |
| Tests | pytest + pytest-django + pytest-cov; Vitest + jsdom + Testing Library; Playwright (smoke only) | 9.2.0 / 4.14.0 / 7.1.0; 5.1.0 / 31.0.1 / 16.3.3; 1.63.0 | Property tests use seeded random generators (no Hypothesis — MPL-2.0, D22). |
| Lint/format | Ruff; ESLint + typescript-eslint + Prettier | 0.17.5; 10.15.0 / 8.72.2 / 3.10.1 | |

**Licence rule:** every runtime dependency must be MIT, BSD, Apache-2.0, PSF, ISC or PostgreSQL
licensed. P0.2 records each licence in `docs/THIRD_PARTY.md`. No GPL/AGPL and no "free for
non-commercial use" packages, because this product is sold.

**Background jobs:** do not add Celery or a task framework. Implement the small `job` table and
worker loop described in section 6.7.

### 5.3 Repository layout

```
MASTERPLAN.md            this file
README.md                how to run locally
Makefile                 up, down, migrate, test, check, seed-demo, build
reference/               original workbooks and deck (git-ignored, read-only)
tools/                   one-off scripts (fixture extraction)
deploy/                  Dockerfile, docker-compose.yml, docker-compose.cloud.yml, Caddyfile,
                         backup.sh, restore.sh, make-offline-bundle.sh
docs/                    THIRD_PARTY.md, ADMIN_GUIDE.md, USER_GUIDE.md, SECURITY.md, API.md
backend/
  config/                settings (base, dev, prod), urls, wsgi
  apps/
    tenancy/             agency, platform admin, support grant, RLS middleware
    accounts/            user, sign-in, 2FA, password rules, role assignment, permissions
    structure/           org level, office, office group
    audit/               audit log
    scoring/             PURE scoring engine (no ORM imports inside engine.py)
    planning/            fiscal year, scoring profile, plan, activity, indicator, targets
    reporting/           period, submission, actuals, attachments
    results/             live computation service, period_result snapshots, ranking
    alerts/              alert rule, notification, scans
    exports/             xlsx writer, pptx writer, plan import, templates
    jobs/                job table, worker command
  fixtures/              test vectors (JSON) — sample data only
  seed/                  demo agency seed command
frontend/
  src/                   app, routes, api client, components, pages
```

### 5.4 Configuration (environment variables)

| Variable | Values | Purpose |
|---|---|---|
| `DEPLOYMENT_MODE` | `single` / `multi` | `single`: exactly one agency; agency creation UI hidden. `multi`: platform owner can create agencies. |
| `DATABASE_URL` | URL | App connection (role `app_user`, subject to RLS). |
| `DATABASE_ADMIN_URL` | URL | Migrations and platform-owner operations (role `app_owner`). |
| `FILE_STORAGE` | `local` / `s3` | Where MOVs, logos and export files are kept. |
| `FILE_ROOT` | path | For `local`. |
| `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | | For `s3` (any S3-compatible service). |
| `EMAIL_URL` | SMTP URL or empty | Empty = email disabled; in-app notifications still work. |
| `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | | Standard Django. |
| `SESSION_IDLE_MINUTES` | default 60 | Idle sign-out. |
| `MAX_UPLOAD_MB` | default 25 | Upload limit. |
| `LICENCE_FILE` | path or empty | Office installs only (Phase 13). |

---

## 6. Data model and cross-cutting rules

Conventions: primary keys are UUID unless stated; timestamps are `timestamptz` in UTC; money is
`numeric(18,2)`; quantities are `numeric(18,4)`; ratios are `numeric(14,10)`. Every table below
except `platform_admin` has `agency_id uuid not null` referencing `agency` (omitted from the field
lists for brevity; `audit_log` and `export_template` allow null as stated in their entries) and an
index beginning with `agency_id`.

### 6.1 Isolation (F1)

- PostgreSQL row-level security is **enabled and forced** on every tenant table with the policy
  `USING (agency_id = current_setting('app.agency_id', true)::uuid) WITH CHECK (same)`.
  For `agency` itself the policy compares `id`.
- The web and worker processes connect as `app_user`, which does **not** own the tables and has
  no `BYPASSRLS`. Migrations and platform-owner actions use `app_owner`.
- `ATOMIC_REQUESTS = True`. A middleware runs `SET LOCAL app.agency_id = '<id>'` at the start of
  every authenticated request, taken from the signed-in user's agency. The worker sets it per job
  from `job.agency_id`.
- Sign-in looks the user up by email through a `SECURITY DEFINER` function that returns only the
  id, agency id and password hash for that one email.
- Files are stored under `<agency_id>/...` and are served only through an authorised endpoint
  that re-checks permission; never expose storage URLs directly.
- A request with no agency set sees zero rows. Tests must prove this (P1.9).

### 6.2 Tables — tenancy and access

- **agency**: `name`, `code` (unique), `logo_key`, `fiscal_year_start_month` (1–12, default 1),
  `timezone` (default `Asia/Manila`), `status` (`active`/`suspended`), `settings` (jsonb),
  `created_at`.
- **user**: `email` (globally unique, lower-cased), `full_name`, `password` (Django hash),
  `totp_secret` (nullable), `is_active`, `must_change_password`, `failed_attempts`,
  `locked_until`, `last_login_at`, `created_at`.
- **platform_admin** (no `agency_id`, no RLS; reachable only through `app_owner`): `email`,
  `full_name`, `password`, `totp_secret`, `is_active`.
- **support_grant**: `platform_admin_id`, `granted_by` (user), `expires_at`, `reason`. A platform
  admin may read an agency's data only while an unexpired grant exists. Creation is audited.
- **role_assignment**: `user_id`, `office_id`, `level` (`admin`/`read_only`), `created_by`,
  `created_at`. Unique on (`user_id`, `office_id`).

### 6.3 Tables — structure

- **org_level**: `depth` (0 = root), `name` (e.g. "Ministry", "Service", "Division").
  Unique on (`agency_id`, `depth`).
- **office**: `parent_id` (null only for the single root), `level_id`, `name`, `code`
  (unique per agency), `sort_order`, `is_active`, `path` (text, materialised path of ancestor ids
  ending with own id, e.g. `/<root>/<a>/<b>/`; indexed with `text_pattern_ops`).
  Rules: exactly one root per agency; no cycles; an office with plans or submissions cannot be
  deleted, only deactivated; moving an office rewrites `path` for its subtree in one transaction.
- **office_group**: `name`, `description`, `sort_order`.
- **office_group_member**: `group_id`, `office_id`. Unique on both.

### 6.4 Tables — planning, reporting, results

- **fiscal_year**: `label` (unique per agency), `start_date`, `end_date`, `status`
  (`draft`/`open`/`closed`). Creating one creates its 12 `reporting_period` rows and one
  `scoring_profile`.
- **scoring_profile** (one per fiscal year): `preset` (text), `weighting`
  (`cost_share`/`equal`/`manual`), `cap_at_100` (bool), `on_time_tolerance` (ratio, default 0),
  `label_ahead`, `label_on_time`, `label_delayed` (defaults `ADVANCED`, `ON-TIME`, `DELAYED`),
  `rollup` (`budget_weighted`/`simple_average`), `indicator_weighting` (`equal`/`manual`),
  `indicator_rollup` (`all_indicators`/`office_scores`), `ranking_metric`
  (`cumulative_actual`/`variance`/`actual_over_plan`), `mov_required` (bool), `auto_lock` (bool),
  `cutoff_day` (1–28, day of the following month), `version` (int, +1 on every change).
- **plan**: `office_id`, `fiscal_year_id`, `version` (int), `status`
  (`draft`/`submitted`/`approved`/`superseded`), `approved_budget` (nullable; the appropriation,
  compared with planned cost), `submitted_by`, `submitted_at`, `approved_by`, `approved_at`,
  `notes`. Unique on (`office_id`, `fiscal_year_id`, `version`). At most one `approved` plan per
  office and fiscal year (partial unique index).
- **activity** (also holds outline rows): `plan_id`, `lineage_id` (uuid, stable across plan
  versions), `parent_id` (self), `row_kind` (`outcome`/`outcome_indicator`/`output`/
  `output_indicator`/`program`/`project`/`activity`), `code`, `title`, `sort_order`; and for
  `row_kind = activity` only: `measure_type` (`quantity`/`money`/`recurring`), `unit`,
  `annual_target`, `unit_cost`, `total_cost`, `manual_weight` (nullable),
  `implementing_office_id` (defaults to the plan's office).
- **activity_target**: `activity_id`, `period_id`, `planned_qty`, `planned_amount` (nullable).
  Unique on (`activity_id`, `period_id`).
- **indicator**: `plan_id`, `lineage_id`, `code`, `name`, `kind` (`outcome`/`output`), `unit`,
  `annual_target`, `weight` (nullable), `aggregation` (`sum`/`last`), `sort_order`.
- **indicator_target**: `indicator_id`, `period_id`, `planned_value`. Unique on both.
- **reporting_period**: `fiscal_year_id`, `month_index` (1–12), `start_date`, `end_date`,
  `cutoff_at`, `status` (`open`/`locked`), `locked_by`, `locked_at`.
- **office_submission**: `office_id`, `period_id`, `status`
  (`draft`/`submitted`/`returned`/`locked`), `submitted_by`, `submitted_at`, `returned_by`,
  `returned_at`, `return_note`. Unique on (`office_id`, `period_id`).
- **activity_actual**: `activity_lineage_id`, `period_id`, `actual_qty`, `actual_amount`
  (nullable), `remarks`, `delay_reason`, `entered_by`, `updated_at`. Unique on
  (`activity_lineage_id`, `period_id`). Keyed by lineage so that a new plan version keeps the
  accomplishments already reported.
- **indicator_actual**: `indicator_lineage_id`, `period_id`, `actual_value`, `remarks`,
  `entered_by`, `updated_at`. Unique on both.
- **attachment**: `target_type` (`activity_actual`/`indicator_actual`), `target_id`, `file_name`,
  `content_type`, `size_bytes`, `sha256`, `storage_key`, `description`, `uploaded_by`,
  `uploaded_at`, `deleted_at` (soft delete; the file is kept).
- **period_result** (written only when a period is locked): `period_id`, `office_id`, `view`
  (`owner`/`implementing`), `plan_version`, `periodic_plan`, `periodic_actual`, `cum_plan`,
  `cum_actual`, `variance`, `status_label`, `funds_total`, `funds_used_est`, `funds_used_actual`
  (nullable), `indicator_score` (nullable), `rank_sibling` (nullable), `detail` (jsonb: per-activity
  and per-indicator figures, per-group ranks), `profile_snapshot` (jsonb copy of the scoring
  profile), `computed_at`. Unique on (`period_id`, `office_id`, `view`).

### 6.5 Tables — operations

- **audit_log**: `id` (bigserial), `at`, `actor_type` (`user`/`platform_admin`/`system`),
  `actor_id`, `action` (e.g. `login`, `login_failed`, `create`, `update`, `delete`, `submit`,
  `return`, `approve`, `lock`, `unlock`, `export`, `import`, `upload`, `download`,
  `role_change`, `support_grant`), `entity_type`, `entity_id`, `before` (jsonb), `after` (jsonb),
  `ip`, `user_agent`, `request_id`. `agency_id` is nullable here only for platform-level events.
  `app_user` has `INSERT` and `SELECT` only — `UPDATE` and `DELETE` are revoked at the database.
- **alert_rule** (one per agency): `remind_days_before` (int array, default `{5,1}`),
  `delay_threshold` (ratio, default `0.05`), `email_enabled` (bool).
- **notification**: `user_id`, `type`, `title`, `body`, `link`, `created_at`, `read_at`,
  `emailed_at`, `dedupe_key` (unique; prevents sending the same alert twice).
- **export_template**: `kind` (`xlsx`/`pptx`), `name`, `settings` (jsonb: titles, colours, logo
  use), `is_default`. A system default exists for each kind; `agency_id` null means system-wide
  (the RLS policy for this table also allows rows where `agency_id is null` for `SELECT`).
- **job**: `kind` (`export_xlsx`/`export_pptx`/`import_plan`/`alert_scan`/`lock_period`),
  `params` (jsonb), `status` (`queued`/`running`/`done`/`failed`), `result_key`, `error`,
  `requested_by`, `attempts`, `created_at`, `started_at`, `finished_at`.

Total: 27 tables.

### 6.6 Permissions (F3)

Implement once in `accounts/permissions.py` and use everywhere:

- `scope(user)` = set of offices whose `path` starts with the `path` of any office the user is
  assigned to.
- `can_view(user, office)` = office in scope (any level).
- `can_edit(user, office)` = office in scope through an `admin` assignment.
- `is_agency_admin(user)` = has an `admin` assignment at the root office.
- Only an agency administrator may: change structure, levels, groups, users, role assignments,
  fiscal years, scoring profiles, alert rules; approve plans; return submissions; lock and unlock
  periods; view the audit log.
- `read_only` users may view and export within scope and download MOVs; they change nothing.
- Uploads: check extension and sniffed content type against D15, enforce `MAX_UPLOAD_MB`, compute
  SHA-256, store under `<agency_id>/mov/<yyyy>/<uuid>-<safe name>`. Call
  `exports/hooks.scan_upload(file)` (a no-op in version 1) so a scanner can be added later.

### 6.7 Job queue

- `jobs/worker.py` loop: `SELECT ... FROM job WHERE status='queued' ORDER BY created_at
  FOR UPDATE SKIP LOCKED LIMIT 1`, mark `running`, run the handler inside the agency context,
  mark `done`/`failed`. Retry up to 3 attempts. Jobs `running` for more than 30 minutes are
  re-queued at worker start.
- The same loop triggers the daily `alert_scan` and, if `auto_lock` is on, `lock_period` jobs.
  Scheduling state lives in the database, not in memory.
- `manage.py run_worker` is the worker container's command.

---

## 7. Scoring specification (the business logic)

Implement in `backend/apps/scoring/engine.py` as pure functions over plain data classes (no
database access). `results/services.py` loads data, calls the engine and returns or stores the
output. Use Python `Decimal` throughout; round only for display (two decimal places for percent).

### 7.1 Inputs for one plan

For each scoreable activity `a` (rows with `row_kind = activity`):
`T_a` annual target, `C_a` total cost, `p_a,m` planned quantity (or amount) in month `m`,
`x_a,m` actual quantity (or amount) in month `m`, for `m = 1..12`.

### 7.2 Weights

| Setting | Weight `w_a` |
|---|---|
| `cost_share` | `C_a / Σ C` over scoreable activities of the plan. If `Σ C = 0`, fall back to `equal`. |
| `equal` | `1 / n` |
| `manual` | `manual_weight`; the plan cannot be approved unless the weights sum to 1 (±0.0001). |

Under `cost_share`, an activity with `C_a = 0` has weight 0; the plan screen must warn about it.

### 7.3 Activity progress

Let `S_a,m = Σ_{k≤m} x_a,k` and `P_a,m = Σ_{k≤m} p_a,k`.

- `quantity` and `money`: planned ratio `rp_a,m = P_a,m / T_a`; actual ratio `ra_a,m = S_a,m / T_a`.
  For `money`, `T_a` is the planned total amount and `x` is the amount disbursed.
- `recurring` (a level maintained every month, e.g. number of scholars paid): let `M_a` be the
  months with `p_a,k > 0` and `n_a` their count. Planned ratio `rp_a,m = (count of k≤m in M_a) / n_a`.
  Actual ratio `ra_a,m = Σ_{k≤m, k∈M_a} (x_a,k / p_a,k) / n_a`.
- If `cap_at_100` is on: `ra_a,m = min(ra_a,m, 1)`.
- If `T_a = 0` (or `n_a = 0`): both ratios are 0 and the activity is reported as "no target".

### 7.4 Office result for a plan

- Cumulative plan `CP_m = Σ_a w_a · rp_a,m`; cumulative actual `CA_m = Σ_a w_a · ra_a,m`.
- Periodic values are differences: `PP_m = CP_m − CP_{m−1}`, `PA_m = CA_m − CA_{m−1}` (`CP_0 = CA_0 = 0`).
- Variance `V_m = CA_m − CP_m`.
- Status, with tolerance `t = on_time_tolerance`, after rounding `V_m` to 9 decimal places:
  `V_m > t` → ahead label; `|V_m| ≤ t` → on-time label; `V_m < −t` → delayed label.
  (The rounding removes floating-point residue; the workbook once showed "delayed" for −5.55e-17.)
- Funds: `funds_total = Σ C_a`; `funds_used_est = funds_total · CA_m`;
  `funds_used_actual = Σ actual_amount through m` if any amount was entered, else null;
  `funds_remaining = funds_total − (funds_used_actual if present else funds_used_est)`.

### 7.5 Indicators

- Rate `r_i,m = (Σ_{k≤m} actual) / annual_target` for `aggregation = sum`; for `last`, the most
  recent actual through `m` divided by the annual target. With `cap_at_100`: `min(r, 1)`.
- Office indicator score = `Σ weight_i · r_i,m` with equal weights `1/n` by default.
- Roll-up of indicator scores: `all_indicators` = unweighted mean of every indicator in the
  subtree (the workbook's rule); `office_scores` = mean of the child offices' indicator scores.

### 7.6 Roll-up along the owner tree

For an office with children and/or its own approved plan, the *components* are its own plan (if
any) and each child office that has a result.

- `budget_weighted`: `CA = Σ_j B_j · CA_j / Σ_j B_j`, same for `CP`, where `B_j` is the
  component's `funds_total` (a child's `funds_total` is the sum of its components').
- `simple_average`: unweighted mean of the components.
- Variance, status and funds are then derived as in 7.4. Apply the same rule at every level.

### 7.7 Implementing view

For an office `o`, take every activity in any approved plan of the fiscal year whose
`implementing_office_id = o`, re-normalise weights among them with the profile's weighting rule,
and compute 7.3–7.4. Implementing-view results are for display and ranking only; they never feed
the owner-tree roll-up (that would count an activity twice).

### 7.8 Ranking

A ranking set is either the children of one office or the members of one office group. Metric by
`ranking_metric`: `cumulative_actual` = `CA_m`; `variance` = `V_m`; `actual_over_plan` =
`CA_m / CP_m` (0 if `CP_m = 0`). Sort descending on the metric rounded to 4 decimal places of a
percent (i.e. ratio rounded to 6 places). Equal values share a rank; the next rank skips
(1, 1, 3). Offices with no result are listed last, unranked. For group members that own no plan,
use the implementing view.

### 7.9 Which data a month uses

- An accomplishment counts in the period it is entered against. Entries for a locked period are
  impossible; late accomplishments are reported in the current open period and earn full credit
  (workbook rule).
- Open periods are computed live from the currently approved plan version.
- Locked periods are read from `period_result` and never recomputed, except by an explicit
  unlock → re-lock.
- An office whose plan is not yet approved has no result ("no approved plan").

### 7.10 Presets

| Preset | Settings |
|---|---|
| `workbook_compatible` (default) | `cost_share`, `cap_at_100 = false`, tolerance 0, labels ADVANCED / ON-TIME / DELAYED, `budget_weighted`, indicators `equal` + `all_indicators`, ranking `cumulative_actual` |
| `capped_with_tolerance` | as above but `cap_at_100 = true`, tolerance 0.02 |

---

## 8. Test vectors

### 8.1 Worked example (must be a unit test; needs no external file)

Three activities, `cost_share`:

| Activity | Cost | Target | Plan Jan/Feb/Mar | Actual Jan/Feb/Mar |
|---|---|---|---|---|
| A | 600,000 | 10 | 2 / 3 / 5 | 2 / 2 / 4 |
| B | 300,000 | 4 | 0 / 2 / 2 | 0 / 1 / 3 |
| C | 100,000 | 1 | 0 / 0 / 1 | 0 / 0 / 0 |

Weights 0.6, 0.3, 0.1. Expected:

| Month | Cumulative plan | Cumulative actual | Variance | Status |
|---|---|---|---|---|
| Jan | 0.12 | 0.12 | 0 | ON-TIME |
| Feb | 0.45 | 0.315 | −0.135 | DELAYED |
| Mar | 1.00 | 0.78 | −0.22 | DELAYED |

March funds: total 1,000,000; used (estimate) 780,000; remaining 220,000.

Over-delivery variant: change B's March actual to 5. March cumulative actual = **0.93** with
`cap_at_100 = false`, **0.78** with `cap_at_100 = true`.

Roll-up: office X (budget 1,000,000, CA 0.78) and office Y (budget 3,000,000, CA 0.90):
`budget_weighted` = **0.87**, `simple_average` = **0.84**.

Ranking: values 0.90, 0.90, 0.80 → ranks 1, 1, 3.

### 8.2 Real-data vectors from the MOST workbook (December 2023)

Source file: `reference/MOST MONITORING TOOL 2024.xlsx` (33 sheets). Task P4.2 extracts the six
error-free entry sheets into JSON fixtures. Expected cumulative accomplishment for month 12,
`workbook_compatible` preset, tolerance ±0.005 percentage points:

| Sheet | Budget (Σ cost) | Expected CA (Dec) | Extraction notes |
|---|---|---|---|
| PME | sum of column L, rows 13–28 | **95.83%** | Weighted block at AA:AL. Layout as in section 9 except the block position. |
| HRM | sum of column L | **83.68%** | Same shape as PME. |
| RDI | 21,123,500 | **99.07%** | Weighted block at AD:AO. |
| AST | 13,095,400 | **58.76%** | The file's own total reads 58.59% because the January–March weighted formulas were deleted. Compute from the quantities in O:Z; expect 58.76%. |
| ILD | 21,571,200 | **90.23%** | The file's own total reads 90.58% because its total formula adds row 17 twice. Compute from quantities; expect 90.23%. |
| GAS | 107,678,522 (cell `K311`) | **80.16%** | Money measure: total disbursement 86,318,893.37 ÷ planned 107,678,522. Layout differs (plan cost and disbursement rows); extract plan and disbursement by month. |

In every entry sheet: column H (or F in PME/HRM) holds the activity title, I = QTY, J = UNIT,
K = UNIT COST, L = TOTAL COST, M = weight, N = `PLAN`/`ACTUAL` label, O:Z = January–December
quantities. An activity is a `PLAN` row followed by its `ACTUAL` row. Ignore the weighted block
and total rows (recompute them). Do **not** use the sheets STS, SESG or the seven provincial
sheets: they are in a broken, half-migrated state.

Roll-up vectors (budget-weighted):

- RDS = RDI + AST + ILD: (0.99072 × 21,123,500 + 0.58764 × 13,095,400 + 0.90230 × 21,571,200)
  ÷ 55,790,100 = **86.19%**.
- GAS as a money-measure office: **80.16%**.

Ranking vector (from the December 2023 deck, provincial centers): Basilan 96.27, Maguindanao
96.23, SGA 96.18, Lanao del Sur 93.50, Cotabato 87.74, Tawi-Tawi 87.37, Sulu 76.57 → ranks 1–7 in
that order.

If `reference/` is not available to the agent, skip the 8.2 fixtures, mark P4.2 and P4.6 with
`> BLOCKED: reference files missing`, continue with 8.1, and note it in STATUS. Do not invent data.

---

## 9. Excel export specification (F6, D10)

One workbook per request. Sheets: `SUMMARY`, then one sheet per office in scope that has an
approved plan (sheet name = office code, max 31 characters). Written with XlsxWriter. All
percentages are live formulas so the file recalculates when opened.

### 9.1 Office sheet layout (rows and columns are fixed)

| Cell / range | Content |
|---|---|
| `A1` | `Fiscal Year <label>` |
| `A2` | Agency name; `A3` office name; `A4` `As of <Month YYYY>` |
| Row 5 | `A` = name of the agency's level 0 in capitals (e.g. `MINISTRY`), `B` `OUTCOME STATEMENT`, `C` `OUTCOME INDICATORS`, `D` `OUTPUTS`, `E` `OUTPUT INDICATORS`, `F` `PROGRAMS`, `G` `PROJECTS`, `H` `ACTIVITIES`, `I:J` merged `TARGETS`, `K:L` merged `PROJECTED COST`, `O:Z` merged `INDICATIVE SCHEDULE OF IMPLEMENTATION (MONTHLY)`, `AD:AO` merged with the same text |
| Row 6 | `O` `Q1`, `R` `Q2`, `U` `Q3`, `X` `Q4` (each merged over 3 columns); the same at `AD`, `AG`, `AJ`, `AM` |
| Row 7 | `I` `QTY`, `J` `UNIT`, `K` `UNIT COST`, `L` `TOTAL COST`, `M` `Wtd%`, `N` `REMARKS`, `O:Z` month abbreviations in fiscal-year order (`JAN` … `DEC`), `AD:AO` the same |
| Row 8 onward | One row per outline row, text (`code` + space + `title`) in the column of its kind: outcome → B, outcome indicator → C, output → D, output indicator → E, program → F, project → G. Row 8 column A holds the office name in capitals. |
| Activity, PLAN row `r` | `H` code + title, `I` annual target, `J` unit, `K` unit cost, `L` total cost, `M` `=L{r}/$L${t}`, `N` `PLAN`, `O:Z` planned quantities, `AD:AO` `=O{r}*$M{r}/$I{r}` (column moves with the month) |
| Activity, ACTUAL row `r+1` | `N` `ACTUAL`, `O:Z` actual quantities (blank for months after the selected month), `AD:AO` `=O{r+1}*$M{r}/$I{r}` |
| Total row `t` | `B` and `H` `TOTAL COST`, `L` `=SUM` of the PLAN rows' costs, `M` `=SUM` of the weights |
| `t+1` | `U` `Plan`, `W` `Periodic`, `AD:AO` `=SUMIF($N${first}:$N${last},"PLAN",AD${first}:AD${last})` |
| `t+2` | `W` `Commulative(Plan)` (spelling kept from the source), `AD` `=AD{t+1}`, then `AE` `=AE{t+1}+AD{t+2}` … |
| `t+3` | `U` `Actual`, `W` `Periodic`, `AD:AO` the same `SUMIF` with `"ACTUAL"` |
| `t+4` | `W` `Commulative(Actual)`, running total of `t+3` |
| `t+5` | `U` `Variance`, `W` `Periodic`, `=AD{t+3}-AD{t+1}` |
| `t+6` | `W` `Commulative(Variance)`, `=AD{t+4}-AD{t+2}` |
| `t+8` | `U` `FUNDS TOTAL`, `W` `=L{t}` |
| `t+9` | `U` `FUNDS USED`, `W` `=<cumulative actual cell of the selected month>*W{t+8}` |
| `t+10` | `U` `FUNDS REMAINING`, `W` `=W{t+8}-W{t+9}`; `t+11` `U` `STATUS`, `W` the status label as text |
| Indicator header `t+13` | `H` `OUTPUT INDICATORS`, `L` `TOTAL`, `N` `WTD%`, `O:Z` month names in full capitals (`JANUARY` …), `AD:AO` the same |
| Indicator target row `q` | `H` code, `I` name, `L` `=SUM(O{q}:Z{q})`, `N` weight, `O:Z` monthly targets, `AD:AO` `=(O{q}/$L{q})*$N{q}` |
| Indicator actual row `q+1` | `L` `=SUM(O{q+1}:Z{q+1})`, `O:Z` monthly actuals, `AD:AO` `=(O{q+1}/$L{q})*$N{q}` |

Rules: columns `AA:AC` stay empty (as in the source). `recurring` activities cannot use the
`=O*M/I` formula: write their weighted cells as values computed by the engine and add the cell
comment "Recurring measure: value computed by the system". Under `cap_at_100` or any non-default
profile, likewise write engine values for the total rows `t+1…t+6` and state the profile on the
`SUMMARY` sheet. Formats: costs `#,##0.00`, weights and weighted cells `0.00%`, header rows bold
with fill, freeze panes at `O8`, print area and landscape A3 fit-to-width.

### 9.2 SUMMARY sheet

One row per office in scope (tree order, indented by depth): office code and name, funds total,
cumulative plan %, cumulative actual %, variance, status, indicator score, rank among siblings.
Header shows agency, fiscal year, "As of" month, scoring preset and whether the month is locked
("FINAL") or open ("PROVISIONAL").

### 9.3 Acceptance

Opening the exported file in Excel or LibreOffice and recalculating must give the same cumulative
percentages (±0.005 points) as the dashboard for the same month. P9 tests do this with LibreOffice
headless if available, otherwise by evaluating the written formulas with a small evaluator in the
test.

### 9.4 Plan import template (D17)

The import template is the same office sheet with headers only. Import reads rows from row 8,
classifies outline rows by column, pairs each `PLAN` row with the `ACTUAL` row beneath it (actuals
are ignored on import), validates (the checks are listed in task P5.4) and creates a
**draft** plan. Nothing is imported if any row has an error; the job returns a row-by-row error
list.

---

## 10. PowerPoint export specification (F7, D11)

16:9 deck built with python-pptx, native charts, for one selected month and one scope.

| Slide | Content |
|---|---|
| 1 Title | Agency logo and name, "Performance Monitoring Report", "As of <Month YYYY>", FINAL or PROVISIONAL |
| 2 Overall | The scope's root office: four figures (cumulative plan %, cumulative actual %, variance, status); line chart of cumulative plan vs cumulative actual for months 1..12 (actual series stops at the selected month); doughnut of funds used vs remaining with peso amounts; indicator score |
| 3…n Office slides | One per office in tree order, same layout as slide 2, plus a clustered bar of its children's cumulative actual % when it has children. Footer "Page x of n" |
| Ranking slides | One per ranking set in scope (children of each parent that has ≥ 2 children, then each office group): table of rank, office, cumulative actual %, variance, status; at most 12 rows per slide, continued on the next |
| Indicators slide(s) | Table per office: indicator, annual target, actual to date, rate |
| Last | Notes: scoring preset, date generated, generated by |

Colours and logo come from `export_template.settings`. All numbers come from the same service the
dashboard uses.

---

## 11. Phases

Each phase lists: goal, start-state check, tasks, exit checks. Task ids are stable — refer to them
in commits and in the STATUS block.

---

### Phase 0 — Repository, tooling, containers, pinned versions

**Goal:** an empty but running skeleton: `make up` starts web, worker and database; `make check`
passes.

**Verify start state:** repository contains this file; nothing else is required.

- [x] **P0.1** Initialise git, `.gitignore` (include `reference/`, `.env`, `node_modules`,
  `frontend/dist`, `__pycache__`), `README.md`, the directory layout of section 5.3.
- [x] **P0.2** Decide exact versions for every row of the table in 5.2 by checking each project's
  official site; write them into the table in this file and into `backend/requirements.txt`
  (hashes pinned with `pip-compile` or `uv`) and `frontend/package.json` + lockfile. Record every
  dependency's licence in `docs/THIRD_PARTY.md`; replace any that breaks the licence rule.
- [x] **P0.3** Create the Django project `config` with settings split `base/dev/prod`, the empty
  apps of 5.3, environment-variable configuration (5.4), `ATOMIC_REQUESTS = True`, UTC storage,
  custom user model declared from the first migration.
- [x] **P0.4** Create the Vite + React + TypeScript app with routing, an API client using the
  session cookie and CSRF header, and a placeholder sign-in page. Bundle all assets locally.
- [x] **P0.5** `deploy/Dockerfile` (multi-stage: build frontend, install backend, collect static)
  and `deploy/docker-compose.yml` with services `db`, `web`, `worker`. Database init script
  creates roles `app_owner` and `app_user` (section 6.1). Until P7.7 the worker command
  `manage.py run_worker` is a stub loop that only records a heartbeat.
- [x] **P0.6** `Makefile` targets: `up`, `down`, `migrate`, `test`, `lint`, `check` (= lint +
  backend tests + frontend tests + build), `seed-demo`, `build`.
- [x] **P0.7** Health endpoint `/api/v1/health` (database reachable, storage writable, worker
  heartbeat age) and a CI workflow file that runs `make check`.

**Phase exit checks:** `make up` then `curl /api/v1/health` returns ok; `make check` passes;
versions table in 5.2 has no "check in P0.2" entries left.

---

### Phase 1 — Agencies, sign-in, roles, row-level security (F1, F3)

**Goal:** users sign in, belong to one agency, and cannot read another agency's rows even with a
deliberately wrong query.

**Verify start state:** Phase 0 exit checks pass.

- [x] **P1.1** Models and migrations: `agency`, `user`, `platform_admin`, `support_grant`,
  `role_assignment` (the `office_id` foreign key is added in P2.1; create the column now as a
  plain uuid if needed).
- [x] **P1.2** A reusable migration operation `EnableTenantRLS(table)` that enables and forces RLS
  and creates the policy of 6.1; apply it to every tenant table created so far.
- [x] **P1.3** Middleware that sets `app.agency_id` per request; worker helper that sets it per
  job; `SECURITY DEFINER` lookup function for sign-in.
- [x] **P1.4** Sign-in, sign-out, session idle timeout, account lock after 5 failed attempts for
  15 minutes, password rules (minimum 12 characters, Django validators), forced password change
  on first sign-in, password reset by an agency administrator (and by email when SMTP is set).
  > NOTE: the administrator reset is the service `accounts.services.admin_reset_password`; its
  > endpoint `users/{id}/reset-password` is added with the Users API in P2.5.
- [x] **P1.5** Optional TOTP two-factor: enrol with QR code, verify at sign-in, recovery codes.
- [x] **P1.6** Platform-owner area under `/platform/` (separate sign-in, uses `app_owner`): list,
  create, suspend agencies; create an agency's first administrator; hidden entirely when
  `DEPLOYMENT_MODE=single`. `manage.py bootstrap_single_agency` for single mode.
- [x] **P1.7** Support grants: an agency administrator can grant a platform admin time-limited
  read access; without a grant the platform area shows no agency data.
- [x] **P1.8** `accounts/permissions.py` with the functions of 6.6 and DRF permission classes.
- [x] **P1.9** Isolation tests: (a) with agency A set, raw SQL `SELECT` on every tenant table
  returns no rows of agency B; (b) inserting a row with another agency's id fails; (c) with no
  agency set, every tenant table returns zero rows; (d) a meta-test lists all models and fails if
  any model with an `agency_id` field lacks an RLS policy, or any model lacks `agency_id` without
  being on an explicit allow-list (`platform_admin`, Django internals).
- [x] **P1.10** Frontend: sign-in page, 2FA step, change-password page, session-expired handling.

**Phase exit checks:** P1.9 tests pass; two demo agencies exist in the seed and a browser session
of one cannot fetch any object id of the other (API returns 404).

---

### Phase 2 — Office structure and user management (F2, F3)

**Goal:** an agency administrator builds any hierarchy and assigns users to offices.

**Verify start state:** Phase 1 ticked; `make check` passes.

- [x] **P2.1** Models: `org_level`, `office`, `office_group`, `office_group_member`; path
  maintenance; constraints of 6.3; RLS applied.
- [x] **P2.2** API: levels CRUD; office tree read (whole tree in one call), create, rename, move,
  reorder, deactivate; groups CRUD and membership.
- [x] **P2.3** Frontend "Structure" page: tree view with add / rename / move (drag or "move to")
  / deactivate; level names editor; paste-a-list import (one office per line, indentation or a
  parent-code column sets the parent) with preview before saving.
- [x] **P2.4** Frontend "Groups" page.
- [x] **P2.5** Users page (agency administrator only): create user, deactivate, reset password,
  assign to offices with a level; show each user's effective scope.
- [x] **P2.6** Scope enforcement in the API base queryset: every office-bound endpoint filters by
  `scope(user)`; tests for view vs edit vs out-of-scope.
- [x] **P2.7** First-run setup wizard for a new agency: level names → root office → offices →
  first users.

**Phase exit checks:** tests prove an `admin` of a mid-level office cannot see or edit a sibling
office; moving a subtree keeps all paths correct; the seed builds a three-level and a five-level
agency with no code changes.

---

### Phase 3 — Audit log (F4)

**Goal:** every sign-in and every change is recorded and cannot be altered.

**Verify start state:** Phase 2 ticked.

- [x] **P3.1** `audit_log` model; revoke `UPDATE`/`DELETE` from `app_user` in a migration; RLS
  allowing an agency to read only its own rows.
- [x] **P3.2** `audit.record(action, entity, before, after)` service plus a model mixin / DRF
  mixin that records create, update and delete with field-level before/after (exclude password
  and secret fields). Request id, IP and user agent captured by middleware.
- [x] **P3.3** Wire auditing into everything built in Phases 1–2 (sign-in success and failure,
  role changes, structure changes, support grants).
- [x] **P3.4** A test that walks every registered API route with an unsafe method and fails if a
  successful call writes no audit row (allow-list only for sign-out and notification-read).
- [x] **P3.5** Audit page (agency administrator): filter by date range, user, action, office,
  entity; row detail with before/after; CSV download (itself audited as `export`).

**Phase exit checks:** P3.4 passes; attempting `UPDATE audit_log` as `app_user` fails in a test.

---

### Phase 4 — Scoring engine (the business logic)

**Goal:** `scoring/engine.py` implements section 7 exactly and passes section 8.

**Verify start state:** Phase 0 ticked (this phase does not need Phases 1–3).

- [x] **P4.1** Data classes for engine input and output (activity, indicator, profile, office
  result, ranking row). No ORM imports in `engine.py` (enforce with a test that inspects imports).
- [x] **P4.2** `tools/extract_fixtures.py`: read `reference/MOST MONITORING TOOL 2024.xlsx` with
  openpyxl (formulas ignored, values from typed cells only) and write
  `backend/fixtures/most_fy2023_<sheet>.json` for PME, HRM, RDI, AST, ILD and GAS following the
  notes in 8.2. Commit the JSON (it is sample data), not the workbook.
  > DONE 2026-11-15: workbook supplied by the owner; fixtures extracted for all six sheets (PME 6,
  > HRM 9, RDI 10, AST 6, ILD 31 activities; GAS as one money-measure line from rows 311/312).
  > Formula data cells use Excel's saved results (D31).
- [x] **P4.3** Write the tests of 8.1 first; then implement weights (7.2), progress (7.3) for all
  three measure types, office result (7.4) including status rounding and funds.
- [x] **P4.4** Indicators (7.5), roll-up (7.6) for both rules, implementing view (7.7), ranking
  (7.8) with ties.
- [x] **P4.5** Presets (7.10) as data, with a test that each preset loads into a valid profile.
- [x] **P4.6** Golden tests for 8.2: six sheet results, the RDS roll-up, the ranking vector.
  > DONE 2026-11-15: all six sheets, the RDS roll-up (86.19%) and the ranking vector pass; the same
  > figures are reproduced through the API in `backend/tests/test_most_end_to_end.py`.
- [x] **P4.7** Property tests: weights sum to 1; cumulative values are non-decreasing when
  actuals are non-negative; with `cap_at_100` no office exceeds 1; `budget_weighted` roll-up of
  identical children equals the child value.

**Phase exit checks:** all scoring tests pass; coverage of `scoring/engine.py` ≥ 95%.

---

### Phase 5 — Fiscal years, scoring profiles, plans, activities, indicators (F9)

**Goal:** offices enter, submit and get approval for plans; revisions are versioned.

**Verify start state:** Phases 3 and 4 ticked.

- [x] **P5.1** Models: `fiscal_year`, `reporting_period`, `scoring_profile`, `plan`, `activity`,
  `activity_target`, `indicator`, `indicator_target`; RLS; audit.
- [x] **P5.2** Fiscal-year API and page: create (generates 12 periods from the agency's start
  month and a profile from the default preset), open, close. Scoring-profile page with every
  setting of 6.4 explained in plain language and a preset picker. Changing a profile after any
  period of that year is locked requires confirmation and never changes locked results.
- [x] **P5.3** Plan API: create draft for (office, fiscal year); read with outline, activities,
  targets and indicators in one call; bulk save (the grid posts all changed rows at once);
  submit; approve; return to draft.
- [x] **P5.4** Plan validation service (run on save as warnings, on submit as errors):
  monthly targets must sum to the annual target for `quantity` and `money`; `total_cost` should
  equal `annual_target × unit_cost` when both are present (warning only, cost may be typed);
  zero cost under `cost_share` (warning); `manual` weights sum to 1; duplicate codes; activity
  with no target; implementing office must be in the same agency.
- [x] **P5.5** Plan editor page: outline panel (add / indent / reorder rows by kind) and a
  spreadsheet-style grid: columns code, title, unit, target, unit cost, total cost, weight
  (computed, read-only unless `manual`), implementing office, twelve monthly cells, row total.
  Paste from Excel into a cell range; keyboard navigation; undo; validation messages on the row;
  live planned curve and weight chart beside the grid (computed by calling the engine endpoint).
- [x] **P5.6** Indicators tab on the same page (name, unit, kind, annual target, weight, monthly
  targets).
- [x] **P5.7** Versioning: "Revise plan" on an approved plan clones it into a new draft version
  with the same `lineage_id` per row; approving the new version marks the old one `superseded`;
  rows removed in the new version keep their past actuals but stop being scored for open months;
  a version comparison view lists added, removed and changed rows.
- [x] **P5.8** Plan approval queue for the agency administrator; approved budget entry and a
  "budget vs planned cost" line per office.
- [x] **P5.9** Copy last year's plan into a new fiscal year as a draft (targets kept, actuals
  not).

**Phase exit checks:** the demo seed loads the six MOST fixtures (or, if P4.2 is blocked, the
worked example of 8.1) as plans of a sample agency through the public API, not by writing rows
directly; an end-to-end test creates, submits,
approves, revises and re-approves a plan; every action appears in the audit log.

---

### Phase 6 — Monthly reporting and MOV uploads (F9, F11)

**Goal:** offices report accomplishments month by month with supporting files.

**Verify start state:** Phase 5 ticked.

- [x] **P6.1** Models: `office_submission`, `activity_actual`, `indicator_actual`, `attachment`;
  RLS; audit.
- [x] **P6.2** Storage layer: `FILE_STORAGE=local|s3`, upload rules of 6.6, authorised download
  endpoint, soft delete. Tests for wrong type, oversize, and cross-agency download (404).
- [x] **P6.3** Reporting API: read one office's month (activities with target for the month,
  cumulative target, previous cumulative actual, this month's actual, remarks, attachments);
  bulk save; submit; agency administrator returns with a note.
- [x] **P6.4** Edit rules: actuals can be saved only when the period is `open` and the submission
  is `draft` or `returned`; only by a user with `can_edit` on the plan's office **or** on the
  activity's implementing office (D6: field units report their own activities).
- [x] **P6.5** Monthly entry page: month picker; grid with one row per activity (target this
  month, actual this month input, cumulative target vs actual, a small progress bar, status
  chip); a required "reason for delay" when the activity's cumulative actual is behind plan;
  attach / view MOVs per row (drag-and-drop, multiple files); indicators tab; a live result
  panel (this month, cumulative, variance, status) that updates as numbers are typed; "Submit".
- [x] **P6.6** If the profile has `mov_required`, block submission while any row with a non-zero
  actual has no attachment, and show which rows.
- [x] **P6.7** Optional actual-amount column (D7), hidden by default, switchable per agency.
- [x] **P6.8** "My implementing activities" view for an office that implements activities owned
  by other offices.

**Phase exit checks:** end-to-end test: a field-unit admin reports on an activity owned by a
division; both the division's owner view and the field unit's implementing view change; a
read-only user gets 403 on save; files are stored under the agency's folder.

---

### Phase 7 — Cutoff, locking, frozen results (F10)

**Goal:** a locked month cannot change and its results are stored forever.

**Verify start state:** Phase 6 ticked.

- [x] **P7.1** `period_result` model; `results/services.py` with `compute_live(period, office,
  view)` and `compute_agency(period)` (loads data once, calls the engine, returns results for
  every office in both views with ranks).
- [x] **P7.2** Cutoff calendar: `cutoff_at` for each period derived from `cutoff_day`, editable
  per period by the agency administrator.
- [x] **P7.3** Lock: sets the period `locked`, sets all submissions `locked`, writes
  `period_result` rows for every office and view with the profile snapshot, in one transaction.
  A period can be locked only if all earlier periods of the year are locked.
- [x] **P7.4** Unlock: agency administrator only, reason required; allowed only for the latest
  locked period; deletes that period's `period_result` rows after copying them into the audit
  row; re-lock recomputes.
- [x] **P7.5** Database trigger (defence in depth): reject insert/update/delete on
  `activity_actual`, `indicator_actual` and `attachment` rows whose period is `locked`.
- [x] **P7.6** Submission board page: every office × status for the chosen month, who submitted
  and when, days to cutoff, buttons Return / Lock / Unlock, and a list of offices that have not
  submitted.
- [x] **P7.7** `job` model (RLS, audit), the worker loop of section 6.7 replacing the stub from
  P0.5, and the `lock_period` job that locks automatically when `auto_lock` is on and `cutoff_at`
  has passed.
- [x] **P7.8** Results read path: one function `get_result(period, office, view)` that returns
  the frozen row for locked periods and the live computation for open ones, flagged
  `final`/`provisional`. Everything in Phases 8–11 uses only this function.

**Phase exit checks:** tests: saving an actual in a locked period fails at both the API and the
database trigger; changing the scoring profile or the plan after locking does not change
`get_result` for that period; lock → unlock → lock is fully audited.

---

### Phase 8 — Dashboards and ranking (F5)

**Goal:** executives see the agency's performance for any month and drill down.

**Verify start state:** Phase 7 ticked.

- [x] **P8.1** Dashboard API: for (office, period, view) return headline figures, twelve-month
  cumulative plan and actual series (actual stops at the selected period), funds, status,
  indicator table, children summary, rankings for the office's children and for groups in scope.
  One call per screen.
- [x] **P8.2** Agency dashboard page: month picker; headline tiles; S-curve; funds doughnut;
  ranking table of top-level offices; FINAL / PROVISIONAL badge.
- [x] **P8.3** Office page (same layout) with breadcrumb drill-down to children, then to the
  activity list (target, actual, variance, status, delay reason), then to an activity's month
  history and MOVs.
- [x] **P8.4** Ranking page: choose a ranking set (children of an office, or a group); table and
  horizontal bar chart; rank change against the previous month.
- [x] **P8.5** Owner / implementing view switch wherever an office has both.
- [ ] **P8.6** Quarter and year-to-date summaries derived from monthly results (D9).
- [ ] **P8.7** Chart rules: one shared chart theme; status colours always paired with the status
  word; every chart has a "view as table" toggle; numbers formatted to two decimals with the
  percent sign; peso amounts with thousands separators.
- [ ] **P8.8** Performance: the agency dashboard for the D13 sizing ceiling returns in under
  2 seconds for an open period (add query-count tests; cache live results per (period, profile
  version, latest data timestamp)).

**Phase exit checks:** with the MOST sample agency seeded and December locked, the dashboard shows
PME 95.83%, HRM 83.68%, RDI 99.07%, AST 58.76%, ILD 90.23%, GAS 80.16% and RDS 86.19%; a
read-only user scoped to one division sees only that division.

---

### Phase 9 — Excel export and plan import (F6, D10, D17)

**Goal:** a downloadable workbook in the section 9 layout, and plan import from the same layout.

**Verify start state:** Phase 8 ticked.

- [ ] **P9.1** Jobs API on top of the queue built in P7.7 (create, poll status, download
  result) and a "My exports" list.
- [ ] **P9.2** `exports/xlsx_writer.py`: office sheet exactly as 9.1, driven by a layout
  constants module (column letters and header texts in one place so a paid custom template can
  override them).
- [ ] **P9.3** SUMMARY sheet (9.2).
- [ ] **P9.4** Export dialog: scope (one office / office and everything beneath / whole agency),
  month, view. Export is audited.
- [ ] **P9.5** Acceptance test of 9.3 (recalculate and compare with the engine) for the worked
  example of 8.1 and for the RDI fixture.
- [ ] **P9.6** Layout test: for the RDI fixture, assert the header cells of rows 5–7, the column
  of each field, the PLAN/ACTUAL pairing and the formulas of the first activity and of the total
  rows, cell by cell, against 9.1.
- [ ] **P9.7** Import template download (headers only) and `import_plan` job (9.4) with a
  row-by-row error report shown in the UI; imported plans arrive as drafts.
- [ ] **P9.8** Round-trip test: export a plan, import the file into a new fiscal year, compare
  activities and targets.

**Phase exit checks:** P9.5, P9.6 and P9.8 pass; a 500-activity office exports in under 30 seconds.

---

### Phase 10 — PowerPoint export (F7, D11)

**Goal:** a ready-to-present deck for any month.

**Verify start state:** Phase 9 ticked.

- [ ] **P10.1** `exports/pptx_writer.py` following section 10, with native line, doughnut and bar
  charts and tables; layout constants in one module.
- [ ] **P10.2** `export_template` model and settings page: logo upload, primary colour, report
  title, footer text; system default template.
- [ ] **P10.3** Export dialog (scope, month, which slide groups to include) using the job queue.
- [ ] **P10.4** Tests: slide count and order for a known tree; every chart's data equals the
  dashboard API values; the deck opens with python-pptx without repair; long office names do not
  overflow (truncate with an ellipsis after measuring).

**Phase exit checks:** deck for the MOST sample agency, December, contains one slide per office
and a ranking slide whose order matches section 8.2's ranking rule.

---

### Phase 11 — Alerts and notifications (F12, D16)

**Goal:** people are told about deadlines and delays without opening a report.

**Verify start state:** Phase 10 ticked.

- [ ] **P11.1** Models `alert_rule`, `notification`; settings page for the agency administrator.
- [ ] **P11.2** Daily `alert_scan` job producing notifications with dedupe keys:

  | Trigger | Recipients |
  |---|---|
  | Cutoff in N days (N in `remind_days_before`) and office not submitted | Admins of that office |
  | Cutoff passed, not submitted | Admins of that office and agency administrators |
  | Activity with a target this month and no actual, 3 days before cutoff | Admins of that office and of the implementing office |
  | Office variance below −`delay_threshold` after a period is locked | Admins and read-only users of that office and of its ancestors |
  | Submission returned / period locked / period unlocked | Admins of the affected offices |
  | Plan submitted for approval | Agency administrators |

- [ ] **P11.3** In-app notification centre (bell with unread count, list, mark read, link to the
  relevant screen).
- [ ] **P11.4** Email delivery when `EMAIL_URL` is set and `email_enabled` is on: plain, short
  messages with a link; per-user opt-out; one digest per user per day at most.
- [ ] **P11.5** Tests with a frozen clock for each trigger, for deduplication and for the
  no-SMTP case.

**Phase exit checks:** all P11.5 tests pass; a scan run twice creates no duplicates.

---

### Phase 12 — Phone layouts and UX polish (F8, F9, D12)

**Goal:** the product is pleasant on desktop and useful, within limits, on a phone.

**Verify start state:** Phase 11 ticked.

- [ ] **P12.1** Responsive layouts (≤ 480 px wide) for: sign-in, agency dashboard, office
  dashboard, ranking, notifications, activity detail with MOV list.
- [ ] **P12.2** Phone MOV upload: from an activity's month detail, take or choose a photo and
  attach it (same rules and permissions as desktop).
- [ ] **P12.3** On small screens the plan editor, monthly grid, structure, users, settings and
  audit pages show a clear "Open on a computer to edit" message instead of a broken grid.
- [ ] **P12.4** UX pass on desktop: empty states that say what to do next; consistent status
  words; confirmation with consequences for lock, unlock, approve, deactivate; unsaved-changes
  guard; loading and error states on every page; keyboard access to the grids.
- [ ] **P12.5** Accessibility checks: colour contrast, focus order, labels on inputs, charts
  with table alternatives.
- [ ] **P12.6** In-app help: a one-page guide per role and tooltips on every scoring setting.
- [ ] **P12.7** Playwright smoke tests for the five flows of section 12 at desktop and phone
  viewport sizes.

**Phase exit checks:** P12.7 passes; no page scrolls horizontally at 360 px width.

---

### Phase 13 — Deployment packaging (D13)

**Goal:** the same build installs on one office machine or runs as a cloud service.

**Verify start state:** Phase 12 ticked.

- [ ] **P13.1** Production settings: secure cookies, HSTS when behind TLS, content security
  policy without external origins, upload size limits at the proxy, structured logs.
- [ ] **P13.2** `deploy/docker-compose.yml` (single machine: db, web, worker, Caddy with internal
  or supplied certificates) and `deploy/docker-compose.cloud.yml` (external managed PostgreSQL
  and S3-compatible storage). `.env.example` for each.
- [ ] **P13.3** `deploy/backup.sh` and `restore.sh`: database dump plus file directory, dated,
  with a retention count; restore tested from a fresh machine state in CI.
- [ ] **P13.4** `deploy/make-offline-bundle.sh`: saves images and compose files into one archive
  that installs on a machine with no internet; `install.sh` and `update.sh` inside it (update =
  backup, load images, migrate, restart, health check, automatic rollback on failure).
- [ ] **P13.5** Office-install licence: a signed licence file (Ed25519; public key in the image)
  holding agency name, expiry and seat limit; a banner 30 days before expiry; after expiry the
  system becomes read-only (never locks customers out of their data). Disabled in `multi` mode.
- [ ] **P13.6** `docs/ADMIN_GUIDE.md`: hardware sizing, install on Windows Server and Linux with
  Docker, network and VPN notes for field offices, backups, updates, SMTP, troubleshooting.
- [ ] **P13.7** Verify the single-mode install end to end on a clean VM with networking disabled
  after install: all pages load, exports work, no external requests in the browser's network log.

**Phase exit checks:** both compose files start from scratch with one command each; backup →
wipe → restore reproduces the dashboard numbers; P13.7 passes.

---

### Phase 14 — Hardening, performance, documentation, release

**Goal:** safe to put in front of a paying agency.

**Verify start state:** Phase 13 ticked.

- [ ] **P14.1** Security review against `docs/SECURITY.md` (write it): authentication, session,
  CSRF, RLS, object-level permission on every endpoint, upload handling, rate limits on sign-in
  and exports, dependency audit (`pip-audit`, `npm audit`), secrets handling.
  > NOTE (added during P2.1): PostgreSQL foreign-key checks bypass RLS, so a row of agency A
  > could reference a row id of agency B if code wrote a raw foreign id. Every API resolves
  > referenced ids through RLS-scoped querysets (foreign ids 404); P14.1 should add composite
  > `(agency_id, id)` foreign keys between tenant tables so the database itself forbids it.
- [ ] **P14.2** Automated cross-tenant test: for every API route, call it as agency A with ids
  belonging to agency B; every response must be 404 or 403.
- [ ] **P14.3** Load test at the D13 sizing ceiling: dashboard, monthly grid save, lock of a
  period (target: lock completes in under 60 seconds for one agency).
- [ ] **P14.4** Demo data: `make seed-demo` builds two sample agencies with different shapes —
  "Sample Ministry" (the MOST fixtures, three levels plus field units and two groups) and
  "Sample Bureau" (five levels, equal weighting, capped preset) — proving nothing is hard-coded.
- [ ] **P14.5** `docs/USER_GUIDE.md` (per role, with screenshots) and `docs/API.md`.
- [ ] **P14.6** Release checklist, version number, changelog, tagged build of the images.
- [ ] **P14.7** Final pass over this file: every box ticked or struck through with a reason;
  section 5.2 versions match the lockfiles; section 14 lists every deviation.

**Phase exit checks:** `make check` green; P14.2 green; a person who has never seen the system can
install it from `ADMIN_GUIDE.md` alone.

---

## 12. User flows (reference for UI work and for the smoke tests)

1. **Agency setup:** platform owner creates agency and first admin → admin names levels, builds
   the tree, picks a scoring preset, opens the fiscal year, sets the cutoff day, adds users.
2. **Planning:** office admin enters or imports the plan → fixes validation messages → submits →
   agency administrator approves → plan becomes the baseline (revisions create versions).
3. **Monthly cycle:** reminder → office admin types accomplishments, attaches MOVs, gives delay
   reasons → submits → agency administrator reviews the submission board, returns or accepts →
   locks the month → results are frozen.
4. **Monitoring:** read-only user opens the dashboard (desktop or phone) → agency score, curve,
   ranking → drills to office → activity → MOV.
5. **Reporting:** user picks month and scope → requests Excel or PowerPoint → downloads when the
   job finishes.

---

## 13. API outline

All under `/api/v1/`, JSON, session-authenticated, CSRF-protected, scoped by RLS and by
`scope(user)`. Unknown or out-of-scope ids return 404.

| Area | Resources |
|---|---|
| Auth | `auth/login`, `auth/logout`, `auth/2fa`, `auth/password`, `me` |
| Structure | `levels`, `offices` (tree, move), `groups` |
| Users | `users`, `role-assignments` |
| Planning | `fiscal-years`, `scoring-profiles`, `plans` (bulk save, submit, approve, revise, compare), `plans/{id}/import` |
| Reporting | `periods`, `submissions` (bulk save, submit, return), `attachments` |
| Locking | `periods/{id}/lock`, `periods/{id}/unlock`, `submission-board` |
| Results | `dashboard`, `rankings`, `results/preview` (engine call for unsaved grid data) |
| Exports | `jobs`, `exports/xlsx`, `exports/pptx`, `export-templates` |
| Alerts | `alert-rules`, `notifications` |
| Audit | `audit-log` |
| Platform | `/platform/api/agencies`, `/platform/api/support-grants` (separate session) |

---

## 14. Decision log (append only)

Record here any change to sections 2–10 made during the build: date, who/what agent, what
changed, why. Start ids at D19.

| ID | Date | Change | Reason |
|---|---|---|---|
| — | 2026-11-15 | `export_job` and `import_job` from the Step 1 proposal are merged into one `job` table; `support_grant` table added. Table count stays 27. | Simpler queue; makes the platform owner's "no data access without a grant" rule enforceable. |
| D19 | 2026-11-15 | Two-factor uses `pyotp` + `qrcode` instead of `django-otp`. (Claude Code, P0.2) | django-otp is under the Unlicense, which is not on the 5.2 licence allow-list; pyotp is MIT. |
| D20 | 2026-11-15 | Licence exception: `psycopg` (LGPL-3.0) is allowed as the PostgreSQL driver. (Claude Code, P0.2) | Django supports only psycopg/psycopg2, both LGPL. Used unmodified and dynamically loaded, which LGPL permits commercially. Product owner should confirm. |
| D21 | 2026-11-15 | TypeScript pinned to 6.0.3, not 7.x. (Claude Code, P0.2) | typescript-eslint 8.72 requires TypeScript <6.1. Revisit when it supports 7. |
| D22 | 2026-11-15 | Property tests (P4.7) use seeded `random` generators instead of Hypothesis. (Claude Code, P0.2) | Avoid an MPL-2.0 dependency; seeded tests are reproducible. |
| D24 | 2026-11-15 | Extra columns: `user.recovery_codes` (jsonb, hashed TOTP recovery codes), `user.email_opt_out` (P11.4), `platform_admin.failed_attempts`/`locked_until`/`created_at`, `support_grant.revoked_at`/`created_at`. Table count unchanged. (Claude Code) | Needed by P1.5 recovery codes, P11.4 opt-out, platform sign-in lockout, and early revocation of a support grant. |
| D25 | 2026-11-15 | RLS policy expression is `agency_id = NULLIF(current_setting('app.agency_id', true), '')::uuid` (6.1 wrote it without NULLIF). `platform_admin` has ALL privileges revoked from app_user. (Claude Code) | After a transaction-local SET the setting reads back as '' and a bare cast raises an error; NULLIF keeps 'no agency = zero rows'. Revoking makes 6.2's 'reachable only through app_owner' a database rule. |
| D23 | 2026-11-15 | Order inside Phase 1: P1.8 is done before P1.6/P1.7, and the bare `org_level` and `office` models (fields, path computed on create, RLS) are created in P1.8 instead of P2.1. `role_assignment.office_id` becomes a foreign key then. P2.1 still adds moves, cycle checks, remaining constraints and groups. (Claude Code) | Permissions (6.6) are defined over office paths, and the platform area (P1.6) must create an agency's root office so its first administrator is an agency administrator (D1). |
| D26 | 2026-11-15 | `audit_log` gains `office_id` (uuid, the office the entity belongs to) and `actor_label` (the actor's email at the time). (Claude Code) | P3.5 filters by office, and the audit page must name actors even after a user is renamed or a platform admin (invisible to app_user) acted. |
| D27 | 2026-11-15 | Engine details not fixed by section 7: a `budget_weighted` roll-up whose components all have funds_total 0 uses the simple average; a roll-up's funds_used_actual is the sum of its components' actual amounts when any component has one; offices tied in a ranking are listed in the order given (tree order). (Claude Code) | Avoid division by zero and keep results defined; ordering ties by tree order is stable and predictable for exports. |
| D28 | 2026-11-15 | `reporting_period` lives in the `planning` app (5.3 listed it under reporting). `plan` also has `updated_at` and a partial unique constraint allowing at most one draft-or-submitted version per office and fiscal year. `scoring_profile` adds `show_actual_amounts` (the P6.7 switch) and defaults `cutoff_day` to 10. (Claude Code) | Creating a fiscal year creates its periods, and activity/indicator targets reference periods; one app avoids a cross-app cycle. One open version at a time keeps revision (P5.7) unambiguous. The actual-amount column is per agency per year like the other profile switches. |
| D29 | 2026-11-15 | `POST results/preview` is read-only (POST for payload size) and is allow-listed in the P3.4 audit test; `GET offices/directory` returns code and name of every active office to any signed-in user of the agency. (Claude Code) | The plan editor must get weights and curves from the engine (rule 0.2). Choosing an implementing office (D6) needs offices outside the user's own scope; only names are exposed. |
| D30 | 2026-11-15 | `activity_actual`, `indicator_actual` and `attachment` also store the owning `office_id`; `attachment` stores its `period_id`. (Claude Code) | Actuals are keyed by lineage, so the office would otherwise need a join through plan versions for every scope check, audit filter and submission-status check; the period on attachments lets the P7.5 trigger refuse changes in locked months directly. |
| D31 | 2026-11-15 | Fixture extraction (P4.2) reads Excel's saved result for a formula inside an activity's data cells (e.g. a total cost written as =K20*14), instead of treating it as empty. GAS is extracted from row 311 (GRAND TOTAL PLAN, budget K311) and row 312 (ACTUAL MONTHLY DISBURSMENT) as one money-measure line; the 4-decimal rounding residue of its monthly plan (Excel itself sums to 107678521.99999993) goes into the last planned month. (Claude Code) | Several sheets compute total cost by formula; reading them as 0 distorted cost-share weights (PME came out 100%). With these rules all six December 2023 figures and the RDS roll-up match 8.2 exactly. |
| D32 | 2026-11-15 | The worker (app_user) claims jobs through SECURITY DEFINER functions `claim_next_job()`, `requeue_stale_jobs(minutes)` and `active_agency_ids()`; `job` gains `result` (jsonb, a small summary for the UI). (Claude Code) | Without an agency set, app_user cannot see any job row, so the cross-agency claim must run with the owner's rights; the worker still needs no owner credentials. The summary lets 'My exports' and the board show outcomes without opening files. |

---

## 15. Progress log (append only, one line per completed phase or notable event)

| Date | Phase / task | Note |
|---|---|---|
| 2026-11-15 | — | Plan written. No code yet. |
| 2026-11-15 | Phase 0 | Complete. make up → /api/v1/health ok (db, storage, worker); make check green. Docker builds behind a TLS proxy need EXTRA_CA_FILE. |
| 2026-11-15 | Phase 1 | Complete. RLS forced on every tenant table and proven by generic tests; sign-in with lockout, idle timeout, TOTP; platform area with support grants; two-agency demo seed. Task order changed per D23. |
| 2026-11-15 | Phase 2 | Complete. Any-depth structure with moves, groups, paste import, users and scope; setup wizard; demo seed builds 3- and 5-level agencies through the services. |
| 2026-11-15 | Phase 3 | Complete. Append-only audit_log (DB-enforced), model-level field diffs, explicit events, route-walking coverage test, audit page with CSV. |
| 2026-11-15 | Phase 4 (not ticked) | Engine complete: 8.1 vectors, all of section 7, presets, property tests, 100% coverage. P4.2/P4.6 BLOCKED on the missing reference workbook; extractor and golden tests ready. |
| 2026-11-15 | Phase 5 | Complete. Fiscal years and profiles, plan API with validation, spreadsheet plan editor with engine preview, versions/compare, approvals, copy-forward. Demo plan (8.1 worked example, P4.2 blocked) loaded through the API. |
| 2026-11-15 | Phase 6 | Complete. Monthly entry with live engine results, MOV uploads (sniffed types, agency folders, authorised download), submit/return, implementing view. Exit e2e passes. |
| 2026-11-15 | Phase 4 | Complete. Golden 8.2 vectors pass from the real workbook (PME 95.83, HRM 83.68, RDI 99.07, AST 58.76, ILD 90.23, GAS 80.16, RDS 86.19, ranking); also reproduced through the API. |
| 2026-11-15 | Phase 7 | Complete. Frozen period_result per office and view, ordered lock/unlock with audited copies, DB trigger on locked months, job queue and worker with auto-lock, submission board, single read path (FINAL/PROVISIONAL). |
