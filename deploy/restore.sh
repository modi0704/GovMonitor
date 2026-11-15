#!/usr/bin/env bash
# Restore a backup made by deploy/backup.sh (P13.3) into a single-machine install — the same
# machine or a fresh one where `docker compose up -d` has run once. REPLACES all current data.
#   deploy/restore.sh backups/govmonitor-20260101-020000.tar [--yes]
set -euo pipefail
cd "$(dirname "$0")/.."
archive=${1:?usage: deploy/restore.sh <backup archive> [--yes]}
ENV_FILE=${ENV_FILE:-deploy/.env}
COMPOSE=${COMPOSE:-docker compose -f deploy/docker-compose.yml $([ -f "$ENV_FILE" ] && echo "--env-file $ENV_FILE")}
WEB_PORT=${WEB_PORT:-8000}

if [ "${2:-}" != "--yes" ]; then
  read -r -p "This replaces ALL current data with $archive. Type RESTORE to continue: " answer
  [ "$answer" = "RESTORE" ] || { echo "restore: cancelled"; exit 1; }
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
tar -C "$work" -xf "$archive"
for part in db files; do
  file=$([ "$part" = db ] && echo db.dump || echo files.tar.gz)
  want=$(sed -n "s/.*\"${part}_sha256\": \"\([0-9a-f]*\)\".*/\1/p" "$work/manifest.json")
  have=$(sha256sum "$work/$file" | cut -d' ' -f1)
  [ "$want" = "$have" ] || { echo "restore: $file is damaged (checksum mismatch)" >&2; exit 1; }
done

echo "restore: stopping web and worker"
$COMPOSE up -d db
$COMPOSE stop web worker caddy >/dev/null 2>&1 || true
for _ in $(seq 1 60); do $COMPOSE exec -T db pg_isready -U postgres -d postgres >/dev/null 2>&1 && break; sleep 1; done

echo "restore: database"
$COMPOSE exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "DROP DATABASE IF EXISTS govmonitor WITH (FORCE)" >/dev/null
$COMPOSE exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "CREATE DATABASE govmonitor OWNER app_owner" >/dev/null
$COMPOSE exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d govmonitor \
  -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO app_user;" >/dev/null
$COMPOSE exec -T db pg_restore -U postgres -d govmonitor --exit-on-error < "$work/db.dump"

echo "restore: files"
$COMPOSE run --rm --no-deps -T --entrypoint sh web -c 'find /data/files -mindepth 1 -delete && tar -xzf - -C /data/files' \
  < "$work/files.tar.gz"

echo "restore: starting"
$COMPOSE up -d
for _ in $(seq 1 60); do
  curl -fsS "http://localhost:$WEB_PORT/api/v1/health" >/dev/null 2>&1 && { echo "restore: done, healthy"; exit 0; }
  sleep 2
done
echo "restore: the web service did not become healthy" >&2
exit 1
