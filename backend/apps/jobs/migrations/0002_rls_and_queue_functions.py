from django.db import migrations

from apps.tenancy.operations import EnableTenantRLS

# The worker connects as app_user, which sees no agency's rows until an agency is set. These
# SECURITY DEFINER functions are the only cross-agency reads it needs (MASTERPLAN 6.7):
#   claim_next_job()          take the oldest queued job (FOR UPDATE SKIP LOCKED), mark it running
#   requeue_stale_jobs(mins)  jobs running longer than `mins` go back to the queue (worker start)
#   active_agency_ids()       agencies for the scheduler pass (auto-lock, daily alert scan)
FUNCTIONS = """
CREATE OR REPLACE FUNCTION claim_next_job()
RETURNS TABLE (job_id uuid, job_agency_id uuid)
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    UPDATE job SET status = 'running', attempts = attempts + 1, started_at = now()
    WHERE id = (
        SELECT id FROM job WHERE status = 'queued' ORDER BY created_at
        FOR UPDATE SKIP LOCKED LIMIT 1
    )
    RETURNING id, agency_id
$$;
CREATE OR REPLACE FUNCTION requeue_stale_jobs(p_minutes integer)
RETURNS integer
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    WITH moved AS (
        UPDATE job SET status = 'queued'
        WHERE status = 'running' AND started_at < now() - make_interval(mins => p_minutes)
        RETURNING 1
    )
    SELECT count(*)::integer FROM moved
$$;
CREATE OR REPLACE FUNCTION active_agency_ids()
RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT id FROM agency WHERE status = 'active' ORDER BY created_at
$$;
REVOKE ALL ON FUNCTION claim_next_job() FROM PUBLIC;
REVOKE ALL ON FUNCTION requeue_stale_jobs(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION active_agency_ids() FROM PUBLIC;
"""
DROP = """
DROP FUNCTION IF EXISTS claim_next_job();
DROP FUNCTION IF EXISTS requeue_stale_jobs(integer);
DROP FUNCTION IF EXISTS active_agency_ids();
"""


class Migration(migrations.Migration):
    dependencies = [("jobs", "0001_initial")]

    operations = [EnableTenantRLS("job"), migrations.RunSQL(FUNCTIONS, DROP)]
