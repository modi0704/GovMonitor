#!/usr/bin/env bash
# Starts deploy/docker-compose.cloud.yml against stand-ins for the managed services — PostgreSQL in
# a container and SeaweedFS as the S3-compatible store — and checks health and an export written to
# the bucket (Phase 13 exit check). Needs the image govmonitor:${GOVMONITOR_VERSION:-dev}.
# Usage: deploy/test-cloud-compose.sh        (cleans up after itself)
set -euo pipefail
cd "$(dirname "$0")/.."
PORT_DB=${PORT_DB:-5433}
PORT_S3=${PORT_S3:-8333}
WEB_PORT=${CLOUD_WEB_PORT:-8100}
ENV_FILE=$(mktemp)
COMPOSE="docker compose -f deploy/docker-compose.cloud.yml --env-file $ENV_FILE"

cleanup() {
  $COMPOSE down -v >/dev/null 2>&1 || true
  docker rm -f govmonitor-test-db govmonitor-test-s3 >/dev/null 2>&1 || true
  rm -f "$ENV_FILE"
}
trap cleanup EXIT

docker run -d --name govmonitor-test-db -p "$PORT_DB:5432" \
  -e POSTGRES_PASSWORD=pg -e APP_OWNER_PASSWORD=ownerpw -e APP_USER_PASSWORD=userpw -e APP_DB=govmonitor \
  -v "$PWD/deploy/db/init-roles.sh:/docker-entrypoint-initdb.d/10-init-roles.sh:ro" postgres:18 >/dev/null
docker run -d --name govmonitor-test-s3 -p "$PORT_S3:8333" chrislusf/seaweedfs:latest \
  server -s3 -s3.port=8333 -dir=/data >/dev/null
GW=$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')
for _ in $(seq 1 60); do docker exec govmonitor-test-db pg_isready -U postgres -d govmonitor >/dev/null 2>&1 && break; sleep 1; done

cat > "$ENV_FILE" <<ENV
SECRET_KEY=cloud-test-secret-key-0123456789abcdefghijkl
ALLOWED_HOSTS=localhost,127.0.0.1,web
CSRF_TRUSTED_ORIGINS=http://localhost:$WEB_PORT
DATABASE_URL=postgres://app_user:userpw@$GW:$PORT_DB/govmonitor
DATABASE_ADMIN_URL=postgres://app_owner:ownerpw@$GW:$PORT_DB/govmonitor
S3_ENDPOINT=http://$GW:$PORT_S3
S3_BUCKET=govmonitor-files
S3_ACCESS_KEY=test
S3_SECRET_KEY=test
SECURE_SSL=0
WEB_PORT=$WEB_PORT
ENV

# The bucket is created by the operator in real deployments; here with the image's own boto3.
IMAGE="govmonitor:${GOVMONITOR_VERSION:-dev}"
for _ in $(seq 1 30); do
  docker run --rm --network host --entrypoint python "$IMAGE" -c "
import boto3
s3 = boto3.client('s3', endpoint_url='http://127.0.0.1:$PORT_S3', aws_access_key_id='test',
                  aws_secret_access_key='test', region_name='us-east-1')
s3.create_bucket(Bucket='govmonitor-files')" >/dev/null 2>&1 && break
  sleep 2
done

$COMPOSE up -d
for _ in $(seq 1 60); do
  curl -fsS "http://localhost:$WEB_PORT/api/v1/health" | grep -q '"worker": {"ok": true' && break
  sleep 2
done
curl -fsS "http://localhost:$WEB_PORT/api/v1/health"; echo

$COMPOSE exec -T -e DJANGO_SETTINGS_MODULE=config.settings.dev web entrypoint.sh manage seed_demo >/dev/null
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
"
for _ in $(seq 1 60); do
  found=$(docker run --rm --network host --entrypoint python "$IMAGE" -c "
import boto3
s3 = boto3.client('s3', endpoint_url='http://127.0.0.1:$PORT_S3', aws_access_key_id='test',
                  aws_secret_access_key='test', region_name='us-east-1')
print(sum('/exports/' in o['Key'] for o in s3.list_objects_v2(Bucket='govmonitor-files').get('Contents', [])))")
  [ "$found" -ge 1 ] && { echo "cloud compose: ok (export stored in S3)"; exit 0; }
  sleep 2
done
echo "cloud compose: the export never reached the bucket" >&2
$COMPOSE logs --tail 50 >&2
exit 1
