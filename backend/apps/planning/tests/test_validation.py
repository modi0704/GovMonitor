import pytest

from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user
from tests.plan_helpers import months

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx():
    agency = make_agency("alpha")
    root = make_root(agency)
    div = make_office(root, "DIV")
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    boss = Json(api_client("boss@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    plan = boss.post("/api/v1/plans", {"office_id": str(div.id), "fiscal_year_id": fy["id"]}).json()
    return boss, plan, fy, div


def act(key, **kw):
    base = {
        "client_key": key,
        "row_kind": "activity",
        "title": f"Activity {key}",
        "code": key,
        "measure_type": "quantity",
        "annual_target": "4",
        "total_cost": "100",
        "targets": months([4]),
    }
    return {**base, **kw}


def issues(boss, plan, rows=None, indicators=None):
    data = boss.post(
        f"/api/v1/plans/{plan['id']}/save", {"rows": rows or [], "indicators": indicators or []}
    ).json()
    return {(i["code"], i["severity"]) for i in data["plan"]["issues"]}


def test_rules_are_warnings_on_save(ctx):
    boss, plan, *_ = ctx
    found = issues(
        boss,
        plan,
        rows=[
            act("A", targets=months([1])),  # sum 1 != 4
            act("A2", code="A"),  # duplicate code
            act("C", unit_cost="10"),  # 4 x 10 = 40 != 100
            act("Z", total_cost="0"),  # zero cost under cost share
            act("N", annual_target="0", targets=months([])),  # no target
        ],
    )
    assert {
        ("targets_sum", "warning"),
        ("duplicate_code", "warning"),
        ("cost_mismatch", "warning"),
        ("zero_cost", "warning"),
        ("no_target", "warning"),
    } <= found


def test_submit_turns_rules_into_errors_except_cost_warnings(ctx):
    boss, plan, *_ = ctx
    boss.post(
        f"/api/v1/plans/{plan['id']}/save", {"rows": [act("A", unit_cost="10"), act("Z", total_cost="0")]}
    )
    r = boss.post(f"/api/v1/plans/{plan['id']}/submit")
    assert r.status_code == 200 and r.json()["status"] == "submitted"  # cost warnings do not block


def test_manual_weights_must_sum_to_one(ctx):
    boss, plan, fy, _ = ctx
    boss.patch(f"/api/v1/scoring-profiles/{fy['profile_id']}", {"weighting": "manual"})
    boss.post(
        f"/api/v1/plans/{plan['id']}/save",
        {"rows": [act("A", manual_weight="0.5"), act("B", manual_weight="0.4")]},
    )
    r = boss.post(f"/api/v1/plans/{plan['id']}/submit")
    assert ("weights_sum", "error") in {(i["code"], i["severity"]) for i in r.json()["issues"]}


def test_recurring_needs_a_planned_month_and_indicator_sums(ctx):
    boss, plan, *_ = ctx
    found = issues(
        boss,
        plan,
        rows=[act("R", measure_type="recurring", targets=months([]))],
        indicators=[{"client_key": "i", "name": "Ind", "annual_target": "10", "targets": months([3])}],
    )
    assert ("no_target", "warning") in found and ("indicator_targets_sum", "warning") in found


def test_empty_plan_cannot_be_submitted(ctx):
    boss, plan, *_ = ctx
    r = boss.post(f"/api/v1/plans/{plan['id']}/submit")
    assert ("empty_plan", "error") in {(i["code"], i["severity"]) for i in r.json()["issues"]}


def test_bad_numbers_are_rejected(ctx):
    boss, plan, *_ = ctx
    r = boss.post(f"/api/v1/plans/{plan['id']}/save", {"rows": [act("A", annual_target="ten")]})
    assert r.status_code == 400 and r.json()["code"] == "bad_number"
