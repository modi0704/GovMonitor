# GovMonitor — Performance Monitoring Web Application

A web application for monitoring the performance of government offices against their annual work
and financial plans. It replaces the monitoring Excel workbook.

## How it works (for users)

One monitoring officer collects the figures from the offices they handle and types them in. The app
opens on **Step-by-step**, a progress bar with six steps:

1. **Add your offices** (once)
2. **Set up the year** (once a year)
3. **Enter each office's plan**: activities, monthly targets, costs, output targets (once a year)
4. **Enter the monthly results** of each office (every month)
5. **Check and close the month** (every month)
6. **Download the report**: the monthly Excel/PowerPoint report, or the **over-all performance
   presentation for the year** (based on activities and on output indicators, with rankings)

The app calculates everything else: plan versus actual, gap, status (ADVANCED / ON-TIME / DELAYED),
funds, S-curves and rankings. It can be set up for any agency's offices.

**Read the [User Guide](docs/USER_GUIDE.md)** ([PDF](docs/user-guide/USER_GUIDE.pdf)) — short and
step by step.

**Run it on your PC** (Docker Desktop open, in Git Bash inside this folder): `./run.sh start`, then
open <http://localhost:8000/>. `./run.sh stop` closes it, `./run.sh update` gets the newest
version, `./run.sh demo` loads practice data. Details: [docs/RUN_AND_CLOSE.txt](docs/RUN_AND_CLOSE.txt). To practise with invented figures, use
[docs/SAMPLE_INPUT.txt](docs/SAMPLE_INPUT.txt) and [docs/INPUT_AND_METRICS.txt](docs/INPUT_AND_METRICS.txt).

## For developers

Start with [`MASTERPLAN.md`](MASTERPLAN.md). It is the single source of truth for the build:
decisions, data model, the scoring method, test vectors and the phase-by-phase task list with the
current status.

### Repository layout

| Path | Contents |
|---|---|
| `backend/` | Django project (`config/`) and apps (`apps/`), with separate development fixtures |
| `frontend/` | React + TypeScript single-page app (Vite) |
| `deploy/` | Dockerfile, Compose files, database init, backup/restore scripts |
| `docs/` | Third-party licences, admin and user guides, security notes, API |
| `tools/` | Fixture extraction, vendor licence tool, API reference generator, user-guide PDF builder |
| `reference/` | The customer's original workbooks — git-ignored, read-only |

### Running locally

Requirements: Docker with Compose, GNU Make. For development without Docker: Python 3.13,
Node 22, PostgreSQL 16 or later.

```bash
make up          # build and start db, web, worker and Caddy
make migrate     # apply migrations
make check       # lint + backend tests + frontend tests + build
make smoke       # browser tests of the five user flows (needs a running server with demo data)
make audit       # known-vulnerability check of the dependencies
make down        # stop everything
```

The app is then served at <https://localhost/> (through Caddy, with its own certificate) and at
<http://localhost:8000/> from this machine; `GET /api/v1/health` reports database, storage, worker
and version. For a real workspace, run the interactive setup once:

```powershell
docker compose -f deploy/docker-compose.yml --env-file deploy/.env exec web entrypoint.sh manage initialize_workspace
```

Use your actual agency and administrator details. Setup creates a temporary password for first
sign-in and disables recognized built-in demo accounts. Training records are retained for recovery;
renamed agencies or agencies with other users are left untouched. No sample plans or reports are
created. The demo loader is available only under development/test settings.

### Documentation

* [Administrator guide](docs/ADMIN_GUIDE.md) — install (Linux, Windows Server, cloud), certificates,
  email, backups, updates, licence, troubleshooting.
* [User guide](docs/USER_GUIDE.md) — the six steps in plain words, with screenshots.
  [Printable PDF](docs/user-guide/USER_GUIDE.pdf).
  The same guide is inside the app under **User guide** (searchable, works without internet).
* [Practice figures](docs/SAMPLE_INPUT.txt), [how to type them in and the expected results](docs/INPUT_AND_METRICS.txt),
  and [Windows start / update / close commands](docs/RUN_AND_CLOSE.txt).
* [API reference](docs/API.md) · [Security review](docs/SECURITY.md) ·
  [Release checklist](docs/RELEASE.md) · [Changelog](CHANGELOG.md) ·
  [Third-party licences](docs/THIRD_PARTY.md)

Configuration is by environment variables (see `MASTERPLAN.md` section 5.4 and
`deploy/.env.example`).
