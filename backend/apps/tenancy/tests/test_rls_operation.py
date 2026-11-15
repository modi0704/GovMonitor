import uuid

import pytest
from django.db import connection, connections

from apps.tenancy import context
from apps.tenancy.models import Agency
from apps.tenancy.operations import EnableTenantRLS, disable_tenant_rls_sql, tenant_rls_sql


def _policies(table):
    with connections["owner"].cursor() as cur:
        cur.execute("SELECT policyname, cmd FROM pg_policies WHERE tablename = %s ORDER BY 1", [table])
        return cur.fetchall()


def test_operation_deconstructs():
    op = EnableTenantRLS("export_template", allow_global_select=True)
    assert op.deconstruct() == (
        "EnableTenantRLS",
        [],
        {"table": "export_template", "allow_global_select": True},
    )
    assert op.migration_name_fragment == "rls_export_template"


@pytest.mark.django_db(databases=["default", "owner"], transaction=True)
def test_sql_is_idempotent_and_reversible():
    owner = connections["owner"]
    with owner.cursor() as cur:
        cur.execute("CREATE TABLE rls_probe (id int, agency_id uuid)")
        try:
            for _ in range(2):  # twice: idempotent
                for sql in tenant_rls_sql("rls_probe", allow_global_select=True):
                    cur.execute(sql)
            assert _policies("rls_probe") == [("global_read", "SELECT"), ("tenant_isolation", "ALL")]
            for sql in disable_tenant_rls_sql("rls_probe"):
                cur.execute(sql)
            assert _policies("rls_probe") == []
        finally:
            cur.execute("DROP TABLE rls_probe")


@pytest.mark.django_db
def test_app_user_sees_only_current_agency():
    a, b = uuid.uuid4(), uuid.uuid4()
    with context.agency_context(a):
        Agency.objects.create(id=a, name="A", code="a")
    with context.agency_context(b):
        Agency.objects.create(id=b, name="B", code="b")
        assert list(Agency.objects.values_list("code", flat=True)) == ["b"]
    with context.agency_context(a):
        assert list(Agency.objects.values_list("code", flat=True)) == ["a"]
    # No agency set: nothing is visible (the setting is now '' on this connection, not NULL).
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('app.agency_id', true)")
        assert cur.fetchone()[0] == ""
    assert Agency.objects.count() == 0
