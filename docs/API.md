# GovMonitor — API reference

Generated from the code by `tools/api_docs.py`; do not edit by hand.

## Conventions

* **Base path** `/api/v1/`. JSON in and out (multipart for file uploads). Times are ISO 8601 in UTC;
  amounts and quantities are decimal strings (e.g. `"1250.50"`); ids are UUIDs.
* **Sign-in** with `POST /api/v1/auth/login` (`{"email", "password"}`); the session cookie
  `gm_session` then authenticates every call. Call `GET /api/v1/auth/csrf` first and send the
  `gm_csrftoken` cookie's value as the `X-CSRFToken` header on every POST, PUT, PATCH and DELETE.
* **Scope**: every answer is limited to the caller's agency (database row-level security) and to the
  offices beneath their assignments. Ids outside that scope answer **404**, never revealing that they
  exist. Read-only users get **403** on changes; agency-wide settings need an agency administrator.
* **Errors**: `{"detail": "...", "code": "..."}` or field errors `{"field": ["message"]}` with
  400; 401 when not signed in (`code` `not_authenticated` or `session_expired`); 403, 404, 409 for
  conflicts (e.g. a month already locked), 429 when rate-limited.
* **Audit**: every successful change writes an audit-log row (who, what, before/after).
* **Background work** (exports, imports) returns a job (`202`); poll `GET /api/v1/jobs/{job_id}`
  and download from `download_url` when `status` is `done`.
* **Background polls** should send `X-Background: 1` so they do not count as user activity for
  the idle sign-out.
* **Read-only installs**: without a valid licence (office installs) changes answer 403 with
  `code` `licence_read_only`; reading and exports keep working.


## Sign-in and account

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/auth/csrf` | `auth-csrf` | GET sets the CSRF cookie so the SPA can make its first POST. |
| POST | `/api/v1/auth/login` | `auth-login` | Sign in: `{"email", "password"}` → `{"status": "ok", "me"}` or `{"status": "2fa_required"}`. Wrong passwords lock the account after 5 tries; 20 failures from one address in 15 minutes → 429. |
| POST | `/api/v1/auth/logout` | `auth-logout` | Sign out (ends the session). |
| POST | `/api/v1/auth/password` | `auth-password` | Change your own password: `{"current_password", "new_password"}` (at least 12 characters). |
| POST | `/api/v1/auth/password-reset` | `auth-password-reset` | Ask for a reset link by email: `{"email"}`. Always answers ok; sends nothing without SMTP. |
| POST | `/api/v1/auth/password-reset/confirm` | `auth-password-reset-confirm` | Set a new password with the emailed link: `{"agency", "user", "token", "new_password"}`. |
| POST | `/api/v1/auth/2fa` | `auth-2fa` | Second sign-in step: ``{"code": "123456"}`` or ``{"recovery_code": "abcde-fghij"}``. |
| POST | `/api/v1/auth/2fa/setup` | `auth-2fa-setup` | Start enrolment: returns a new secret, its otpauth URI and a QR code (SVG). |
| POST | `/api/v1/auth/2fa/enable` | `auth-2fa-enable` | Turn on two-step sign-in with a code from the app: `{"code"}` → one-time recovery codes. |
| POST | `/api/v1/auth/2fa/disable` | `auth-2fa-disable` | Turn off two-step sign-in: `{"password"}`. |
| GET | `/api/v1/me` | `me` | The signed-in user: name, agency, roles, whether they are agency administrator, licence status. |
| PATCH | `/api/v1/me` | `me` | Personal preferences: ``email_opt_out`` (no alert emails for me, P11.4). |

## Users and access

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/users` | `users` | Users of the agency with their access (agency administrator). |
| POST | `/api/v1/users` | `users` | Add a user: `{"email", "full_name", "assignments": [{"office_id", "level"}]}` → a temporary password, shown once. |
| GET | `/api/v1/users/{user_id}` | `user` | One user with their access. |
| PATCH | `/api/v1/users/{user_id}` | `user` | Change a user: `{"full_name"}`, `{"is_active": false}` to deactivate (the last administrator cannot be). |
| POST | `/api/v1/users/{user_id}/reset-password` | `user-reset` | The agency administrator resets a password (P1.4): one-time temporary password, shown once. |
| GET | `/api/v1/users/{user_id}/scope` | `user-scope` | The offices a user can see and change, as the permission rules compute it. |
| POST | `/api/v1/role-assignments` | `role-assignments` | Give access: `{"user_id", "office_id", "level": "admin" \| "read_only"}`. |
| PATCH | `/api/v1/role-assignments/{assignment_id}` | `role-assignment` | Change the level of one access: `{"level"}`. |
| DELETE | `/api/v1/role-assignments/{assignment_id}` | `role-assignment` | Remove one access (not the last agency administrator). |

