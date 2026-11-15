"""Database privilege management for the two-role model of MASTERPLAN 6.1."""

from django.conf import settings
from django.db import connections

# Tables where app_user may only INSERT and SELECT (MASTERPLAN 6.5). Filled in by later phases.
APPEND_ONLY_TABLES: tuple[str, ...] = ("audit_log",)
# Tables app_user may not touch at all; only app_owner (platform-owner operations) reads them.
OWNER_ONLY_TABLES: tuple[str, ...] = ("platform_admin",)


def apply_grants(using: str) -> None:
    """Grant app_user DML on every table and sequence the migrating role owns. Idempotent.

    Runs after every ``migrate`` (post_migrate signal). Append-only tables then have UPDATE and
    DELETE revoked again so that the database itself forbids rewriting history.
    """
    connection = connections[using]
    app_role = settings.DB_APP_ROLE
    with connection.cursor() as cur:
        cur.execute("SELECT current_user")
        (current,) = cur.fetchone()
        if current == app_role:
            return  # migrating as app_user would be a misconfiguration; nothing to grant
        q_role = connection.ops.quote_name(app_role)
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {q_role}")
        cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {q_role}")
        cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {q_role}")
        cur.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {q_role}")
        for table in OWNER_ONLY_TABLES:
            cur.execute("SELECT to_regclass(%s)", [f"public.{table}"])
            if cur.fetchone()[0] is not None:
                cur.execute(f"REVOKE ALL ON {connection.ops.quote_name(table)} FROM {q_role}")
        for table in APPEND_ONLY_TABLES:
            cur.execute("SELECT to_regclass(%s)", [f"public.{table}"])
            if cur.fetchone()[0] is not None:
                cur.execute(
                    f"REVOKE UPDATE, DELETE, TRUNCATE ON {connection.ops.quote_name(table)} FROM {q_role}"
                )
