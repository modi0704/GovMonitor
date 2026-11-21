#!/usr/bin/env bash
# P13.7: a single-agency install from the offline bundle, then the containers are cut off from the
# internet (firewall: no traffic from the Docker networks to anything outside them), and a browser
# signs in, opens every page and exports Excel and PowerPoint — failing on any request that leaves
# the site. Needs root (iptables), the image (make build), Playwright and its Chromium.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${GOVMONITOR_VERSION:-dev}
work=$(mktemp -d)
target="$work/install"
RULES=()
cleanup() {
  for r in "${RULES[@]}"; do sudo iptables -D DOCKER-USER $r 2>/dev/null || true; done
  [ -f "$target/.env" ] && (cd "$target" && docker compose --env-file .env down -v >/dev/null 2>&1) || true
  rm -rf "$work"
}
trap cleanup EXIT

OUT="$work/dist" deploy/make-offline-bundle.sh "$BASE" >/dev/null
tar -C "$work" -xzf "$work/dist/govmonitor-offline-$BASE.tar.gz"
bundle="$work/govmonitor-offline-$BASE"
"$bundle/install.sh" "$target" >/dev/null

# A licence signed with a throwaway key that only this test install is told to trust. (The shipped
# compose file does not pass LICENCE_PUBLIC_KEY on purpose: operators cannot swap the vendor key.)
signed=$(docker run --rm -i -v "$PWD/tools:/tools:ro" --entrypoint python "govmonitor:$BASE" - <<'PY'
import base64, importlib.util, json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
spec = importlib.util.spec_from_file_location("t", "/tools/licence.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
k = Ed25519PrivateKey.generate()
raw = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
doc = t.sign_payload(base64.b64encode(raw).decode(), {"agency": "Sample Ministry", "expires": "2099-12-31", "seats": 100})
pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
print(base64.b64encode(pub).decode())
print(json.dumps(doc))
PY
)
keys=$(echo "$signed" | sed -n 1p)
echo "$signed" | sed -n 2p > "$target/licence/licence.json"
cat >> "$target/.env" <<ENV
LICENCE_PUBLIC_KEY=$keys
ENV
grep -q LICENCE_PUBLIC_KEY "$target/docker-compose.yml" || \
  sed -i 's#^  LICENCE_FILE: \${LICENCE_FILE:-}#  LICENCE_FILE: ${LICENCE_FILE:-}\n  LICENCE_PUBLIC_KEY: ${LICENCE_PUBLIC_KEY:-}#' "$target/docker-compose.yml"
(cd "$target" && docker compose --env-file .env up -d >/dev/null)

# Cut every container off from the internet (traffic between containers and replies to the host
# still flow).
DROP="-s 172.16.0.0/12 ! -d 172.16.0.0/12 -j DROP"
KEEP="-m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT"
sudo iptables -I DOCKER-USER 1 $DROP && RULES+=("$DROP")
sudo iptables -I DOCKER-USER 1 $KEEP && RULES+=("$KEEP")

cd "$target"
for _ in $(seq 1 90); do curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1 && break; sleep 2; done
if docker compose --env-file .env exec -T web python -c \
  "import urllib.request; urllib.request.urlopen('https://pypi.org', timeout=5)" >/dev/null 2>&1; then
  echo "the containers can still reach the internet" >&2; exit 1
fi
echo "offline: containers cannot reach the internet"
docker compose --env-file .env exec -T -e DJANGO_SETTINGS_MODULE=config.settings.dev web entrypoint.sh manage seed_demo >/dev/null
lic=$(curl -fsS http://localhost:8000/api/v1/health)
echo "offline: $lic"
cd - >/dev/null
cd frontend && OFFLINE_CHECK=1 SMOKE_BASE_URL=https://localhost npx playwright test e2e/offline.spec.ts --project desktop --trace off
echo "offline install: ok"