## Agency

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/agency` | `agency` | GET the agency; PATCH name / timezone / setup_complete (agency administrator). |
| PATCH | `/api/v1/agency` | `agency` | GET the agency; PATCH name / timezone / setup_complete (agency administrator). |
| GET | `/api/v1/support-grants` | `support-grants` | Active support grants: platform-owner staff allowed to look at this agency's data. |
| POST | `/api/v1/support-grants` | `support-grants` | Let vendor support look at the agency for a time: `{"platform_admin_email", "hours", "reason"}`. |
| DELETE | `/api/v1/support-grants/{grant_id}` | `support-grant` | End a support grant now. |

## Structure

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/levels` | `levels` | Names of the structure's levels (e.g. Ministry, Service, Division). |
| PUT | `/api/v1/levels` | `levels` | Set the names of levels 0..n-1: ``{"names": ["Ministry", "Service", "Division"]}``. |
| PATCH | `/api/v1/levels/{level_id}` | `level` | Rename a level: `{"name"}`. |
| DELETE | `/api/v1/levels/{level_id}` | `level` | Remove an unused level. |
| GET | `/api/v1/offices` | `offices` | GET: every office in the caller's scope, in tree order, in one call. POST: create. |
| POST | `/api/v1/offices` | `offices` | GET: every office in the caller's scope, in tree order, in one call. POST: create. |
| GET | `/api/v1/offices/directory` | `offices-directory` | Code and name of every active office in the agency — for pick-lists such as the implementing office of an activity, which may lie outside the user's own scope (D29). No other data. |
| POST | `/api/v1/offices/import` | `offices-import` | Paste-a-list import. ``{"parent_id", "rows": [{code, name, depth, parent_code}], "dry_run"}``. |
| POST | `/api/v1/offices/reorder` | `offices-reorder` | Order siblings: `{"parent_id", "order": [office ids]}`. |
| GET | `/api/v1/offices/{office_id}` | `office` | One office with its place in the tree. |
| PATCH | `/api/v1/offices/{office_id}` | `office` | Rename or recode an office, or set `{"is_active"}`. |
| DELETE | `/api/v1/offices/{office_id}` | `office` | Delete an unused office; with ``?everything=1``, the office, every office beneath it and everything recorded for them (see ``delete-preview``). |
| GET | `/api/v1/offices/{office_id}/delete-preview` | `office-delete-preview` | GET — what deleting this office with everything recorded for it would remove. |
| POST | `/api/v1/offices/{office_id}/move` | `office-move` | Move an office and everything beneath it: `{"parent_id"}`. |
| GET | `/api/v1/groups` | `groups` | Office groups (sets of offices compared in rankings). |
| POST | `/api/v1/groups` | `groups` | Create a group: `{"name"}`. |
| GET | `/api/v1/groups/{group_id}` | `group` | One group with its members. |
| PATCH | `/api/v1/groups/{group_id}` | `group` | Rename a group or change its order. |
| DELETE | `/api/v1/groups/{group_id}` | `group` | Delete a group (the offices are not affected). |
| PUT | `/api/v1/groups/{group_id}/members` | `group-members` | Replace a group's members: `{"office_ids": [...]}`. |

## Audit log

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/audit-log` | `audit-log` | Audit log, newest first; filters `from`, `to`, `actor`, `action`, `office`, `entity_type`; paging with `before`. |
| GET | `/api/v1/audit-log/export.csv` | `audit-log-csv` | CSV of the filtered log. The download itself is audited as ``export``. |
| GET | `/api/v1/audit-log/{row_id}` | `audit-log-row` | One audit row with its before/after values. |

## Fiscal years and scoring

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/fiscal-years` | `fiscal-years` | Fiscal years, newest first. |
| POST | `/api/v1/fiscal-years` | `fiscal-years` | Create a fiscal year with its twelve months: `{"label", "start_year", "preset"}`. |
| GET | `/api/v1/fiscal-years/{fy_id}` | `fiscal-year` | One fiscal year with its months (cutoffs, locked or open) and scoring profile id. |
| PATCH | `/api/v1/fiscal-years/{fy_id}` | `fiscal-year` | Open or close a fiscal year: `{"status": "open" \| "closed"}`. |
| GET | `/api/v1/periods/{period_id}` | `period` | PATCH ``{"cutoff_at": ISO datetime}`` — move one month's cutoff (P7.2). Open months only. |
| PATCH | `/api/v1/periods/{period_id}` | `period` | PATCH ``{"cutoff_at": ISO datetime}`` — move one month's cutoff (P7.2). Open months only. |
| GET | `/api/v1/scoring-presets` | `scoring-presets` | The built-in scoring presets and what each means. |
| GET | `/api/v1/scoring-profiles/{profile_id}` | `scoring-profile` | A fiscal year's scoring settings. |
| PATCH | `/api/v1/scoring-profiles/{profile_id}` | `scoring-profile` | Change scoring settings (`preset`, `weighting`, `cap_at_100`, `on_time_tolerance`, labels, `rollup`, `cutoff_day`, …). After a month is locked, needs `{"confirm": true}`; locked months keep their results. |
| POST | `/api/v1/periods/{period_id}/lock` | `period-lock` | POST — lock a month: freeze every office's results (P7.3). Agency administrator. |
| POST | `/api/v1/periods/{period_id}/unlock` | `period-unlock` | POST ``{"reason"}`` — unlock the latest locked month (P7.4). Agency administrator. |

