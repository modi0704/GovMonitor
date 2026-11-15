import pytest
from django.db import DatabaseError, connection, transaction

from apps.audit.models import AuditLog
from apps.tenancy import context
from tests.factories import make_agency

pytestmark = pytest.mark.django_db


def test_app_user_cannot_update_or_delete_audit_rows():
    agency = make_agency("alpha")
    with context.agency_context(agency.id):
        row = AuditLog.objects.create(agency=agency, actor_type="system", action="test")
        for sql in (
            "UPDATE audit_log SET action = 'tampered'",
            "DELETE FROM audit_log",
            "TRUNCATE audit_log",
        ):
            with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(sql)
        assert AuditLog.objects.get(pk=row.pk).action == "test"
        with pytest.raises(RuntimeError):
            row.save()
        with pytest.raises(RuntimeError):
            row.delete()


def test_agency_reads_only_its_own_audit_rows():
    a, b = make_agency("a"), make_agency("b")
    for agency in (a, b):
        with context.agency_context(agency.id):
            AuditLog.objects.create(agency=agency, actor_type="system", action=f"for-{agency.code}")
    with context.agency_context(a.id):
        assert list(AuditLog.objects.values_list("action", flat=True)) == ["for-a"]
        with pytest.raises(DatabaseError, match="row-level security"), transaction.atomic():
            AuditLog.objects.create(agency=b, actor_type="system", action="forged")
