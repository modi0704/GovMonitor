#!/usr/bin/env bash
# Update an installation from a newer offline bundle (P13.4). Run from the unpacked NEW bundle:
#   sudo ./update.sh [/opt/govmonitor]
# Steps: backup → load images → new compose files → start (migrations run on start) → health
# check; if anything fails, roll back automatically to the previous version and the backup.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
target=${1:-/opt/govmonitor}
new=$(cat "$here/VERSION")
cd "$target"
[ -f .env ] || { echo "update: no installation in $target (use install.sh)" >&2; exit 1; }
old=$(sed -n 's/^GOVMONITOR_VERSION=//p' .env)
port=$(sed -n 's/^WEB_PORT=//p' .env); port=${port:-8000}
echo "update: $old → $new"

healthy() {
  for _ in $(seq 1 "${HEALTH_TRIES:-90}"); do
    curl -fsS "http://localhost:$port/api/v1/health" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

echo "update: backup first"
BACKUP_DIR="$target/backups" ./backup.sh
backup=$(ls -1t "$target"/backups/govmonitor-*.tar | head -1)
saved=$(mktemp -d)
cp docker-compose.yml Caddyfile backup.sh restore.sh update.sh .env "$saved/"

rollback() {
  echo "update: FAILED — rolling back to $old" >&2
  cp "$saved"/{docker-compose.yml,Caddyfile,backup.sh,restore.sh,update.sh,.env} "$target/"
  ./restore.sh "$backup" --yes || true
  docker compose --env-file .env up -d
  if healthy; then
    echo "update: rolled back; $old is running again with the data from before the update" >&2
  else
    echo "update: rollback did not come up healthy — restore $backup by hand (ADMIN_GUIDE.md)" >&2
  fi
  exit 1
}
trap rollback ERR

( cd "$here" && sha256sum -c SHA256SUMS >/dev/null )
gunzip -c "$here/images.tar.gz" | docker load -q
for f in docker-compose.yml Caddyfile backup.sh restore.sh update.sh install.sh VERSION; do cp "$here/$f" "$target/"; done
cp "$here/db/init-roles.sh" "$target/db/"
[ -f "$here/ADMIN_GUIDE.md" ] && cp "$here/ADMIN_GUIDE.md" "$target/"
sed -i "s/^GOVMONITOR_VERSION=.*/GOVMONITOR_VERSION=$new/" .env
docker compose --env-file .env up -d
healthy || false
trap - ERR
echo "update: GovMonitor $new is running (backup kept: $backup)"
