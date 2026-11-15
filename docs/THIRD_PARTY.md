# Third-party components and licences

Licence rule (MASTERPLAN section 5.2): every **runtime** dependency must be MIT, BSD, Apache-2.0,
PSF, ISC or PostgreSQL licensed. No GPL/AGPL and no "non-commercial" licences. Exceptions are
recorded in MASTERPLAN section 14 and listed under "Exceptions" below.

Checked 2026-11-15 against PyPI / npm metadata. Re-run this check whenever a lockfile changes
(`backend/requirements*.txt`, `frontend/package-lock.json`).

## Backend runtime (`backend/requirements.txt`)

| Package | Version | Licence | Why it is here |
|---|---|---|---|
| Django | 5.2.19 | BSD-3-Clause | Web framework (5.2 LTS) |
| djangorestframework | 3.18.3 | BSD-3-Clause | JSON API |
| asgiref | 3.13.0 | BSD-3-Clause | Django dependency |
| sqlparse | 0.6.1 | BSD-3-Clause | Django dependency |
| psycopg / psycopg-binary | 3.3.9 | **LGPL-3.0-only** | PostgreSQL driver — see Exceptions |
| dj-database-url | 3.1.2 | BSD-3-Clause | `DATABASE_URL` parsing |
| whitenoise | 6.12.0 | MIT | Static file serving |
| gunicorn | 27.0.1 | MIT | WSGI server |
| pyotp | 2.11.2 | MIT | TOTP two-factor codes (replaces django-otp, see D19) |
| qrcode | 8.2 | BSD | QR code for TOTP enrolment (SVG output, no Pillow needed) |
| XlsxWriter | 3.3.1 | BSD-2-Clause | Excel export |
| openpyxl | 3.1.5 | MIT | Excel import / fixture extraction |
| et-xmlfile | 2.0.0 | MIT | openpyxl dependency |
| python-pptx | 1.0.2 | MIT | PowerPoint export |
| lxml | 6.1.3 | BSD-3-Clause | python-pptx dependency |
| Pillow | 13.0.0 | MIT-CMU (HPND, permissive, MIT-style) | python-pptx dependency |
| typing-extensions | 4.16.0 | PSF-2.0 | python-pptx dependency |
| django-storages | 1.14.6 | BSD-3-Clause | S3-compatible file storage |
| boto3 / botocore | 1.44.3 | Apache-2.0 | S3 client |
| s3transfer | 0.19.3 | Apache-2.0 | boto3 dependency |
| jmespath | 1.1.0 | MIT | botocore dependency |
| python-dateutil | 2.9.0.post0 | BSD-3-Clause (dual Apache-2.0) | botocore dependency |
| six | 1.17.0 | MIT | python-dateutil dependency |
| urllib3 | 2.8.0 | MIT | botocore dependency |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Ed25519 licence signatures |
| cffi | 2.1.1 | MIT-0 | cryptography dependency |
| pycparser | 3.12 | BSD-3-Clause | cffi dependency |

## Backend development only (`backend/requirements-dev.txt`, not shipped in the image)

pytest 9.2.0 (MIT), pytest-django 4.14.0 (BSD-3-Clause), pytest-cov 7.1.0 (MIT), coverage 7.17.3
(Apache-2.0), ruff 0.17.5 (MIT), pluggy (MIT), iniconfig (MIT), packaging (Apache-2.0/BSD),
Pygments (BSD-2-Clause).

## Frontend runtime (bundled into `frontend/dist`)

| Package | Version | Licence |
|---|---|---|
| react, react-dom, scheduler | 19.3.1 | MIT |
| react-router-dom, react-router, cookie, set-cookie-parser | 7.18.5 | MIT |
| use-sync-external-store | — | MIT |
| echarts | 6.1.0 | Apache-2.0 |
| zrender | (echarts dependency) | BSD-3-Clause |
| tslib | (echarts dependency) | 0BSD |

## Frontend build and test tools (not shipped)

TypeScript 6.0.3 (Apache-2.0), Vite 8.3.8 (MIT), @vitejs/plugin-react 6.3.0 (MIT), Vitest 5.1.0
(MIT), jsdom 31.0.1 (MIT), Testing Library (MIT), ESLint 10.15.0 (MIT), typescript-eslint 8.72.2
(MIT), Prettier 3.10.1 (MIT), @playwright/test 1.63.0 (Apache-2.0), @types/node 22.20.5 (MIT), @axe-core/playwright and
axe-core 4.14.0 (MPL-2.0; accessibility checks in the Playwright tests only, never shipped — the
licence rule covers runtime dependencies).

Transitive build-only packages with other licences (never included in the bundle): lightningcss
(MPL-2.0, Vite's CSS minifier), minimatch / lru-cache (BlueOak-1.0.0, permissive), caniuse-lite
(CC-BY-4.0, browser data used at build time).

## Container images and services

| Component | Version | Licence |
|---|---|---|
| python:3.13-slim (Debian) base image | 3.13.18 | PSF-2.0 (Python); Debian packages under their own licences |
| PostgreSQL | 18.7 (image `postgres:18`); app minimum 16 | PostgreSQL License |
| Caddy | 2.11.9 (image `caddy:2`) | Apache-2.0 |
| Node.js (build stage only) | 22 | MIT |

## Exceptions

- **psycopg (LGPL-3.0-only).** Django supports only psycopg 3 and psycopg2 as PostgreSQL drivers,
  and both are LGPL. The library is used unmodified and loaded dynamically, which the LGPL permits
  in commercial, closed-source products. Customers may replace it (it is a separate, documented
  package in the image). Recorded as decision D20.
- **django-otp was replaced** by pyotp because django-otp is under the Unlicense, which is not on
  the allow-list (D19).
