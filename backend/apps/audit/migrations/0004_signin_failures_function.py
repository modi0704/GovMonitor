from django.db import migrations

# Sign-in rate limit (P14.1): count recent failed sign-ins from one address across all agencies.
# app_user cannot read other agencies' audit rows, so this runs with its owner's rights and
# returns only a number (MASTERPLAN 6.1 pattern, like auth_lookup_user).
CREATE = """
CREATE OR REPLACE FUNCTION signin_failures(p_ip inet, p_since timestamptz)
RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT count(*)::integer FROM audit_log
    WHERE action = 'login_failed' AND ip = p_ip AND at >= p_since
$$;
REVOKE ALL ON FUNCTION signin_failures(inet, timestamptz) FROM PUBLIC;
CREATE INDEX IF NOT EXISTS audit_log_failed_signin_ip ON audit_log (ip, at) WHERE action = 'login_failed';
"""

DROP = """
DROP INDEX IF EXISTS audit_log_failed_signin_ip;
DROP FUNCTION IF EXISTS signin_failures(inet, timestamptz);
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0003_auditlog_audit_agency_id")]

    operations = [migrations.RunSQL(CREATE, DROP)]
