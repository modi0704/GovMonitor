#!/usr/bin/env bash
# Container entrypoint. Commands: web | worker | migrate | manage <args...>
set -euo pipefail
cd /app/backend

wait_for_db() {
  local err=""
  for _ in $(seq 1 60); do
    # The error text names the problem (wrong password, host not found …); it never contains a password.
    if err=$(python - 2>&1 <<'PY'
import os, sys, psycopg
try:
    psycopg.connect(os.environ["DATABASE_ADMIN_URL"], connect_timeout=2).close()
except Exception as exc:  # noqa: BLE001
    sys.exit(str(exc).strip().splitlines()[-1] if str(exc).strip() else type(exc).__name__)
PY
    ); then return 0; fi
    sleep 1
  done
  echo "entrypoint: database not reachable: ${err}" >&2
  if grep -qi "password authentication failed" <<<"$err"; then
    cat >&2 <<'MSG'
entrypoint: the saved database was created with other passwords than the ones used now
            (deploy/.env, or the built-in defaults when there is no deploy/.env).
            On one PC, run:  ./run.sh fix-db   — it keeps all data (docs/RUN_AND_CLOSE.txt).
MSG
  fi
  return 1
}

case "${1:-web}" in
  web)
    wait_for_db
    if [ "${MIGRATE_ON_START:-1}" = "1" ]; then
      python manage.py migrate --database owner --noinput
    fi
    access_format='%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
    if [ "${LOG_FORMAT:-plain}" = "json" ]; then
      # One JSON object per request, like the application's own logs (P13.1).
      access_format='{"time":"%(t)s","remote":"%(h)s","method":"%(m)s","path":"%(U)s","status":%(s)s,"bytes":"%(B)s","ms":%(M)s,"agent":"%(a)s"}'
    fi
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${WEB_CONCURRENCY:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --access-logfile - --error-logfile - \
      --access-logformat "$access_format"
    ;;
  worker)
    wait_for_db
    exec python manage.py run_worker
    ;;
  migrate)
    wait_for_db
    exec python manage.py migrate --database owner --noinput
    ;;
  manage)
    shift
    exec python manage.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
