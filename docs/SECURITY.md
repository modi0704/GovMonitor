# GovMonitor — Security review

Review of version 1 against MASTERPLAN P14.1, 2026-11-15. Each control names where it is
implemented and the test that proves it; findings fixed during the review are listed at the end.
Report vulnerabilities to the vendor's security contact; do not open public issues for them.

## 1. What we protect and from whom

* **Assets:** agencies' plans, monthly accomplishments, supporting files (photos, scans), results
  and the audit log; user accounts.
* **Threats considered:** another agency's users (cloud service), users reaching beyond their
  office scope, outsiders guessing passwords, cross-site request forgery, malicious uploads,
  tampered licences, insiders rewriting history.
* **Out of scope for version 1:** virus scanning of uploads (hook provided), single sign-on,
  hardware security modules.

## 2. Authentication

| Control | Where | Proof |
|---|---|---|
| Passwords: PBKDF2 (Django default), at least 12 characters, common/numeric/similar-to-name refused | `config/settings/base.py` `AUTH_PASSWORD_VALIDATORS` | `apps/accounts/tests` |
| Account lock: 5 wrong passwords lock the account for 15 minutes; messages never reveal whether an email exists (constant-time dummy hash for unknown emails) | `apps/accounts/services.py` `check_credentials` | `test_auth_api.py` |
| Per-address limit: 20 failed sign-ins from one address in 15 minutes → HTTP 429 (agency and platform sign-in), counted from the audit log so all web processes agree | `apps/accounts/ratelimit.py` | `test_ratelimit.py` |
| Temporary passwords (new users, admin resets) must be changed at first sign-in | `must_change_password` | `test_auth_api.py` |
| Optional two-step sign-in (TOTP); recovery codes stored hashed and single use | `apps/accounts/api_2fa.py`, `twofactor.py` | `test_2fa.py` |
| Password reset by email: signed, expiring token; silent on unknown emails; nothing sent without SMTP | `request_password_reset_email` | `test_auth_api.py` |
| Platform owners (vendor staff) are a separate table, separate sign-in and separate cookie (`gm_platform`, path `/platform/`), refused entirely in single-agency mode | `apps/tenancy/platform_api.py` | `test_platform.py` |

## 3. Sessions and CSRF

* Session cookie `gm_session`: HttpOnly, SameSite=Lax, Secure when served over HTTPS
  (`SECURE_SSL=1`, the default behind Caddy); the session key is replaced at sign-in.
* Idle sign-out after `SESSION_IDLE_MINUTES` (60); absolute maximum 12 hours. Only real API use
  counts as activity — background polls (`X-Background: 1`, the notification bell) and page loads do
  not, so an unattended open tab still signs out (fixed in this review, see §11).
* CSRF: every unsafe API request must carry `X-CSRFToken` matching the `gm_csrftoken` cookie
  (DRF SessionAuthentication; sign-in endpoints enforce it explicitly); `CSRF_TRUSTED_ORIGINS`
  lists the site's own addresses.
* HSTS (one year) only when served over TLS, so an office install on plain HTTP is never bricked.

## 4. Isolation between agencies (multi-agency service)

* Every tenant table carries `agency_id`; PostgreSQL row-level security is **enabled and
  forced**, policy `agency_id = NULLIF(current_setting('app.agency_id', true), '')::uuid`. The web
  and worker processes connect as `app_user`, which owns nothing and cannot bypass RLS; each request
  runs in one transaction with `SET LOCAL app.agency_id` (`apps/tenancy/middleware.py`).
* With no agency set, no agency row is visible (only system-wide defaults such as the default
  export template, readable and never writable).
* **Foreign keys cannot cross agencies (new in this review):** foreign-key checks bypass RLS, so
  every key between two tenant tables is also a composite `(agency_id, column) → (agency_id, id)`
  constraint, added after every migration (`apps/tenancy/db.py`, 39 constraints today).
* Proof (`tests/test_isolation.py`): every model is isolated or allow-listed; agency A reads no
  row of B; writing B's id fails; no agency sees nothing; system rows are read-only; every
  tenant-to-tenant key has its same-agency constraint; even the owner role cannot file a row under
  another agency's office. P14.2 calls every API route as agency A with agency B's ids.

## 5. Permissions inside an agency

* Each user's scope is the set of offices beneath their assignments (materialized paths). Every
  office-bound endpoint filters by scope (`filter_by_scope`, `get_office_or_404`); ids outside the
  scope answer **404**, never revealing existence. Read-only users get 403 on writes.
