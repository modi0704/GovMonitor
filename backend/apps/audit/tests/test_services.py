import pytest

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.structure.models import Office
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user

pytestmark = pytest.mark.django_db


def rows(agency, **filters):
    with context.agency_context(agency.id):
        return list(AuditLog.objects.filter(**filters).order_by("id"))


def test_create_update_delete_with_field_level_diff():
    agency = make_agency("alpha")
    root = make_root(agency)
    with context.agency_context(agency.id):
        office = make_office(root, "DIV")
        office = Office.objects.get(pk=office.pk)
        office.name = "Renamed"
        office.save()
        office.save()  # no change -> no row
        office_id = office.pk
        office.delete()
    created, updated, deleted = rows(agency, entity_type="office", entity_id=str(office_id))
    assert created.action == "create" and created.after["code"] == "DIV" and created.before is None
    assert "agency_id" not in created.after
    assert (updated.action, updated.before, updated.after) == ("update", {"name": "DIV"}, {"name": "Renamed"})
    assert deleted.action == "delete" and deleted.before["name"] == "Renamed"
    assert created.office_id == office_id == deleted.office_id
    assert created.actor_type == "system"


def test_secrets_and_counters_are_not_recorded():
    agency = make_agency("alpha")
    user = make_user(agency, "a@alpha.gov")
    create = rows(agency, entity_type="user", action="create")[0]
    assert not any(audit.is_sensitive(k) for k in create.after)
    assert "password" not in create.after and "totp_secret" not in create.after
    with context.agency_context(agency.id):
        u = User.objects.get(pk=user.pk)
        u.failed_attempts = 3
        u.save()
        u.set_password("another-long-password")
        u.save()
    assert rows(agency, entity_type="user", action="update") == []  # counters and secrets only


def test_request_context_is_captured_via_the_api():
    agency = make_agency("alpha")
    root = make_root(agency)
    boss = make_user(agency, "boss@alpha.gov")
    assign(boss, root, "admin")
    client = Json(api_client("boss@alpha.gov"))
    r = client.c.post(
        "/api/v1/offices",
        {"parent_id": str(root.id), "name": "New", "code": "NEW"},
        content_type="application/json",
        HTTP_USER_AGENT="pytest-agent",
        HTTP_X_REQUEST_ID="req-12345678",
    )
    assert r.status_code == 201 and r["X-Request-ID"] == "req-12345678"
    row = rows(agency, entity_type="office", action="create")[-1]
    assert row.actor_type == "user" and row.actor_id == boss.id and row.actor_label == "boss@alpha.gov"
    assert (row.ip, row.user_agent, row.request_id) == ("127.0.0.1", "pytest-agent", "req-12345678")


def test_explicit_record_and_actor_override():
    agency = make_agency("alpha")
    with context.agency_context(agency.id), audit.acting_as("system", label="worker"):
        audit.record("export", entity_type="job", entity_id="j1", after={"kind": "xlsx"})
    row = rows(agency, action="export")[0]
    assert (row.actor_type, row.actor_label, row.entity_type, row.after) == (
        "system",
        "worker",
        "job",
        {"kind": "xlsx"},
    )
