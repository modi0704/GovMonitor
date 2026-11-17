# GovMonitor — Performance Monitoring Web Application

A multi-agency web application for monitoring and evaluating the performance of government offices
against their annual work and financial plans. It replaces a manual Excel workflow.

**Start with [`MASTERPLAN.md`](MASTERPLAN.md).** It is the single source of truth for the build:
decisions, data model, the scoring method, test vectors and the phase-by-phase task list with the
current status.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Django project (`config/`) and apps (`apps/`), with separate development fixtures |
| `frontend/` | React + TypeScript single-page app (Vite) |
| `deploy/` | Dockerfile, Compose files, database init, backup/restore scripts |
| `docs/` | Third-party licences, admin and user guides, security notes, API |
| `tools/` | Fixture extraction, vendor licence tool, API reference generator |
| `reference/` | The customer's original workbooks — git-ignored, read-only |

## Running locally

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

## Documentation

* [Administrator guide](docs/ADMIN_GUIDE.md) — install (Linux, Windows Server, cloud), certificates,
  email, backups, updates, licence, troubleshooting.
* [User guide](docs/USER_GUIDE.md) — by role, with screenshots.
  [Printable PDF](docs/user-guide/USER_GUIDE.pdf).
  The full searchable guide is also inside the app at **User guide**; PDF downloads work without internet while the local app is running.
* [Practice input](docs/SAMPLE_INPUT.txt), [entry and metrics](docs/INPUT_AND_METRICS.txt), and
  [Windows start/stop commands](docs/RUN_AND_CLOSE.txt).
* [API reference](docs/API.md) · [Security review](docs/SECURITY.md) ·
  [Release checklist](docs/RELEASE.md) · [Changelog](CHANGELOG.md) ·
  [Third-party licences](docs/THIRD_PARTY.md)

Configuration is by environment variables (see `MASTERPLAN.md` section 5.4 and
`deploy/.env.example`).
