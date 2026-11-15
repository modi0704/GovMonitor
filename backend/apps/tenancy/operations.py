"""Migration operation that puts a table under tenant row-level security (MASTERPLAN 6.1, P1.2).

Usage in a migration::

    from apps.tenancy.operations import EnableTenantRLS
    operations = [..., EnableTenantRLS("office")]

Effect (idempotent)::

    ALTER TABLE t ENABLE ROW LEVEL SECURITY;  ALTER TABLE t FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON t
      USING (agency_id = <current agency>) WITH CHECK (agency_id = <current agency>);

``<current agency>`` is ``NULLIF(current_setting('app.agency_id', true), '')::uuid``: NULL when no
agency is set, so a request without an agency sees zero rows. (``NULLIF`` matters: once a
transaction-local value has been set on a connection, the setting reads back as '' afterwards, and
``''::uuid`` would raise instead of matching nothing.)
"""

from django.db.migrations.operations.base import Operation

CURRENT_AGENCY_SQL = "NULLIF(current_setting('app.agency_id', true), '')::uuid"
POLICY_NAME = "tenant_isolation"
GLOBAL_READ_POLICY_NAME = "global_read"


def tenant_rls_sql(table: str, column: str = "agency_id", allow_global_select: bool = False) -> list[str]:
    q = f'"{table}"'
    stmts = [
        f"ALTER TABLE {q} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {q} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS {POLICY_NAME} ON {q}",
        f'CREATE POLICY {POLICY_NAME} ON {q} USING ("{column}" = {CURRENT_AGENCY_SQL}) '
        f'WITH CHECK ("{column}" = {CURRENT_AGENCY_SQL})',
        f"DROP POLICY IF EXISTS {GLOBAL_READ_POLICY_NAME} ON {q}",
    ]
    if allow_global_select:
        # System-wide rows (agency_id IS NULL) are readable by every agency, writable by none.
        stmts.append(f'CREATE POLICY {GLOBAL_READ_POLICY_NAME} ON {q} FOR SELECT USING ("{column}" IS NULL)')
    return stmts


def disable_tenant_rls_sql(table: str) -> list[str]:
    q = f'"{table}"'
    return [
        f"DROP POLICY IF EXISTS {GLOBAL_READ_POLICY_NAME} ON {q}",
        f"DROP POLICY IF EXISTS {POLICY_NAME} ON {q}",
        f"ALTER TABLE {q} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {q} DISABLE ROW LEVEL SECURITY",
    ]


class EnableTenantRLS(Operation):
    reversible = True
    reduces_to_sql = True

    def __init__(self, table: str, column: str = "agency_id", allow_global_select: bool = False):
        self.table = table
        self.column = column
        self.allow_global_select = allow_global_select

    def state_forwards(self, app_label, state):
        pass  # database-only operation

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        for sql in tenant_rls_sql(self.table, self.column, self.allow_global_select):
            schema_editor.execute(sql)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        for sql in disable_tenant_rls_sql(self.table):
            schema_editor.execute(sql)

    def describe(self):
        return f"Enable tenant row-level security on {self.table}"

    @property
    def migration_name_fragment(self):
        return f"rls_{self.table}"

    def deconstruct(self):
        kwargs = {"table": self.table}
        if self.column != "agency_id":
            kwargs["column"] = self.column
        if self.allow_global_select:
            kwargs["allow_global_select"] = True
        return self.__class__.__name__, [], kwargs
