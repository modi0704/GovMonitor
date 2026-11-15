# GovMonitor — Performance Monitoring Web Application

A multi-agency web application for monitoring and evaluating the performance of government offices
against their annual work and financial plans. It replaces a manual Excel workflow.

**Start with [`MASTERPLAN.md`](MASTERPLAN.md).** It is the single source of truth for the build:
decisions, data model, the scoring method, test vectors and the phase-by-phase task list with the
current status.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Django project (`config/`) and apps (`apps/`), fixtures and the demo seed |
| `frontend/` | React + TypeScript single-page app (Vite) |
| `deploy/` | Dockerfile, Compose files, database init, backup/restore scripts |
| `docs/` | Third-party licences, admin and user guides, security notes, API |
| `tools/` | One-off scripts (fixture extraction) |
| `reference/` | The customer's original workbooks — git-ignored, read-only |

## Running locally

Requirements: Docker with Compose, GNU Make. For development without Docker: Python 3.13,
Node 22, PostgreSQL 16 or later.

```bash
make up          # build and start db, web and worker
make migrate     # apply migrations
make seed-demo   # load demo data
make check       # lint + backend tests + frontend tests + build
make down        # stop everything
```

The app is then served at <http://localhost:8000/>, and `GET /api/v1/health` reports database,
storage and worker status.

Configuration is by environment variables (see `MASTERPLAN.md` section 5.4 and
`deploy/.env.example`).
