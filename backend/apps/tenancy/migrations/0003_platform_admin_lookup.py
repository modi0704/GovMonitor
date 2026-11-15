from django.db import migrations

# app_user has no privileges on platform_admin. Agency administrators still need to name the
# vendor person they grant support access to (P1.7): these return only id/email of active admins.
CREATE = """
CREATE OR REPLACE FUNCTION platform_admin_lookup(p_email text)
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT id FROM platform_admin WHERE email = lower(btrim(p_email)) AND is_active LIMIT 1
$$;
CREATE OR REPLACE FUNCTION platform_admin_emails(p_ids uuid[])
RETURNS TABLE (id uuid, email varchar)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT id, email FROM platform_admin WHERE id = ANY(p_ids)
$$;
REVOKE ALL ON FUNCTION platform_admin_lookup(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_emails(uuid[]) FROM PUBLIC;
"""
DROP = """
DROP FUNCTION IF EXISTS platform_admin_lookup(text);
DROP FUNCTION IF EXISTS platform_admin_emails(uuid[]);
"""


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0002_rls")]

    operations = [migrations.RunSQL(CREATE, DROP)]
