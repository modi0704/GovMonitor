#!/usr/bin/env bash
# Phase 13 exit check (P13.3): backup → wipe (containers AND volumes, like a fresh machine) →
# start empty → restore, then the frozen results (the dashboard's numbers for locked months) and
# the stored files must be exactly as before. Needs the image built (make build).
set -euo pipefail
cd "$(dirname "$0")/.."
export COMPOSE="docker compose -f deploy/docker-compose.yml"
export BACKUP_DIR=$(mktemp -d)
WEB_PORT=${WEB_PORT:-8000}
trap 'rm -rf "$BACKUP_DIR"' EXIT

wait_healthy() {
  for _ in $(seq 1 90); do curl -fsS "http://localhost:$WEB_PORT/api/v1/health" >/dev/null 2>&1 && return 0; sleep 2; done
  echo "not healthy" >&2; return 1
}
numbers() {
  $COMPOSE exec -T web entrypoint.sh manage shell -c "
import json
from apps.results.models import PeriodResult
rows = PeriodResult.objects.using('owner').select_related('office', 'period')
print(json.dumps(sorted((r.office.code, r.period.month_index, r.view, str(r.cum_actual), str(r.cum_plan)) for r in rows)))
" | tail -1
}
files() {  # stored files, without the worker's heartbeat (it changes every few seconds)
  $COMPOSE exec -T web sh -c 'cd /data/files && find . -type f ! -path "./_system/*" | sort | xargs -r sha256sum'
}

$COMPOSE up -d
wait_healthy
$COMPOSE exec -T -e DJANGO_SETTINGS_MODULE=config.settings.dev web entrypoint.sh manage seed_demo >/dev/null
# A stored file to carry across: an export produced by the worker.
$COMPOSE exec -T web entrypoint.sh manage shell -c "
from apps.tenancy.models import Agency
from apps.tenancy import context
from apps.jobs import worker
from apps.planning.models import ReportingPeriod
from apps.structure.models import Office
a = Agency.objects.using('owner').get(code='sample-ministry')
with context.agency_context(a.id):
    root = Office.objects.get(parent=None)
    dec = ReportingPeriod.objects.get(fiscal_year__label='2023', month_index=12)
    worker.enqueue('export_xlsx', {'scope': 'agency', 'office_id': str(root.id), 'period_id': str(dec.id), 'view': 'owner'})
" >/dev/null
export_done() {
  $COMPOSE exec -T web entrypoint.sh manage shell -c "
from apps.jobs.models import Job
print(Job.objects.using('owner').filter(kind='export_xlsx', status='done').count())" | tail -1
}
# Back up only once the job is recorded as done; a job caught mid-run is simply run again after a
# restore (exports are repeatable), which would add a second file and spoil the comparison.
for _ in $(seq 1 60); do [ "$(export_done)" = "1" ] && break; sleep 2; done
before_numbers=$(numbers); before_files=$(files)
[ "$(echo "$before_numbers" | wc -c)" -gt 100 ] || { echo "no results to compare" >&2; exit 1; }
[ -n "$before_files" ] || { echo "no stored file to compare" >&2; exit 1; }

deploy/backup.sh
archive=$(ls -1 "$BACKUP_DIR"/govmonitor-*.tar | head -1)
# Retention: with KEEP=2, a third backup removes the oldest.
for _ in 1 2; do sleep 1; KEEP=2 deploy/backup.sh >/dev/null; done
[ "$(ls -1 "$BACKUP_DIR"/govmonitor-*.tar | wc -l)" = "2" ] || { echo "retention did not keep 2" >&2; exit 1; }
archive=$(ls -1t "$BACKUP_DIR"/govmonitor-*.tar | head -1)

echo "wiping containers and volumes"
$COMPOSE down -v
$COMPOSE up -d
wait_healthy
[ "$(numbers)" = "[]" ] || { echo "the wipe left data behind" >&2; exit 1; }

deploy/restore.sh "$archive" --yes
wait_healthy
after_numbers=$(numbers); after_files=$(files)
[ "$before_numbers" = "$after_numbers" ] || { echo "results differ after restore" >&2; exit 1; }
[ "$before_files" = "$after_files" ] || { echo "files differ after restore" >&2; exit 1; }
echo "backup/restore: ok ($(echo "$before_numbers" | grep -o '\],' | wc -l) results, $(echo "$before_files" | wc -l) file(s) identical)"