## Plans

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/plans` | `plans` | GET plans in scope (filters: fiscal_year, office, status); POST create a draft. |
| POST | `/api/v1/plans` | `plans` | GET plans in scope (filters: fiscal_year, office, status); POST create a draft. |
| GET | `/api/v1/plans/{plan_id}` | `plan` | One plan version: rows (outline and activities with monthly targets), indicators, validation messages. |
| PATCH | `/api/v1/plans/{plan_id}` | `plan` | Approved budget (agency administrator) — allowed in any status (P5.8). |
| POST | `/api/v1/plans/{plan_id}/save` | `plan-save` | Bulk save from the grid: all changed rows and indicators in one request. |
| POST | `/api/v1/plans/{plan_id}/submit` | `plan-submit` | Submit a draft for approval (refused with the list of problems if it does not validate). |
| POST | `/api/v1/plans/{plan_id}/approve` | `plan-approve` | Approve a submitted plan (agency administrator); it becomes the baseline and supersedes the previous version. |
| POST | `/api/v1/plans/{plan_id}/return` | `plan-return` | Return a submitted plan to its office: `{"note"}`. |
| POST | `/api/v1/plans/{plan_id}/revise` | `plan-revise` | Start a revision of the approved plan (a new draft version). |
| GET | `/api/v1/plans/{plan_id}/versions` | `plan-versions` | Every version of a plan with who submitted and approved it. |
| GET | `/api/v1/plans/{plan_id}/compare` | `plan-compare` | Compare this version with another version of the same office's plan (``?with=<plan id>``). |
| POST | `/api/v1/plans/{plan_id}/copy` | `plan-copy` | Copy a plan into another fiscal year as a draft — targets kept, actuals not (P5.9). |

## Results

| Method | Path | Name | What it does |
|---|---|---|---|
| POST | `/api/v1/results/preview` | `results-preview` | POST ``{"fiscal_year_id", "activities": [{key, measure_type, annual_target, total_cost, manual_weight, targets[12]}]}`` → weights per key, cumulative planned curve, funds total. Read-only: it stores nothing (allow-listed in the audit coverage test, D29). |
| GET | `/api/v1/dashboard` | `dashboard` | Dashboard of one office for one month: `?office&period[&view=implementing]` → figures, curves, quarters, children, rankings, FINAL or PROVISIONAL. |
| GET | `/api/v1/dashboard/activities` | `dashboard-activities` | GET ``?office&period[&view]`` — the activity list behind an office's figures (P8.3). |
| GET | `/api/v1/rankings` | `rankings` | GET ``?period[&set=children:<office id>\|group:<group id>]`` — one ranking set with each office's rank change against the previous month, plus the sets the user can choose from (P8.4). |
| GET | `/api/v1/dashboard/activity` | `dashboard-activity` | GET ``?lineage&period`` — one activity month by month with its files (P8.3). |

## Monthly reporting

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/reports` | `reports` | Monthly report of one office: `?office&period[&view]` → activities with targets and accomplishments, indicators, submission status, live result. |
| POST | `/api/v1/reports/save` | `reports-save` | Save accomplishments: `{"office", "period", "activities": [{"lineage_id", "actual", "amount", "remarks", "delay_reason"}], "indicators": [...]}`. |
| POST | `/api/v1/reports/preview` | `reports-preview` | Live result for numbers typed but not saved yet (P6.5). Read-only (D29-style allow-list). |
| POST | `/api/v1/reports/submit` | `reports-submit` | Submit an office's month: `{"office", "period"}` (refused while delay reasons or required files are missing). |
| GET | `/api/v1/submission-board` | `submission-board` | GET ``?period=`` — every office with an approved plan × its submission status (P7.6). |
| POST | `/api/v1/reports/return` | `reports-return` | Return a submitted month to its office: `{"office", "period", "note"}` (agency administrator). |
| GET | `/api/v1/attachments` | `attachments` | GET ?target_type&lineage_id&period_id — files of one actual. POST multipart — upload one file. |
| POST | `/api/v1/attachments` | `attachments` | GET ?target_type&lineage_id&period_id — files of one actual. POST multipart — upload one file. |
| DELETE | `/api/v1/attachments/{attachment_id}` | `attachment` | Remove a supporting file (kept in storage for the audit trail). |
| GET | `/api/v1/attachments/{attachment_id}/download` | `attachment-download` | Download a supporting file (audited). |

