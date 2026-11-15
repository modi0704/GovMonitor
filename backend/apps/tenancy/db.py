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


def _short(name: str) -> str:
    """PostgreSQL identifiers are at most 63 bytes: keep the start and add a stable hash."""
    import hashlib

    if len(name) <= 63:
        return name
    return f"{name[:54]}_{hashlib.sha256(name.encode()).hexdigest()[:8]}"


def tenant_foreign_keys() -> list[tuple[str, str, str]]:
    """(table, column, referenced table) for every foreign key between two tenant tables."""
    from django.apps import apps

    def tenant(model) -> bool:
        return (
            any(f.column == "agency_id" for f in model._meta.concrete_fields)
            and model._meta.db_table != "agency"
        )

    out = set()
    for model in apps.get_models():
        if not tenant(model) or not model._meta.managed:
            continue
        for f in model._meta.concrete_fields:
            if not f.is_relation or not f.many_to_one or f.column == "agency_id":
                continue
            target = f.related_model
            if tenant(target) and target._meta.pk.column == f.target_field.column:
                out.add((model._meta.db_table, f.column, target._meta.db_table))
    return sorted(out)


def apply_tenant_foreign_keys(using: str) -> int:
    """P14.1: make the database itself refuse a row that points at another agency's row.

    Foreign-key checks bypass row-level security, so a plain ``office_id`` could name an office of
    another agency if code ever wrote a raw id. For every foreign key between tenant tables this
    adds ``FOREIGN KEY (agency_id, <column>) REFERENCES <table> (agency_id, id)`` (with a unique
    key on ``(agency_id, id)`` of the referenced table). Idempotent; runs after every migrate, so
    tables added later are covered too. Returns the number of constraints added.
    """
    connection = connections[using]
    q = connection.ops.quote_name
    added = 0
    with connection.cursor() as cur:
        cur.execute("SELECT conname FROM pg_constraint")
        existing = {row[0] for row in cur.fetchall()}
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = {row[0] for row in cur.fetchall()}
        for table, column, target in tenant_foreign_keys():
            if table not in tables or target not in tables:
                continue
            key = _short(f"{target}_agency_id_id_key")
            if key not in existing:
                cur.execute(f"ALTER TABLE {q(target)} ADD CONSTRAINT {q(key)} UNIQUE (agency_id, id)")
                existing.add(key)
            name = _short(f"{table}_{column}_same_agency")
            if name not in existing:
                cur.execute(
                    f"ALTER TABLE {q(table)} ADD CONSTRAINT {q(name)} FOREIGN KEY (agency_id, {q(column)}) "
                    f"REFERENCES {q(target)} (agency_id, id) DEFERRABLE INITIALLY DEFERRED"
                )
                existing.add(name)
                added += 1
    return added
