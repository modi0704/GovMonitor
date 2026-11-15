"""Phase 5 exit check: create, submit, approve, revise and re-approve a plan through the API;
every action appears in the audit log."""

import pytest

from apps.audit.models import AuditLog
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user
from tests.plan_helpers import months, worked_example_rows

pytestmark = pytest.mark.django_db


def test_plan_lifecycle_is_fully_audited():
    agency = make_agency("alpha")
    root = make_root(agency)
    div = make_office(root, "DIV")
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    assign(make_user(agency, "head@a.gov"), div, "admin")
    boss, head = Json(api_client("boss@a.gov")), Json(api_client("head@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    boss.patch(f"/api/v1/fiscal-years/{fy['id']}", {"status": "open"})

    v1 = head.post("/api/v1/plans", {"office_id": str(div.id), "fiscal_year_id": fy["id"]}).json()
    head.post(f"/api/v1/plans/{v1['id']}/save", {"rows": worked_example_rows()})
    assert head.post(f"/api/v1/plans/{v1['id']}/submit").json()["status"] == "submitted"
    assert boss.post(f"/api/v1/plans/{v1['id']}/approve").json()["status"] == "approved"

    v2 = head.post(f"/api/v1/plans/{v1['id']}/revise").json()
    a = next(r for r in v2["rows"] if r["code"] == "A")
    head.post(
        f"/api/v1/plans/{v2['id']}/save",
        {"rows": [{"id": a["id"], "annual_target": "12", "targets": months([2, 5, 5])}]},
    )
    head.post(f"/api/v1/plans/{v2['id']}/submit")
    assert boss.post(f"/api/v1/plans/{v2['id']}/approve").json()["status"] == "approved"
    assert boss.get(f"/api/v1/plans/{v1['id']}").json()["status"] == "superseded"

    with context.agency_context(agency.id):
        log = list(
            AuditLog.objects.order_by("id").values_list("action", "entity_type", "entity_id", "actor_label")
        )
    plan_events = [(a, e, actor) for a, e, eid, actor in log if e == "plan"]
    assert [(a, actor) for a, _, actor in plan_events if a in ("submit", "approve", "revise")] == [
        ("submit", "head@a.gov"),
        ("approve", "boss@a.gov"),
        ("revise", "head@a.gov"),
        ("submit", "head@a.gov"),
        ("approve", "boss@a.gov"),
    ]
    assert ("create", "plan") in {(a, e) for a, e, _ in plan_events}
    # Row-level edits are recorded with the activity they changed.
    changed = [x for x in log if x[0] == "update" and x[1] == "activity" and x[2] == a["id"]]
    assert changed and changed[0][3] == "head@a.gov"
    with context.agency_context(agency.id):
        approve_v2 = AuditLog.objects.filter(action="approve").order_by("id").last()
    assert approve_v2.after["superseded"] == [v1["id"]] and approve_v2.office_id == div.id
