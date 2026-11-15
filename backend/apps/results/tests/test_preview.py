import pytest

from tests.factories import Json, api_client, assign, make_agency, make_office, make_root, make_user
from tests.plan_helpers import WORKED_EXAMPLE, months

pytestmark = pytest.mark.django_db


def test_preview_returns_engine_weights_and_planned_curve():
    agency = make_agency("alpha")
    root = make_root(agency)
    assign(make_user(agency, "boss@a.gov"), root, "admin")
    make_office(root, "X")
    boss = Json(api_client("boss@a.gov"))
    fy = boss.post("/api/v1/fiscal-years", {"label": "2026", "start_year": 2026}).json()
    acts = [
        {
            "key": code,
            "measure_type": "quantity",
            "annual_target": target,
            "total_cost": cost,
            "targets": months(plan),
        }
        for code, _, cost, target, plan in WORKED_EXAMPLE
    ]
    r = boss.post("/api/v1/results/preview", {"fiscal_year_id": fy["id"], "activities": acts}).json()
    assert {k: round(float(v), 6) for k, v in r["weights"].items()} == {"A": 0.6, "B": 0.3, "C": 0.1}
    assert [round(float(v), 6) for v in r["cum_plan"][:3]] == [0.12, 0.45, 1.0]
    assert r["funds_total"] == "1000000"
    assert boss.post("/api/v1/results/preview", {"fiscal_year_id": str(agency.id)}).status_code == 404
    directory = boss.get("/api/v1/offices/directory").json()
    assert [o["code"] for o in directory] == ["ROOT", "X"]
