#!/usr/bin/env bash
# GovMonitor on one computer (Windows Git Bash, Linux or macOS) with Docker Desktop.
#
#   ./run.sh start    build if needed, start, and wait until the app answers
#   ./run.sh stop     stop the app (all data is kept)
#   ./run.sh update   get the newest version (git pull), then start
#   ./run.sh demo     load the practice agencies (sample data)
#   ./run.sh setup    set up your real agency (once; asks a few questions)
#   ./run.sh status   show what is running
#   ./run.sh logs     show the last messages (send these when asking for help)
#   ./run.sh fix-db   the app says the database refused its password: set the database's
#                     passwords to the current settings (all data is kept), then start
#
# Settings come from deploy/.env when that file exists, otherwise from the built-in defaults —
# always the same way, so the saved database and the app agree on their passwords.
set -euo pipefail
cd "$(dirname "$0")"

URL="http://localhost:${WEB_PORT:-8000}"

compose() {
  if [ -f deploy/.env ]; then
    docker compose -f deploy/docker-compose.yml --env-file deploy/.env "$@"
  else
    docker compose -f deploy/docker-compose.yml "$@"
  fi
}

need_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Open Docker Desktop, wait until it says 'Engine running', and try again."
    exit 1
  fi
}

wait_until_up() {
  echo "Waiting for the app to answer (up to 3 minutes)..."
  for _ in $(seq 1 90); do
    if curl -fsS "$URL/api/v1/health" >/dev/null 2>&1; then
      compose up -d >/dev/null 2>&1 || true  # also start the parts that waited for the app
      echo
      echo "GovMonitor is running: open $URL/ in your browser."
      return 0
    fi
    sleep 2
  done
  echo
  echo "The app did not start. Its last messages:"
  compose logs --tail 15 web 2>&1 | tail -15
  if compose logs --tail 60 web 2>&1 | grep -qi "password authentication failed"; then
    echo
    echo "=> The saved database uses other passwords than these settings. Run:  ./run.sh fix-db"
  else
    echo
    echo "=> Send these messages (or the output of ./run.sh logs) to your IT person."
  fi
  return 1
}

start() {
  need_docker
  # 'up' reports an error while the app is still starting; wait_until_up decides.
  compose up -d --build || true
  wait_until_up
}

case "${1:-}" in
  start)
    start
    ;;
  stop)
    need_docker
    compose stop
    echo "GovMonitor is stopped. Your data is kept. Start it again with: ./run.sh start"
    ;;
  update)
    git pull
    start
    ;;
  demo)
    need_docker
    compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.dev web entrypoint.sh manage seed_demo
    echo
    echo "Practice data loaded. Sign in at $URL/ as admin@sample-ministry.demo / demo-password-2026"
    ;;
  setup)
    need_docker
    compose exec web entrypoint.sh manage initialize_workspace
    ;;
  status)
    need_docker
    compose ps
    ;;
  logs)
    need_docker
    compose logs --tail 80 web worker db
    ;;
  fix-db)
    need_docker
    compose up -d db
    echo "Waiting for the database..."
    for _ in $(seq 1 60); do
      compose exec -T db pg_isready -U postgres -d govmonitor >/dev/null 2>&1 && break
      sleep 2
    done
    # The database's own setup script is safe to run again: it sets the two application passwords
    # to the current settings and changes nothing else.
    compose exec -T -u postgres db bash /docker-entrypoint-initdb.d/10-init-roles.sh
    compose up -d --force-recreate web worker || true
    wait_until_up
    ;;
  *)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
