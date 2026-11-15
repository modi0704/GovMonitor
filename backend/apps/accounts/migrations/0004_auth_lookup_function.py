from django.db import migrations

# Sign-in must find a user before the agency is known, but app_user cannot read "user" rows of an
# agency that is not set. This function runs with its owner's rights (app_owner, BYPASSRLS) and
# returns only id, agency id and password hash for exactly one email (MASTERPLAN 6.1).
CREATE = """
CREATE OR REPLACE FUNCTION auth_lookup_user(p_email text)
RETURNS TABLE (id uuid, agency_id uuid, password varchar)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT u.id, u.agency_id, u.password
    FROM "user" u
    WHERE u.email = lower(btrim(p_email))
    LIMIT 1
$$;
REVOKE ALL ON FUNCTION auth_lookup_user(text) FROM PUBLIC;
"""

DROP = "DROP FUNCTION IF EXISTS auth_lookup_user(text);"


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_rls")]

    operations = [migrations.RunSQL(CREATE, DROP)]
