import pytest

from apps.audit.models import AuditLog
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user
from tests.plan_helpers import months, worked_example_rows

pytestmark = pytest.mark.django_db


@pytest.fixture
def w():
    agency = make_agency("alpha")
    root = make_root(agency)
    div, other = make_office(root, "DIV"), make_office(root, "OTHER")
    unit = make_office(div, "UNIT")
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    assign(make_user(agency, "head@a.gov"), div, "admin")
    assign(make_user(agency, "viewer@a.gov"), div, "read_only")
    boss = Json(api_client("boss@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    return {"agency": agency, "root": root, "div": div, "other": other, "unit": unit, "fy": fy, "boss": boss}


def new_plan(client, w, office="div"):
    r = client.post("/api/v1/plans", {"office_id": str(w[office].id), "fiscal_year_id": w["fy"]["id"]})
    assert r.status_code == 201, r.content
    return r.json()


def test_create_read_and_bulk_save(w):
    head = Json(api_client("head@a.gov"))
    plan = new_plan(head, w)
    assert plan["status"] == "draft" and plan["can_edit"] and plan["rows"] == []
    assert (
        head.post("/api/v1/plans", {"office_id": str(w["div"].id), "fiscal_year_id": w["fy"]["id"]}).json()[
            "code"
        ]
        == "plan_exists"
    )
    r = head.post(f"/api/v1/plans/{plan['id']}/save", {"rows": worked_example_rows()})
    assert r.status_code == 200, r.content
    saved = r.json()["plan"]
    assert set(r.json()["created"]) == {"out", "A", "B", "C"}
    acts = [row for row in saved["rows"] if row["row_kind"] == "activity"]
    assert [a["code"] for a in acts] == ["A", "B", "C"]
    assert acts[0]["parent"] == r.json()["created"]["out"]
    assert acts[0]["targets"][:3] == ["2", "3", "5"] and acts[0]["implementing_office_id"] == str(w["div"].id)
    assert saved["planned_cost"] == "1000000.00"
    assert [i["code"] for i in saved["issues"] if i["severity"] == "error"] == []

    # Second save: change one row, delete another, add an indicator.
    a_id = acts[0]["id"]
    r = head.post(
        f"/api/v1/plans/{plan['id']}/save",
        {
            "rows": [
                {"id": a_id, "title": "Activity A (renamed)", "implementing_office_id": str(w["unit"].id)}
            ],
            "deleted_rows": [acts[2]["id"]],
            "indicators": [
                {
                    "client_key": "i1",
                    "name": "Trainings held",
                    "annual_target": "4",
                    "targets": months([1, 1, 2]),
                }
            ],
        },
    ).json()["plan"]
    assert [a["title"] for a in r["rows"] if a["row_kind"] == "activity"] == [
        "Activity A (renamed)",
        "Activity B",
    ]
    assert r["rows"][1]["implementing_office_id"] == str(w["unit"].id)
    assert r["indicators"][0]["targets"][:3] == ["1", "1", "2"]


def test_scope_and_permissions(w):
    head = Json(api_client("head@a.gov"))
    plan = new_plan(head, w)
    viewer = Json(api_client("viewer@a.gov"))
    assert viewer.get(f"/api/v1/plans/{plan['id']}").json()["can_edit"] is False
    assert viewer.post(f"/api/v1/plans/{plan['id']}/save", {"rows": []}).status_code == 404
    assert (
        head.post(
            "/api/v1/plans", {"office_id": str(w["other"].id), "fiscal_year_id": w["fy"]["id"]}
        ).status_code
        == 404
    )
    other_plan = new_plan(w["boss"], w, office="other")
    assert head.get(f"/api/v1/plans/{other_plan['id']}").status_code == 404
    assert {p["office"]["code"] for p in head.get("/api/v1/plans").json()} == {"DIV"}
    # implementing office of another agency is unknown
    stranger = make_office(make_root(make_agency("beta")), "X")
    r = head.post(
        f"/api/v1/plans/{plan['id']}/save",
        {
            "rows": [
                {
                    "client_key": "a",
                    "row_kind": "activity",
                    "title": "t",
                    "implementing_office_id": str(stranger.id),
                }
            ]
        },
    )
    assert r.json()["code"] == "bad_office"


def test_submit_validation_approve_and_return(w):
    head = Json(api_client("head@a.gov"))
    plan = new_plan(head, w)
    rows = worked_example_rows()
    rows[1]["targets"] = months([2, 3, 4])  # sums to 9, not 10
    head.post(f"/api/v1/plans/{plan['id']}/save", {"rows": rows})
    r = head.post(f"/api/v1/plans/{plan['id']}/submit")
    assert r.status_code == 400 and r.json()["code"] == "invalid_plan"
    assert "targets_sum" in {i["code"] for i in r.json()["issues"] if i["severity"] == "error"}

    a = next(x for x in head.get(f"/api/v1/plans/{plan['id']}").json()["rows"] if x["code"] == "A")
    head.post(f"/api/v1/plans/{plan['id']}/save", {"rows": [{"id": a["id"], "targets": months([2, 3, 5])}]})
    assert head.post(f"/api/v1/plans/{plan['id']}/submit").json()["status"] == "submitted"
    assert head.post(f"/api/v1/plans/{plan['id']}/save", {"rows": []}).json()["code"] == "not_draft"
    assert head.post(f"/api/v1/plans/{plan['id']}/approve").status_code == 403

    boss = w["boss"]
    assert boss.post(f"/api/v1/plans/{plan['id']}/return", {"note": "Check B"}).json()["status"] == "draft"
    head.post(f"/api/v1/plans/{plan['id']}/submit")
    approved = boss.post(f"/api/v1/plans/{plan['id']}/approve").json()
    assert approved["status"] == "approved" and approved["approved_by"] == "boss@a.gov"
    assert (
        boss.patch(f"/api/v1/plans/{plan['id']}", {"approved_budget": "1200000"}).json()["approved_budget"]
        == "1200000.00"
    )
    assert head.patch(f"/api/v1/plans/{plan['id']}", {"approved_budget": "1"}).status_code == 403
    with context.agency_context(w["agency"].id):
        actions = list(AuditLog.objects.filter(entity_type="plan").values_list("action", flat=True))
    assert {"create", "submit", "return", "approve", "update"} <= set(actions)
