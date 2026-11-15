#!/usr/bin/env bash
# First install from the offline bundle (P13.4). Run from the unpacked bundle folder:
#   sudo ./install.sh [/opt/govmonitor]
# Needs Docker with the compose plugin; no internet. Creates .env with generated secrets on first
# install, loads the images, starts everything and waits until it is healthy.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
target=${1:-/opt/govmonitor}
version=$(cat "$here/VERSION")
command -v docker >/dev/null || { echo "install: Docker is not installed" >&2; exit 1; }
docker compose version >/dev/null || { echo "install: the Docker compose plugin is missing" >&2; exit 1; }

( cd "$here" && sha256sum -c SHA256SUMS >/dev/null ) || { echo "install: images.tar.gz is damaged" >&2; exit 1; }
echo "install: loading images (a few minutes)"
gunzip -c "$here/images.tar.gz" | docker load -q

mkdir -p "$target"/{db,certs,licence,backups}
for f in docker-compose.yml Caddyfile backup.sh restore.sh update.sh install.sh VERSION; do
  [ "$here" = "$target" ] || cp "$here/$f" "$target/"
done
[ "$here" = "$target" ] || cp "$here/db/init-roles.sh" "$target/db/"
[ -f "$here/ADMIN_GUIDE.md" ] && [ "$here" != "$target" ] && cp "$here/ADMIN_GUIDE.md" "$target/"
[ "$here" = "$target" ] || cp "$here/.env.example" "$target/"

secret() { tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "${1:-40}"; }
if [ ! -f "$target/.env" ]; then
  sed -e "s/^SECRET_KEY=.*/SECRET_KEY=$(secret 60)/" \
      -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(secret)/" \
      -e "s/^APP_OWNER_PASSWORD=.*/APP_OWNER_PASSWORD=$(secret)/" \
      -e "s/^APP_USER_PASSWORD=.*/APP_USER_PASSWORD=$(secret)/" \
      "$target/.env.example" > "$target/.env"
  chmod 600 "$target/.env"
  echo "install: created $target/.env with new secrets — set SITE_ADDRESS, ALLOWED_HOSTS and"
  echo "         CSRF_TRUSTED_ORIGINS for this server (see ADMIN_GUIDE.md), then run install.sh again."
fi
if grep -q '^GOVMONITOR_VERSION=' "$target/.env"; then
  sed -i "s/^GOVMONITOR_VERSION=.*/GOVMONITOR_VERSION=$version/" "$target/.env"
else
  echo "GOVMONITOR_VERSION=$version" >> "$target/.env"
fi

cd "$target"
docker compose --env-file .env up -d
port=$(sed -n 's/^WEB_PORT=//p' .env); port=${port:-8000}
for _ in $(seq 1 90); do
  if curl -fsS "http://localhost:$port/api/v1/health" >/dev/null 2>&1; then
    echo "install: GovMonitor $version is running."
    echo "         Next: docker compose --env-file .env exec web entrypoint.sh manage bootstrap_single_agency"
    exit 0
  fi
  sleep 2
done
echo "install: the service did not become healthy; see: docker compose logs web" >&2
exit 1
