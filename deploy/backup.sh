#!/usr/bin/env bash
# Backup of a single-machine install (P13.3): the database (pg_dump, custom format) and the file
# store (supporting files, exports, logos) in one dated archive, keeping the newest $KEEP.
#   deploy/backup.sh                      # writes backups/govmonitor-YYYYmmdd-HHMMSS.tar
#   BACKUP_DIR=/mnt/nas/govmonitor KEEP=30 deploy/backup.sh
# Runs while the system is in use (pg_dump is consistent; files are only ever added).
# Restore with deploy/restore.sh <archive>.
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP_DIR=${BACKUP_DIR:-backups}
KEEP=${KEEP:-14}
ENV_FILE=${ENV_FILE:-deploy/.env}
COMPOSE=${COMPOSE:-docker compose -f deploy/docker-compose.yml $([ -f "$ENV_FILE" ] && echo "--env-file $ENV_FILE")}

stamp=$(date -u +%Y%m%d-%H%M%S)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$BACKUP_DIR"

echo "backup: database"
$COMPOSE exec -T db pg_dump -U postgres -d govmonitor --format=custom > "$work/db.dump"
echo "backup: files"
$COMPOSE exec -T web tar -C /data/files -czf - . > "$work/files.tar.gz"
version=$($COMPOSE exec -T web sh -c 'cat /app/VERSION 2>/dev/null || echo unknown' | tr -d '\r')
cat > "$work/manifest.json" <<JSON
{"created_utc": "$stamp", "app_version": "$version",
 "db_sha256": "$(sha256sum "$work/db.dump" | cut -d' ' -f1)",
 "files_sha256": "$(sha256sum "$work/files.tar.gz" | cut -d' ' -f1)"}
JSON
archive="$BACKUP_DIR/govmonitor-$stamp.tar"
tar -C "$work" -cf "$archive" manifest.json db.dump files.tar.gz
echo "backup: wrote $archive ($(du -h "$archive" | cut -f1))"

# Retention: keep the newest $KEEP archives.
mapfile -t old < <(ls -1t "$BACKUP_DIR"/govmonitor-*.tar 2>/dev/null | tail -n +"$((KEEP + 1))")
for f in "${old[@]}"; do rm -f "$f" && echo "backup: removed old $f"; done