## Exports and imports

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/jobs` | `jobs` | GET — the signed-in user's exports and imports, newest first ("My exports"). |
| GET | `/api/v1/jobs/{job_id}` | `job` | One export or import job: status, result summary, `download_url` when done. |
| GET | `/api/v1/jobs/{job_id}/download` | `job-download` | Download a finished job's file (audited). |
| POST | `/api/v1/exports/xlsx` | `export-xlsx` | POST {scope: office\|subtree\|agency, office_id, period_id, view: owner\|implementing}. |
| POST | `/api/v1/exports/pptx` | `export-pptx` | POST {scope, office_id, period_id, view, groups: [overall\|offices\|rankings\|indicators]}, or {…, style: "year", title} for the year's over-all performance deck. |
| GET | `/api/v1/imports/plan-template` | `import-plan-template` | GET ?fiscal_year_id[&office_id] — the import template: the office sheet with headers only. |
| POST | `/api/v1/imports/plan` | `import-plan` | POST multipart {file, office_id, fiscal_year_id} — queue the import of a draft plan. |
| GET | `/api/v1/export-templates/{kind}` | `export-template` | GET the effective settings; PATCH some of them; DELETE to go back to the system default. |
| PATCH | `/api/v1/export-templates/{kind}` | `export-template` | GET the effective settings; PATCH some of them; DELETE to go back to the system default. |
| DELETE | `/api/v1/export-templates/{kind}` | `export-template` | GET the effective settings; PATCH some of them; DELETE to go back to the system default. |
| GET | `/api/v1/export-templates/{kind}/logo` | `export-template-logo` | GET the logo; POST multipart ``file`` to replace it; DELETE to remove it. |
| POST | `/api/v1/export-templates/{kind}/logo` | `export-template-logo` | GET the logo; POST multipart ``file`` to replace it; DELETE to remove it. |
| DELETE | `/api/v1/export-templates/{kind}/logo` | `export-template-logo` | GET the logo; POST multipart ``file`` to replace it; DELETE to remove it. |

## Alerts

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/alert-rules` | `alert-rules` | GET / PATCH ``{remind_days_before: [5, 1], delay_threshold: "0.05", email_enabled}``. |
| PATCH | `/api/v1/alert-rules` | `alert-rules` | GET / PATCH ``{remind_days_before: [5, 1], delay_threshold: "0.05", email_enabled}``. |
| GET | `/api/v1/notifications` | `notifications` | GET ``?unread=1&limit=50`` — the signed-in user's notifications, newest first. |
| GET | `/api/v1/notifications/unread-count` | `notifications-unread` | Number of unread notifications (send `X-Background: 1` when polling). |
| POST | `/api/v1/notifications/read-all` | `notifications-read-all` | Mark all your notifications read. |
| POST | `/api/v1/notifications/{notification_id}/read` | `notification-read` | POST — mark one notification read (not audited: it changes only the reader's own inbox). |

## Service

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/health` | `health` | Liveness and readiness: database, storage, worker heartbeat, deployment mode. No sign-in. |

## Other

| Method | Path | Name | What it does |
|---|---|---|---|
| GET | `/api/v1/progress` | `progress` | GET ``?fiscal_year=&period=`` — the six guided steps, which are done, and the per-office checklist of plans and of the chosen month (agency administrator). |

## Platform owners (multi-agency mode only)

| Method | Path | Name | What it does |
|---|---|---|---|
| POST | `/platform/api/auth/login` | `platform-login` | Platform-owner sign-in (separate cookie, vendor staff). |
| POST | `/platform/api/auth/logout` | `platform-logout` | Platform-owner sign-out. |
| GET | `/platform/api/me` | `platform-me` | The signed-in platform owner. |
| GET | `/platform/api/agencies` | `platform-agencies` | All agencies on the service. |
| POST | `/platform/api/agencies` | `platform-agencies` | Create an agency: `{"name", "code", "fiscal_year_start_month", "root_level_name"}`. |
| GET | `/platform/api/agencies/{agency_id}` | `platform-agency` | One agency. |
| PATCH | `/platform/api/agencies/{agency_id}` | `platform-agency` | Suspend or reactivate an agency: `{"status"}`. |
| POST | `/platform/api/agencies/{agency_id}/admins` | `platform-agency-admins` | Create an agency administrator. Returns a one-time temporary password. |
| GET | `/platform/api/agencies/{agency_id}/support` | `platform-agency-support` | Read-only look into an agency's data — only while a support grant is active (P1.7). |
