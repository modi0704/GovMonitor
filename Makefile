# GovMonitor developer commands. Run `make help` for the list.
# Local (non-Docker) targets use backend/.venv when it exists and a local PostgreSQL 16+
# reachable through DATABASE_URL / DATABASE_ADMIN_URL (defaults: app_user / app_owner on localhost).

SHELL := /bin/bash
comma := ,
COMPOSE ?= docker compose -f deploy/docker-compose.yml
VERSION := $(shell cat VERSION 2>/dev/null || echo dev)
IMAGE ?= govmonitor:$(or $(GOVMONITOR_VERSION),dev)
PY := $(if $(wildcard backend/.venv/bin/python),$(CURDIR)/backend/.venv/bin/python,python3)
BACKEND_BIN := $(if $(wildcard backend/.venv/bin/python),$(CURDIR)/backend/.venv/bin/,)
# Optional: CA bundle of a TLS-inspecting proxy, passed to the image build as a secret.
EXTRA_CA_FILE ?=
BUILD_FLAGS := $(if $(EXTRA_CA_FILE),--secret id=extra_ca$(comma)src=$(EXTRA_CA_FILE),) $(DOCKER_BUILD_FLAGS)
WEB_PORT ?= 8000

.PHONY: help up down logs build migrate migrate-local test test-backend test-frontend lint \
        lint-backend lint-frontend build-frontend check seed-demo seed-demo-local install lock smoke offline-bundle audit release

help: ## List the targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-16s %s\n", $$1, $$2}'

# ---- Containers ------------------------------------------------------------------------------
build: ## Build the application image (web + worker)
	docker build $(BUILD_FLAGS) --build-arg VERSION=$(or $(GOVMONITOR_VERSION),$(VERSION)) -f deploy/Dockerfile -t $(IMAGE) .

up: build ## Build and start db, web and worker; wait for /api/v1/health
	$(COMPOSE) up -d --no-build
	@echo "Waiting for the web service to report healthy..."
	@for i in $$(seq 1 60); do \
	  if curl -fsS http://localhost:$(WEB_PORT)/api/v1/health >/dev/null 2>&1; then \
	    echo "up: http://localhost:$(WEB_PORT)/"; exit 0; fi; \
	  sleep 2; done; echo "web did not become healthy"; $(COMPOSE) logs --tail 50 web; exit 1

down: ## Stop the containers (data volumes are kept)
	$(COMPOSE) down

logs: ## Follow container logs
	$(COMPOSE) logs -f

migrate: ## Apply migrations inside the running stack (as app_owner)
	$(COMPOSE) exec web entrypoint.sh migrate

seed-demo: ## Development only: load training agencies under development settings
	$(COMPOSE) exec -e DJANGO_SETTINGS_MODULE=config.settings.dev web entrypoint.sh manage seed_demo

release: ## Release build (docs/RELEASE.md): image govmonitor:$(VERSION) and its offline bundle
	@grep -q PLACEHOLDER backend/apps/tenancy/licence_public_key.txt && \
	  { echo "release: replace the placeholder licence public key first (docs/RELEASE.md)"; exit 1; } || true
	$(MAKE) build GOVMONITOR_VERSION=$(VERSION) IMAGE=govmonitor:$(VERSION)
	deploy/make-offline-bundle.sh $(VERSION)

offline-bundle: ## Archive for installs without internet: images + compose + scripts (dist/)
	deploy/make-offline-bundle.sh $(or $(GOVMONITOR_VERSION),dev)

# ---- Local development -----------------------------------------------------------------------
install: ## Create backend/.venv and install backend + frontend dependencies
	cd backend && (test -d .venv || uv venv --python 3.13 .venv) && \
	  uv pip install --python .venv/bin/python --require-hashes -r requirements.txt -r requirements-dev.txt
	cd frontend && npm ci --no-audit --no-fund

lock: ## Re-resolve and hash-pin backend requirements
	cd backend && uv pip compile --quiet --generate-hashes --python-version 3.13 requirements.in -o requirements.txt \
	  && uv pip compile --quiet --generate-hashes --python-version 3.13 requirements-dev.in -o requirements-dev.txt

migrate-local: ## Apply migrations to the local database (as app_owner)
	cd backend && $(PY) manage.py migrate --database owner

seed-demo-local: ## Load the demo agencies into the local database
	cd backend && $(PY) manage.py seed_demo

# ---- Quality gates ---------------------------------------------------------------------------
lint-backend:
	cd backend && $(BACKEND_BIN)ruff check . && $(BACKEND_BIN)ruff format --check .

lint-frontend:
	cd frontend && npm run lint

lint: lint-backend lint-frontend ## Ruff, ESLint and Prettier

test-backend:
	cd backend && $(PY) -m pytest -m "not perf" --cov=apps.scoring.engine --cov-fail-under=95 --cov-report=term:skip-covered
	cd backend && $(PY) -m pytest -m perf  # timing tests, without coverage tracing (P8.8)

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend ## Backend (pytest) and frontend (Vitest) tests

build-frontend:
	cd frontend && npm run build

# Playwright smoke + accessibility tests (P12.5, P12.7) against a running server with the demo data,
# a worker and a platform owner (see .github/workflows/ci.yml, job "smoke"). SMOKE_BASE_URL sets it.
smoke: ## Browser smoke tests of the five user flows, desktop and phone
	cd frontend && SMOKE_BASE_URL=$(or $(SMOKE_BASE_URL),http://127.0.0.1:$(WEB_PORT)) npm run smoke

audit: ## Known-vulnerability audit of dependencies (runtime must be clean; docs/SECURITY.md)
	uvx --quiet pip-audit@2.9.0 --disable-pip --no-deps -r backend/requirements.txt -r backend/requirements-dev.txt
	cd frontend && npm audit --omit=dev

check: lint test build-frontend ## lint + backend tests + frontend tests + frontend build
	@echo "check: all green"
