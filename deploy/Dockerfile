# syntax=docker/dockerfile:1
# One image for web and worker (MASTERPLAN 5.1). Build from the repository root:
#   docker build -f deploy/Dockerfile -t govmonitor:dev .
# Behind a TLS-inspecting proxy, pass its CA bundle as an optional build secret (never stored in the
# image):  docker build --secret id=extra_ca,src=/path/to/ca.pem ...   (make build does this when
# EXTRA_CA_FILE is set).

# ---- Stage 1: build the React app -------------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; fi \
 && npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: install Python dependencies ----------------------------------------------------
FROM python:3.13-slim AS pydeps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY backend/requirements.txt /tmp/requirements.txt
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi \
 && python -m venv /opt/venv \
 && /opt/venv/bin/pip install --require-hashes -r /tmp/requirements.txt

# ---- Stage 3: runtime ------------------------------------------------------------------------
FROM python:3.13-slim AS runtime
ARG VERSION=dev
LABEL org.opencontainers.image.title="GovMonitor" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.description="Performance monitoring for government agencies"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    FRONTEND_DIST=/app/frontend/dist \
    FILE_ROOT=/data/files
# No apt packages: database dumps run inside the db container (deploy/backup.sh).
RUN groupadd --system app && useradd --system --gid app --home /app app \
 && mkdir -p /data/files && chown -R app:app /data
COPY --from=pydeps /opt/venv /opt/venv
WORKDIR /app/backend
COPY backend/ /app/backend/
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY VERSION /app/VERSION
RUN rm -rf /app/backend/.venv \
 && SECRET_KEY=build-only DATABASE_URL=postgres://x@localhost/x DATABASE_ADMIN_URL=postgres://x@localhost/x \
    python manage.py collectstatic --noinput \
 && chmod +x /usr/local/bin/entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["web"]
