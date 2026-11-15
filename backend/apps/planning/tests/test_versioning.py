"""P5.7 revisions and P5.9 copy to a new fiscal year."""

import pytest

from apps.planning.models import Activity, Plan
from apps.tenancy import context
from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user
from tests.plan_helpers import months, worked_example_rows

pytestmark = pytest.mark.django_db


@pytest.fixture
def w():
    agency = make_agency("alpha")
    root = make_root(agency)
    div = make_office(root, "DIV")
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    boss = Json(api_client("boss@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    plan = boss.post("/api/v1/plans", {"office_id": str(div.id), "fiscal_year_id": fy["id"]}).json()
    boss.post(f"/api/v1/plans/{plan['id']}/save", {"rows": worked_example_rows()})
    boss.post(f"/api/v1/plans/{plan['id']}/submit")
    boss.post(f"/api/v1/plans/{plan['id']}/approve")
    return {"agency": agency, "boss": boss, "plan": plan, "fy": fy, "div": div}


def test_revise_clones_with_same_lineage_then_supersedes_on_approval(w):
    boss, v1 = w["boss"], w["plan"]
    assert boss.post(f"/api/v1/plans/{v1['id']}/save", {"rows": []}).json()["code"] == "not_draft"
    r = boss.post(f"/api/v1/plans/{v1['id']}/revise")
    assert r.status_code == 201
    v2 = r.json()
    assert (v2["version"], v2["status"]) == (2, "draft")
    assert boss.post(f"/api/v1/plans/{v1['id']}/revise").json()["code"] == "revision_open"
    with context.agency_context(w["agency"].id):
        lineages = lambda pid: {a.lineage_id for a in Activity.objects.filter(plan_id=pid)}  # noqa: E731
        assert lineages(v1["id"]) == lineages(v2["id"])

    rows = {r["code"]: r for r in v2["rows"]}
    boss.post(
        f"/api/v1/plans/{v2['id']}/save",
        {
            "rows": [
                {"id": rows["A"]["id"], "annual_target": "12", "targets": months([2, 5, 5])},
                {
                    "client_key": "D",
                    "parent": rows["O1"]["id"],
                    "row_kind": "activity",
                    "code": "D",
                    "title": "New",
                    "measure_type": "quantity",
                    "annual_target": "1",
                    "total_cost": "50000",
                    "targets": months([0, 0, 1]),
                },
            ],
            "deleted_rows": [rows["C"]["id"]],
        },
    )
    diff = boss.get(f"/api/v1/plans/{v2['id']}/compare", **{"with": v1["id"]}).json()
    assert (diff["from_version"], diff["to_version"]) == (1, 2)
    assert [r["code"] for r in diff["added"]] == ["D"]
    assert [r["code"] for r in diff["removed"]] == ["C"]
    changed = {c["code"]: c["changes"] for c in diff["changed"]}
    assert set(changed) == {"A"} and changed["A"]["annual_target"] == {"before": "10", "after": "12"}

    boss.post(f"/api/v1/plans/{v2['id']}/submit")
    boss.post(f"/api/v1/plans/{v2['id']}/approve")
    versions = boss.get(f"/api/v1/plans/{v2['id']}/versions").json()
    assert [(v["version"], v["status"]) for v in versions] == [(2, "approved"), (1, "superseded")]
    with context.agency_context(w["agency"].id):
        assert Plan.objects.filter(status="approved").count() == 1


def test_copy_into_next_year_keeps_targets_with_new_lineage(w):
    boss, v1 = w["boss"], w["plan"]
    fy2 = boss.post("/api/v1/fiscal-years", {"label": "2027", "start_year": 2027}).json()
    r = boss.post(f"/api/v1/plans/{v1['id']}/copy", {"fiscal_year_id": fy2["id"]})
    assert r.status_code == 201
    copy = r.json()
    assert (copy["fiscal_year"]["label"], copy["version"], copy["status"]) == ("2027", 1, "draft")
    assert copy["approved_budget"] is None
    a = next(x for x in copy["rows"] if x["code"] == "A")
    assert a["targets"][:3] == ["2", "3", "5"] and a["parent"] is not None
    with context.agency_context(w["agency"].id):
        old = {x.lineage_id for x in Activity.objects.filter(plan_id=v1["id"])}
        new = {x.lineage_id for x in Activity.objects.filter(plan_id=copy["id"])}
        assert not old & new
    assert (
        boss.post(f"/api/v1/plans/{v1['id']}/copy", {"fiscal_year_id": fy2["id"]}).json()["code"]
        == "plan_exists"
    )
    assert boss.post(f"/api/v1/plans/{v1['id']}/copy", {"fiscal_year_id": w["fy"]["id"]}).status_code == 400


def test_plain_decimal_never_uses_exponents():
    from decimal import Decimal

    from apps.planning.numbers import plain

    assert [plain(Decimal(v)) for v in ("10.0000", "2.50", "0.0000", "1200000.00", "0.0001")] == [
        "10",
        "2.5",
        "0",
        "1200000",
        "0.0001",
    ]
