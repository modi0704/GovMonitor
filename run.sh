#!/usr/bin/env bash
# GovMonitor on one computer (Windows Git Bash, Linux or macOS) with Docker Desktop.
#
#   ./run.sh start    build if needed, start, and wait until the app answers
#   ./run.sh stop     stop the app (all data is kept)
#   ./run.sh update   get the newest version (git pull), then start
#   ./run.sh demo     load the practice agencies (sample data)
#   ./run.sh setup    set up your real agency (once; asks a few questions)
#   ./run.sh login on|off   switch the sign-in page on or off (off = testing mode, the default)
#   ./run.sh status   show what is running
#   ./run.sh logs     show the last messages (send these when asking for help)
#   ./run.sh reset-password [email]   with sign-in on: list the administrator accounts, or give
#                     one a new temporary password
#   ./run.sh fix-db   the app says the database refused its password: set the database's
#                     passwords to the current settings (all data is kept), then start
#
# Settings come from deploy/.env when that file exists, otherwise from the built-in defaults —
# always the same way, so the saved database and the app agree on their passwords.
set -euo pipefail
cd "$(dirname "$0")"
# Git Bash on Windows rewrites arguments that look like Linux paths (/docker-entrypoint-initdb.d/…
# becomes C:/Program Files/Git/…) before Docker sees them; container paths must stay as written.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

URL="http://localhost:${WEB_PORT:-8000}"

# Testing mode (no sign-in) unless deploy/.env says LOGIN_DISABLED=0. In testing mode only the
# database, the app and its worker run: the app is published on this PC alone (127.0.0.1), and the
# HTTPS front door (Caddy) that other computers could reach stays stopped.
if [ -f deploy/.env ] && grep -q '^LOGIN_DISABLED=' deploy/.env; then
  LOGIN_DISABLED=$(sed -n 's/^LOGIN_DISABLED=//p' deploy/.env | tail -1)
else
  export LOGIN_DISABLED=1
fi
if [ "$LOGIN_DISABLED" = "1" ]; then SERVICES="db web worker"; else SERVICES=""; fi

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

manage_quiet() {  # run a Django command; print only its own last line
  compose exec -T web entrypoint.sh manage "$@" 2>/dev/null | tail -1
}

load_demo() {
  compose exec -T -e DJANGO_SETTINGS_MODULE=config.settings.dev web entrypoint.sh manage seed_demo
}

wait_until_up() {
  echo "Waiting for the app to answer (up to 3 minutes)..."
  for _ in $(seq 1 90); do
    if curl -fsS "$URL/api/v1/health" >/dev/null 2>&1; then
      # shellcheck disable=SC2086 # SERVICES is a list of names
      compose up -d $SERVICES >/dev/null 2>&1 || true  # also start the parts that waited for the app
      if [ "$LOGIN_DISABLED" = "1" ]; then
        agencies=$(manage_quiet shell -v 0 -c \
          "from apps.tenancy.models import Agency; print(Agency.objects.using('owner').count())")
        if [ "$agencies" = "0" ]; then
          echo "The database is empty: loading the practice data so there is something to see..."
          load_demo >/dev/null
        fi
      fi
      echo
      echo "GovMonitor is running: open $URL/ in your browser."
      if [ "$LOGIN_DISABLED" = "1" ]; then
        echo "Testing mode: no sign-in needed. Only this PC can open it."
        echo "(To bring the sign-in page back later: ./run.sh login on)"
      fi
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
  # shellcheck disable=SC2086
  compose up -d --build $SERVICES || true
  if [ "$LOGIN_DISABLED" = "1" ]; then
    compose stop caddy >/dev/null 2>&1 || true  # no door for other computers in testing mode
  fi
  wait_until_up
}

set_login() {  # set_login 0|1: write LOGIN_DISABLED to deploy/.env (created if missing)
  if [ ! -f deploy/.env ]; then
    printf '# Settings for this PC. Missing values use the built-in defaults.\n' > deploy/.env
  fi
  if grep -q '^LOGIN_DISABLED=' deploy/.env; then
    sed -i.bak "s/^LOGIN_DISABLED=.*/LOGIN_DISABLED=$1/" deploy/.env && rm -f deploy/.env.bak
  else
    printf 'LOGIN_DISABLED=%s\n' "$1" >> deploy/.env
  fi
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
    load_demo
    echo
    if [ "$LOGIN_DISABLED" = "1" ]; then
      echo "Practice data loaded. Open $URL/ (no sign-in needed)."
    else
      echo "Practice data loaded. Sign in at $URL/ as admin@sample-ministry.demo / demo-password-2026"
    fi
    ;;
  setup)
    need_docker
    compose exec web entrypoint.sh manage initialize_workspace
    ;;
  login)
    case "${2:-}" in
      on) set_login 0; LOGIN_DISABLED=0; SERVICES=""; echo "Sign-in switched ON." ;;
      off) set_login 1; LOGIN_DISABLED=1; SERVICES="db web worker"; echo "Sign-in switched OFF (testing mode)." ;;
      *) echo "Use: ./run.sh login on   or   ./run.sh login off"; exit 1 ;;
    esac
    export LOGIN_DISABLED
    start
    ;;
  reset-password)
    need_docker
    if [ -n "${2:-}" ]; then
      compose exec -T web entrypoint.sh manage reset_password --email "$2"
    else
      compose exec -T web entrypoint.sh manage reset_password
    fi
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
    sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
