#!/usr/bin/env bash
# Builds one archive that installs GovMonitor on a machine with no internet (P13.4, D13):
#   deploy/make-offline-bundle.sh [version]     → dist/govmonitor-offline-<version>.tar.gz
# Inside: the images (application, PostgreSQL, Caddy), the compose file without build steps, the
# Caddyfile, scripts (install, update, backup, restore) and the admin guide.
# The application image must exist (make build, or GOVMONITOR_VERSION=<version> make build).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=${1:-${GOVMONITOR_VERSION:-$(cat VERSION 2>/dev/null || echo dev)}}
APP_IMAGE="govmonitor:$VERSION"
THIRD_PARTY_IMAGES=$(grep -E '^\s+image: (postgres|caddy):' deploy/docker-compose.yml | awk '{print $2}' | sort -u)
OUT=${OUT:-dist}
name="govmonitor-offline-$VERSION"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
stage="$work/$name"
mkdir -p "$stage/db" "$stage/certs" "$stage/licence" "$stage/backups" "$OUT"

docker image inspect "$APP_IMAGE" >/dev/null 2>&1 || { echo "build $APP_IMAGE first (make build)" >&2; exit 1; }
for img in $THIRD_PARTY_IMAGES; do
  docker image inspect "$img" >/dev/null 2>&1 || docker pull -q "$img"
done
echo "bundle: saving images ($APP_IMAGE $THIRD_PARTY_IMAGES)"
# shellcheck disable=SC2086
docker save "$APP_IMAGE" $THIRD_PARTY_IMAGES | gzip -1 > "$stage/images.tar.gz"

# The compose file runs prebuilt images only: drop the build section.
awk '
  /^    build:/ { skip = 1; next }
  skip && /^      / { next }
  { skip = 0; print }
' deploy/docker-compose.yml > "$stage/docker-compose.yml"
cp deploy/Caddyfile "$stage/"
cp deploy/db/init-roles.sh "$stage/db/"
cp deploy/.env.example "$stage/.env.example"
cp deploy/offline/install.sh deploy/offline/update.sh "$stage/"
# backup/restore run from the install folder (its compose file sits next to them).
sed 's#cd "$(dirname "$0")/.."#cd "$(dirname "$0")"#; s#-f deploy/docker-compose.yml#-f docker-compose.yml#; s#deploy/.env#.env#' \
  deploy/backup.sh > "$stage/backup.sh"
sed 's#cd "$(dirname "$0")/.."#cd "$(dirname "$0")"#; s#-f deploy/docker-compose.yml#-f docker-compose.yml#; s#deploy/.env#.env#; s#deploy/restore.sh#./restore.sh#' \
  deploy/restore.sh > "$stage/restore.sh"
chmod +x "$stage"/*.sh
[ -f docs/ADMIN_GUIDE.md ] && cp docs/ADMIN_GUIDE.md "$stage/"
echo "$VERSION" > "$stage/VERSION"
( cd "$stage" && sha256sum images.tar.gz > SHA256SUMS )

tar -C "$work" -czf "$OUT/$name.tar.gz" "$name"
echo "bundle: $OUT/$name.tar.gz ($(du -h "$OUT/$name.tar.gz" | cut -f1))"
