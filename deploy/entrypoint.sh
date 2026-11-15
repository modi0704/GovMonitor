#!/usr/bin/env bash
# Container entrypoint. Commands: web | worker | migrate | manage <args...>
set -euo pipefail
cd /app/backend

wait_for_db() {
  for _ in $(seq 1 60); do
    if python - <<'PY' 2>/dev/null
import os, psycopg
psycopg.connect(os.environ["DATABASE_ADMIN_URL"], connect_timeout=2).close()
PY
    then return 0; fi
    sleep 1
  done
  echo "entrypoint: database not reachable" >&2
  return 1
}

case "${1:-web}" in
  web)
    wait_for_db
    if [ "${MIGRATE_ON_START:-1}" = "1" ]; then
      python manage.py migrate --database owner --noinput
    fi
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${WEB_CONCURRENCY:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --access-logfile - --error-logfile -
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
