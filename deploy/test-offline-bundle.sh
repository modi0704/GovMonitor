#!/usr/bin/env bash
# P13.4 check: bundle → install into an empty folder → update to a second version → update to a
# broken version, which must roll back automatically to the previous version with its data.
# Needs the image govmonitor:${GOVMONITOR_VERSION:-dev}. Uses ports 80/443/8000 and cleans up.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${GOVMONITOR_VERSION:-dev}
work=$(mktemp -d)
target="$work/install"
cleanup() {
  [ -f "$target/.env" ] && (cd "$target" && docker compose --env-file .env down -v >/dev/null 2>&1) || true
  docker rmi govmonitor:bundle-v2 govmonitor:bundle-broken >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

bundle() {  # version → unpacked bundle folder
  OUT="$work/dist" deploy/make-offline-bundle.sh "$1" >/dev/null
  mkdir -p "$work/unpack-$1"
  tar -C "$work/unpack-$1" -xzf "$work/dist/govmonitor-offline-$1.tar.gz"
  echo "$work/unpack-$1/govmonitor-offline-$1"
}
agencies() {
  (cd "$target" && docker compose --env-file .env exec -T web entrypoint.sh manage shell -c \
    "from apps.tenancy.models import Agency; print(Agency.objects.using('owner').count())" | tail -1)
}
version() { sed -n 's/^GOVMONITOR_VERSION=//p' "$target/.env"; }

"$(bundle "$BASE")/install.sh" "$target"
(cd "$target" && docker compose --env-file .env exec -T web entrypoint.sh manage bootstrap_single_agency \
  --name "Bundle Test" --code bundle-test --admin-email chief@bundle.test >/dev/null)
[ "$(agencies)" = "1" ]

docker tag "govmonitor:$BASE" govmonitor:bundle-v2
"$(bundle bundle-v2)/update.sh" "$target"
[ "$(version)" = "bundle-v2" ] && [ "$(agencies)" = "1" ] || { echo "update did not keep the data" >&2; exit 1; }

broken=$(mktemp -d)
printf 'FROM govmonitor:%s\nENTRYPOINT ["sh", "-c", "echo broken release; exit 1"]\n' "$BASE" > "$broken/Dockerfile"
docker build -q -t govmonitor:bundle-broken "$broken" >/dev/null
rm -rf "$broken"
if HEALTH_TRIES=15 "$(bundle bundle-broken)/update.sh" "$target"; then
  echo "a broken release was accepted" >&2; exit 1
fi
[ "$(version)" = "bundle-v2" ] && [ "$(agencies)" = "1" ] || { echo "rollback failed" >&2; exit 1; }
echo "offline bundle: install, update and automatic rollback ok"