* Agency-wide settings (structure, users, fiscal years, scoring, approvals, locking, audit log,
  alert rules, report template) need an admin assignment at the root office (`IsAgencyAdmin`).
* Proof: `tests/test_scope_enforcement.py`, per-feature API tests, and the route-walking audit test.

## 6. Audit trail

* Every state-changing request writes at least one audit row (enforced by
  `tests/test_audit_coverage.py`, which walks every route); only sign-out and marking one's own
  notifications read are exempt.
* `audit_log` is append-only for `app_user` (UPDATE, DELETE and TRUNCATE revoked); rows record
  actor, IP (from `X-Forwarded-For` only behind the trusted proxy), user agent and request id.
* Password hashes, TOTP secrets and recovery codes are never copied into audit rows
  (`is_sensitive`).

## 7. Uploads and downloads

* Allowed: PDF, JPG, PNG, DOCX, XLSX, PPTX; the extension **and** the sniffed content (magic bytes,
  OOXML structure) must agree; size limit `MAX_UPLOAD_MB` in the application and `MAX_BODY_MB` at
  the proxy (Caddy answers 413 before Django reads the body).
* Stored under random keys (`<agency>/mov/<year>/<uuid>-<safe name>`), never served directly:
  downloads go through endpoints that check scope, send `Content-Disposition: attachment`,
  `X-Content-Type-Options: nosniff` and `Cache-Control: private, no-store`, and are audited.
* Plan imports accept XLSX only (same checks) and run in the worker inside a transaction; any
  problem rolls everything back.
* `apps/exports/hooks.scan_upload` is the place for an antivirus scanner.

## 8. Rate limits and abuse

* Sign-in: per account (lock) and per address (§2).
* Exports and imports: at most 3 waiting per user and 30 per hour (HTTP 429); the worker runs jobs
  one at a time per process, so a user cannot starve the queue.
* Request size: proxy limit; JSON bodies limited by Django (`DATA_UPLOAD_MAX_MEMORY_SIZE` 10 MB).

## 9. Browser hardening

Every response carries a content security policy with **no outside origin**
(`default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'` …,
`config/security.py`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
`X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy: same-origin` and a permissions policy that
allows the camera for this site only. The browser smoke tests fail on any CSP violation, and the
offline-install test fails on any request leaving the site.

## 10. Secrets and configuration

* All secrets come from the environment (`.env`, mode 600, generated by `install.sh`); production
  refuses to start with the development `SECRET_KEY` or without database URLs.
* Two database roles: `app_owner` (migrations, platform operations) and `app_user` (everything
  else); app containers never get the PostgreSQL superuser password.
* Licence files are signed with Ed25519; only the public key ships. The private key stays offline
  with the vendor (`tools/licence.py`). The repository holds a **placeholder** public key that must
  be replaced before a release (D41, release checklist).
* Logs are JSON lines without passwords, tokens or session keys.

## 11. Findings fixed during this review

| Finding | Fix |
|---|---|
| Foreign keys between tenant tables were only protected by application code (RLS does not apply to FK checks) | Composite same-agency constraints on all 39 keys, added automatically after every migration; tests |
| No limit on sign-in attempts per address (only per account) | Per-address limit, agency and platform sign-in |
| No limit on export/import requests | Per-user limits on waiting and hourly jobs |
| Background polls refreshed the idle timer, so an open tab never signed out; a page load racing a sign-out returned a server error | Only real API use refreshes the timer; page loads never write the session (found in P12.7) |
| No content security policy | Strict CSP and permissions policy (P13.1) |

## 12. Dependency audit

Run with `make audit` (also in CI). Result on 2026-11-15:

* `pip-audit` on `backend/requirements.txt` and `requirements-dev.txt`: **no known vulnerabilities**.
* `npm audit --omit=dev` (everything shipped in the browser bundle): **0 vulnerabilities**.
* `npm audit` including build tools: one moderate advisory (GHSA-g3hv-75wg-m249, ReDoS in
  `minimatch` used by `typescript-eslint`). **Accepted:** lint-time only, never shipped, processes
  only this repository's files; no fixed `typescript-eslint` release exists yet — recheck at release.

## 13. Accepted risks

| Risk | Why accepted |
|---|---|
| `style-src 'unsafe-inline'` | React and the chart library set style attributes; scripts remain strict, and no user HTML is ever rendered. |
| No antivirus scanning in version 1 | Out of scope (MASTERPLAN 1.3); hook ready; files are never executed or served inline. |
| Office installs: the customer controls the server and could edit the code to bypass the licence | Licensing is commercial, not a security boundary; data protection is unaffected. |
| `psycopg` is LGPL | Licence matter, not security (D20). |
